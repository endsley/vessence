# agent_skills/conversation_manager.py
import os
import sys
import logging
import threading
import time
import uuid
import sqlite3
import datetime
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class silence_stderr_fd:
    def __enter__(self):
        self.stdout_fd = os.dup(1)
        self.stderr_fd = os.dup(2)
        self.null_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.null_fd, 1)
        os.dup2(self.null_fd, 2)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self.stdout_fd, 1)
        os.dup2(self.stderr_fd, 2)
        os.close(self.null_fd)
        os.close(self.stdout_fd)
        os.close(self.stderr_fd)


os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')
with silence_stderr_fd():
    import chromadb
import litellm
import tiktoken
from chromadb.utils import embedding_functions
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import (
    LOCAL_LLM_MODEL_LITELLM, OLLAMA_BASE_URL as LOCAL_LLM_BASE_URL,
    VAULT_DIR as VAULT_PATH,
    VECTOR_DB_LONG_TERM  as LONG_TERM_MEMORY_PATH,
    VECTOR_DB_SHORT_TERM as SHORT_TERM_MEMORY_PATH,
    LEDGER_DB_PATH, IDLE_TIMEOUT_SECS as IDLE_TIMEOUT_SECONDS,
    SHORT_TERM_TTL_DAYS, CONTEXT_COMPACTION_RATIO,
    CHROMA_COLLECTION_SHORT_TERM, CHROMA_COLLECTION_LONG_TERM,
    ARCHIVIST_MODEL_LITELLM, ARCHIVIST_SMART_MODEL_LITELLM,
    ARCHIVIST_SMART_AFTER_HOUR, ARCHIVIST_SMART_IDLE_SECS,
    LOGS_DIR,
)

# --- Configuration ---
TOKEN_ENCODING_MODEL = "cl100k_base"
COMPACTION_THRESHOLD_PERCENT = CONTEXT_COMPACTION_RATIO
ARCHIVIST_MODEL = ARCHIVIST_MODEL_LITELLM
WRITEBACK_TIMING_LOG = Path(LOGS_DIR) / "jane_writeback_timing.log"

# Initialize the tokenizer
try:
    encoding = tiktoken.get_encoding(TOKEN_ENCODING_MODEL)
except Exception:
    encoding = tiktoken.encoding_for_model("gpt-4")


def get_token_count(text: str) -> int:
    """Calculates the number of tokens in a given string."""
    return len(encoding.encode(text))


def _append_writeback_log(line: str) -> None:
    try:
        WRITEBACK_TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
        with WRITEBACK_TIMING_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except Exception:
        pass


class ConversationManager:
    """
    Manages the active conversation history, SQLite ledger, and tiered memory.

    Archival triggers:
      1. Idle: fires after IDLE_TIMEOUT_SECONDS of no new messages AND there is
         new content in short-term DB since the last archival run.
      2. Session end (close()): final archival pass, then full cleanup of the
         session's temporary short-term ChromaDB directory.

    Context window compaction (75% threshold) is separate: it only manages the
    in-memory conversation_history by replacing old turns with a summary.
    It does NOT drive the archival schedule.
    """

    def __init__(self, session_id: str, max_tokens: int = 8192,
                 idle_timeout: int = IDLE_TIMEOUT_SECONDS):
        self.session_id = session_id
        self.max_tokens = max_tokens
        self.compaction_threshold = int(self.max_tokens * COMPACTION_THRESHOLD_PERCENT)
        self.idle_timeout = idle_timeout
        self.conversation_history = []

        self._db_lock = threading.Lock()
        self._archival_lock = threading.Lock()
        self._idle_timer = None
        self._session_closed = False
        self._last_activity_ts = time.time()

        # 1. Initialize SQLite Ledger
        os.makedirs(VAULT_PATH, exist_ok=True)
        try:
            self.db_conn = sqlite3.connect(LEDGER_DB_PATH, check_same_thread=False)
            self._init_db()
        except Exception as e:
            logger.warning("Failed to initialize SQLite ledger: %s", e)
            self.db_conn = None

        # 2. Initialize short-term memory (shared persistent ChromaDB, 14-day TTL)
        os.makedirs(SHORT_TERM_MEMORY_PATH, exist_ok=True)
        with silence_stderr_fd():
            self.short_term_db_client = chromadb.PersistentClient(path=SHORT_TERM_MEMORY_PATH)
            self.short_term_collection = self.short_term_db_client.get_or_create_collection(
                name=CHROMA_COLLECTION_SHORT_TERM,
                embedding_function=embedding_functions.DefaultEmbeddingFunction()
            )

        # 3. Initialize long-term memory (persistent ChromaDB)
        os.makedirs(LONG_TERM_MEMORY_PATH, exist_ok=True)
        with silence_stderr_fd():
            self.long_term_db_client = chromadb.PersistentClient(path=LONG_TERM_MEMORY_PATH)
            self.long_term_collection = self.long_term_db_client.get_or_create_collection(
                name=CHROMA_COLLECTION_LONG_TERM,
                embedding_function=embedding_functions.DefaultEmbeddingFunction()
            )

        logger.info("ConversationManager for session '%s' initialized.", self.session_id)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    # Hard cap on conversation_history entries — prevents unbounded growth if
    # LLM-based compaction repeatedly fails (e.g. Ollama is down).
    _MAX_HISTORY_ENTRIES = 200

    def add_message(self, message: dict, latency_ms: float = 0):
        """
        Adds a message to the in-memory history, logs to SQLite ledger,
        archives to short-term DB, resets the idle timer, and compacts the
        context window if needed.
        """
        self.conversation_history.append(message)
        # Hard-cap: drop oldest entries if compaction is not keeping up
        if len(self.conversation_history) > self._MAX_HISTORY_ENTRIES:
            excess = len(self.conversation_history) - self._MAX_HISTORY_ENTRIES
            self.conversation_history = self.conversation_history[excess:]
        self._log_to_ledger(message, latency_ms)

        # Archive every message to short-term DB immediately so the idle
        # archivist always has the full raw session content to review.
        if message.get('content'):
            self._write_to_short_term([message])

        # Reset idle timer — archival fires when user goes quiet long enough.
        self._last_activity_ts = time.time()
        self._reset_idle_timer()

        # Compact the in-memory context window if it is getting full.
        return self._compact_context_window_if_needed()

    def add_messages(self, messages: list[dict], latency_ms: float = 0):
        """Batch variant used when a user/assistant turn pair is available together."""
        pending = [msg for msg in messages if msg]
        if not pending:
            return None
        for message in pending:
            self.conversation_history.append(message)
            self._log_to_ledger(message, latency_ms)

        contentful = [msg for msg in pending if msg.get("content")]
        if contentful:
            self._write_to_short_term(contentful)

        self._last_activity_ts = time.time()
        self._reset_idle_timer()
        return self._compact_context_window_if_needed()

    def get_stats(self) -> dict:
        """Returns token statistics plus the current short-term memory count."""
        current_tokens = get_token_count(
            " ".join([msg.get('content', '') for msg in self.conversation_history])
        )
        return {
            "current_tokens": current_tokens,
            "threshold": self.compaction_threshold,
            "max_tokens": self.max_tokens,
            "usage_percent": round((current_tokens / self.max_tokens) * 100, 2),
            "short_term_count": self.short_term_collection.count() if self.short_term_collection else 0,
        }

    def close(self):
        """
        Ends the session:
          1. Cancels any pending idle timer.
          2. Runs a final archival pass on remaining short-term memories.
          3. Deletes the session's temporary short-term ChromaDB directory.
          4. Closes the SQLite ledger connection.
        """
        if self._session_closed:
            return
        self._session_closed = True

        logger.info("Session '%s' ending. Running final archival...", self.session_id)

        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

        # Final archival pass
        self._run_archival(idle_seconds=max(0.0, time.time() - self._last_activity_ts))

        # Release client handles (do NOT delete — short-term DB is shared and persistent)
        self._release_short_term_handles()

        # Close SQLite
        if self.db_conn:
            try:
                self.db_conn.close()
            except Exception as e:
                logger.warning(f"Error closing database: {e}")
            self.db_conn = None

        logger.info("Session '%s' closed and cleaned up.", self.session_id)

    # -------------------------------------------------------------------------
    # Idle timer
    # -------------------------------------------------------------------------

    def _reset_idle_timer(self, delay_seconds: float | None = None):
        """Cancels any existing idle timer and starts a fresh one."""
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        delay = self.idle_timeout if delay_seconds is None else max(1.0, delay_seconds)
        self._idle_timer = threading.Timer(delay, self._on_idle)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _on_idle(self):
        """Callback fired after idle_timeout seconds of user inactivity."""
        if self._session_closed:
            return
        count = self.short_term_collection.count() if self.short_term_collection else 0
        idle_seconds = max(0.0, time.time() - self._last_activity_ts)
        if count > 0:
            if self._should_wait_for_smart_archival(idle_seconds):
                remaining = ARCHIVIST_SMART_IDLE_SECS - idle_seconds
                logger.info(
                    "Idle detected — deferring archival for smarter model in %ds.",
                    int(max(1, remaining)),
                )
                self._reset_idle_timer(remaining)
                return
            logger.info(
                "Idle detected — %d short-term memories pending archival after %ds idle.",
                count, int(idle_seconds),
            )
            self._run_archival(idle_seconds=idle_seconds)
        else:
            logger.info("Idle detected — no new short-term memories to archive.")

    # -------------------------------------------------------------------------
    # Archival: short-term → long-term
    # -------------------------------------------------------------------------

    def _run_archival(self, idle_seconds: float = 0.0):
        """
        Retrieves unprocessed entries for this session from the shared short-term DB,
        triages each one using Qwen:
          - Keep       → promote to long-term, delete from short-term
          - Short-term → stamp with expires_at TTL in-place (stays in short-term)
          - Discard    → delete from short-term
          - Retry      → leave untouched in short-term for a later archival pass
        Skips entries that already have expires_at set (already triaged).
        """
        with self._archival_lock:
            if not self.short_term_collection:
                return

            try:
                all_items = self.short_term_collection.get(
                    where={"session_id": self.session_id},
                    include=["documents", "metadatas"]
                )
            except Exception:
                all_items = self.short_term_collection.get(include=["documents", "metadatas"])

            if not all_items or not all_items.get('documents'):
                return

            # Only triage entries not yet stamped with a TTL
            untriaged = [
                (id_, doc, meta or {})
                for id_, doc, meta in zip(all_items['ids'], all_items['documents'], all_items['metadatas'])
                if not (meta or {}).get('expires_at')
            ]

            if not untriaged:
                return

            logger.info("Archiving %d short-term entries...", len(untriaged))
            promoted = kept_short = discarded = retried = 0
            ids_to_delete = []
            archivist_model = self._select_archivist_model(idle_seconds)

            for id_, doc, meta in untriaged:
                verdict = self._triage_memory(doc, archivist_model)
                if verdict == "Keep":
                    self._promote_to_long_term(doc)
                    ids_to_delete.append(id_)
                    promoted += 1
                elif verdict == "Forgettable":
                    # Mark with TTL in-place — entry stays in short-term until janitor purges it
                    now = datetime.datetime.utcnow()
                    expires_at = (now + datetime.timedelta(days=SHORT_TERM_TTL_DAYS)).isoformat()
                    updated_meta = {**meta, "expires_at": expires_at, "memory_type": "short_term"}
                    self.short_term_collection.update(ids=[id_], metadatas=[updated_meta])
                    kept_short += 1
                elif verdict == "Retry":
                    retried += 1
                else:  # Discard
                    ids_to_delete.append(id_)
                    discarded += 1

            if ids_to_delete:
                self.short_term_collection.delete(ids=ids_to_delete)
            logger.info("Archival done: %d promoted, %d short-term (TTL), %d discarded, %d deferred for retry.",
                        promoted, kept_short, discarded, retried)

    def _should_wait_for_smart_archival(self, idle_seconds: float) -> bool:
        now = datetime.datetime.now()
        return now.hour >= ARCHIVIST_SMART_AFTER_HOUR and idle_seconds < ARCHIVIST_SMART_IDLE_SECS

    def _select_archivist_model(self, idle_seconds: float) -> str:
        now = datetime.datetime.now()
        if now.hour >= ARCHIVIST_SMART_AFTER_HOUR and idle_seconds >= ARCHIVIST_SMART_IDLE_SECS:
            return ARCHIVIST_SMART_MODEL_LITELLM
        return ARCHIVIST_MODEL

    def _triage_memory(self, memory_content: str, model_name: str) -> str:
        """
        Asks Qwen (The Archivist) whether a memory is worth keeping long-term.
        Returns 'Keep', 'Forgettable', 'Discard', or 'Retry'.

        - Keep: permanent-ish facts (decisions, preferences, architecture, goals, root causes),
          plus hard-won debugging or implementation knowledge: problems that took meaningful effort
          to solve, the fix that worked, and lessons learned worth reusing later
        - Forgettable: recent-but-temporary context (recent changes made, bugs just fixed,
          progress in current work, solutions discovered this session) unless it captures a
          difficult problem/solution pattern worth preserving long-term — expires after TTL
        - Discard: noise, chitchat, redundant repetition
        - Retry: model failure/timeout path; leave untouched so it can be re-triaged later
        """
        prompt = (
            "You are The Archivist. Respond with ONLY one word: 'Keep', 'Forgettable', or 'Discard'.\n\n"
            "Rules:\n"
            "- Keep: long-term value — decisions, user preferences, architecture changes, project goals, "
            "permanent facts, root cause conclusions, critical resource locations, and hard-won "
            "problem-solving knowledge. If the memory captures a problem that took real effort/time "
            "to solve, the fix that worked, or lessons learned that would help solve similar problems "
            "again, classify it as Keep.\n"
            "- Forgettable: recent but temporary — code changes just made, bugs just fixed, "
            "problems solved this session, solutions discovered, current work-in-progress state, "
            "recent test results. Valuable now, not needed in a week. Do NOT use Forgettable for "
            "difficult debugging stories or durable solution patterns that should be remembered.\n"
            "- Discard: noise, greetings, filler, redundant repetition of already-known facts.\n\n"
            f"Memory: {memory_content}"
        )
        try:
            from agent_skills.claude_cli_llm import completion
            decision = completion(prompt, max_tokens=5, timeout=30)
            return decision if decision in ["Keep", "Forgettable", "Discard"] else "Retry"
        except Exception as e:
            logger.warning("Triage failed: %s", e)
            return "Retry"

    def _promote_to_long_term(self, content: str):
        """Writes a single memory entry to the long-term ChromaDB collection."""
        try:
            self.long_term_collection.add(
                documents=[content],
                metadatas=[{
                    "source": "conversation_archivist",
                    "session_id": self.session_id,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                }],
                ids=[str(uuid.uuid4())]
            )
        except Exception as e:
            logger.warning("Failed to promote memory to long-term: %s", e)


    # -------------------------------------------------------------------------
    # Context window compaction (in-memory only, no archival trigger)
    # -------------------------------------------------------------------------

    def _compact_context_window_if_needed(self):
        """
        Replaces the oldest portion of in-memory conversation_history with a
        Qwen-generated summary when the 75% token threshold is exceeded.
        This only manages the context window — archival to long-term is handled
        separately by the idle timer and close().
        """
        stats = self.get_stats()
        if stats["current_tokens"] <= self.compaction_threshold:
            return None

        logger.info("Context window at %d tokens. Compacting...", stats['current_tokens'])

        tokens_to_remove = (stats["current_tokens"] - self.compaction_threshold
                            + int(self.max_tokens * 0.25))
        split_index = 0
        tokens_so_far = 0
        for i, message in enumerate(self.conversation_history):
            tokens_so_far += get_token_count(message.get('content', ''))
            if tokens_so_far >= tokens_to_remove:
                split_index = i + 1
                break

        if split_index >= len(self.conversation_history) - 1:
            split_index = len(self.conversation_history) - 2
        if split_index <= 0:
            return None

        part_to_summarize = self.conversation_history[:split_index]
        remaining_part = self.conversation_history[split_index:]

        archive_content = " ".join([msg.get('content', '') for msg in part_to_summarize])
        summary = self._generate_summary(archive_content)

        if not summary or summary == "Summary generation failed.":
            return None

        summary_message = {
            "role": "system",
            "content": f"<Archived Conversation Summary>: {summary}"
        }
        self.conversation_history = [summary_message] + remaining_part
        return summary_message["content"]

    def _generate_summary(self, content: str) -> str:
        try:
            response = litellm.completion(
                model=ARCHIVIST_MODEL,
                messages=[
                    {"role": "system", "content": "Summarize key facts and decisions from this conversation excerpt. Neutral, 3rd person."},
                    {"role": "user", "content": content}
                ],
                stream=False,
                timeout=60,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning("Error generating summary: %s", e)
            return "Summary generation failed."

    # -------------------------------------------------------------------------
    # SQLite ledger
    # -------------------------------------------------------------------------

    def _init_db(self):
        cursor = self.db_conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                role TEXT,
                content TEXT,
                tokens INTEGER,
                latency_ms REAL
            )
        """)
        self.db_conn.commit()

    def _log_to_ledger(self, message: dict, latency_ms: float):
        if not self.db_conn:
            return
        try:
            role = message.get("role", "unknown")
            content = (message.get("content", "")
                       if isinstance(message.get("content"), str)
                       else str(message.get("content", "")))
            tokens = get_token_count(content)
            with self._db_lock:
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "INSERT INTO turns (session_id, role, content, tokens, latency_ms) VALUES (?, ?, ?, ?, ?)",
                    (self.session_id, role, content, tokens, latency_ms)
                )
                self.db_conn.commit()
        except Exception as e:
            logger.warning("Failed to log turn to ledger: %s", e)

    # -------------------------------------------------------------------------
    # Short-term DB helpers
    # -------------------------------------------------------------------------

    def _write_to_short_term(self, messages: list):
        """Appends compact per-turn summaries to the shared short-term ChromaDB collection."""
        writeback_start = time.perf_counter()
        prepared = []
        for msg in messages:
            content = msg.get("content")
            if not content:
                continue
            if not self._should_store_short_term_turn(msg.get("role", "unknown"), content):
                _append_writeback_log(
                    f"session={self.session_id} stage=turn_skip role={msg.get('role','unknown')}"
                    f" reason=low_value raw_chars={len(content)} raw_tokens={get_token_count(content)}"
                )
                continue
            summarize_start = time.perf_counter()
            summarized, summary_style = self._summarize_for_short_term(
                role=msg.get("role", "unknown"),
                content=content,
            )
            summarize_ms = int((time.perf_counter() - summarize_start) * 1000)
            raw_chars = len(msg.get("content", ""))
            raw_tokens = get_token_count(msg.get("content", ""))
            summary_chars = len(summarized or "")
            summary_tokens = get_token_count(summarized or "") if summarized else 0
            _append_writeback_log(
                f"session={self.session_id} stage=turn_summarize role={msg.get('role','unknown')}"
                f" duration_ms={summarize_ms} raw_chars={raw_chars} raw_tokens={raw_tokens}"
                f" summary_chars={summary_chars} summary_tokens={summary_tokens}"
                f" summary_style={summary_style}"
            )
            prepared.append((msg, summarized, summary_style))

        if not prepared:
            return

        chroma_start = time.perf_counter()
        self.short_term_collection.add(
            documents=[doc for _, doc, _ in prepared],
            metadatas=[{
                "role": msg.get("role", "unknown"),
                "session_id": self.session_id,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "raw_chars": len(msg.get("content", "")),
                "summary_chars": len(doc),
                "summary_style": summary_style,
            } for msg, doc, summary_style in prepared],
            ids=[str(uuid.uuid4()) for _ in prepared]
        )
        chroma_ms = int((time.perf_counter() - chroma_start) * 1000)
        total_ms = int((time.perf_counter() - writeback_start) * 1000)
        _append_writeback_log(
            f"session={self.session_id} stage=writeback_total duration_ms={total_ms}"
            f" chroma_add_ms={chroma_ms} turns={len(prepared)}"
        )

    @staticmethod
    def _should_store_short_term_turn(role: str, content: str) -> bool:
        text = re.sub(r"\s+", " ", str(content or "")).strip().lower()
        if not text:
            return False
        # --- exact low-value tokens ---
        low_value_exact = {
            "ok", "okay", "yes", "yeah", "yep", "no", "nope", "thanks", "thank you",
            "got it", "sounds good", "cool", "nice", "done", "send", "sent",
            "/new", "none",
        }
        if text in low_value_exact:
            return False
        # --- short ambiguous questions ---
        if role == "user" and len(text) <= 12 and text.endswith("?") and text in {"why?", "how?", "which?", "where?", "when?"}:
            return False
        # --- signal/test strings (all-caps markers, test pings) ---
        _upper = text.upper()
        if _upper == text and len(text) < 40 and re.match(r"^[A-Z_]+$", text.replace(" ", "")):
            return False  # e.g. FINAL_MEMORY_OK, MEMORY_SYSTEM_OK, JANE_WEB_RECOVERED
        # --- greeting/filler patterns (user) ---
        if role == "user":
            _greeting_pats = [
                r"^hey\s*(jane)?\s*[,!.]?\s*(how.s it going|are you|you there|testing|can you say)?\s*[?!.]?\s*$",
                r"^(hi|hello|yo)\s*(jane)?\s*[!.]?\s*$",
                r"^you (working|there) now\??$",
                r"^(hey )?jane did you crash\??$",
                r"^let.s (run this test|see how long|test this)",
                r"^can you respond to this message so i can test",
                r"^what is \d+\+\d+\??\s*$",
            ]
            for pat in _greeting_pats:
                if re.search(pat, text):
                    return False
        # --- assistant filler (no recall value) ---
        if role == "assistant":
            _filler_pats = [
                r"^hey chieh[!.,]?\s*(i.m here|going well|what.s up|what do you)",
                r"^(i.m here|here)\.\s*what do you",
                r"^jane here\.\s*(what|i.ll)",
                r"^doing well\.?\s*(in the workspace|ready)",
                r"^fresh start\.?\s*what.s up",
                r"^yeah\.?\s*what do you need",
                r"^when you what\?",
            ]
            for pat in _filler_pats:
                if re.search(pat, text):
                    return False
        return True

    def _release_short_term_handles(self):
        """Releases ChromaDB client handles. Does NOT delete — short-term DB is shared/persistent."""
        try:
            self.short_term_collection = None
            self.short_term_db_client = None
        except Exception:
            pass

    @staticmethod
    def _looks_like_code_edit(content: str) -> bool:
        text = str(content or "")
        markers = [
            "```",
            "*** Begin Patch",
            "*** Update File:",
            "*** Add File:",
            "*** Delete File:",
            "diff --git",
            "@@",
            "+def ",
            "-def ",
            "+import ",
            "-import ",
            "Syntax check passed",
            "File changed:",
            os.path.expanduser("~/"),
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".md",
        ]
        return any(marker in text for marker in markers)

    @staticmethod
    def _summarize_for_short_term(role: str, content: str) -> tuple[str, str]:
        """
        Compresses a turn into the shortest retrieval-friendly memory note.
        Raw text is still preserved in the SQLite ledger; Chroma gets the compact form.
        """
        clean = re.sub(r"\s+", " ", str(content or "")).strip()
        if not clean:
            return "", "concise_turn_memory_v1"

        summary_style = "concise_turn_memory_v1"
        if role == "assistant" and ConversationManager._looks_like_code_edit(content):
            summary_style = "code_change_turn_memory_v1"
            prompt = (
                "Summarize this assistant turn as a compact code-change memory note for later retrieval.\n"
                "Rules:\n"
                "- Do NOT restate the full diff or prose explanation.\n"
                "- Extract only: files changed, core behavior change, key functions/classes, and any open risk or next step.\n"
                "- Prefer 2 to 4 very short bullets in plain text.\n"
                "- Start each bullet with '- '.\n"
                "- Keep file paths when they matter.\n"
                "- Omit filler, acknowledgements, and formatting chatter.\n"
                "- If no durable code-change context exists, return exactly: No durable context.\n\n"
                f"Role: {role}\n"
                f"Turn: {clean}"
            )
        else:
            if len(clean) <= 150:
                return clean[:150], "rule_based_turn_memory_v1"
            prompt = (
                "Compress this single conversation turn into the shortest and most concise memory note "
                "that will maximally help later context retrieval.\n"
                "Rules:\n"
                "- Keep only concrete facts, decisions, requests, constraints, file paths, errors, or open loops.\n"
                "- Remove filler, politeness, repetition, style words, and nonessential explanation.\n"
                "- Prefer one compact sentence or two very short bullets in plain text.\n"
                "- Do not add analysis or speculation.\n"
                "- If the turn contains no durable or useful context, return exactly: No durable context.\n\n"
                f"Role: {role}\n"
                f"Turn: {clean}"
            )

        try:
            response = litellm.completion(
                model=LOCAL_LLM_MODEL_LITELLM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0,
                stream=False,
                api_base=LOCAL_LLM_BASE_URL,
                timeout=30,
            )
            summarized = response.choices[0].message.content.strip()
        except Exception:
            summarized = ""

        if not summarized:
            fallback = clean[:280]
            return fallback, summary_style

        summarized = ConversationManager._normalize_short_term_summary(
            summarized,
            preserve_bullets=(summary_style == "code_change_turn_memory_v1"),
        )
        if summarized == "No durable context.":
            return summarized, summary_style
        return summarized[:320], summary_style

    @staticmethod
    def _normalize_short_term_summary(text: str, preserve_bullets: bool) -> str:
        text = str(text or "").strip()
        if not text:
            return ""
        if not preserve_bullets:
            return re.sub(r"\s+", " ", text).strip()

        lines = []
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            if re.match(r"^[-*]\s+", line):
                line = "- " + line[2:].strip()
            elif re.match(r"^\d+\.\s+", line):
                line = "- " + re.sub(r"^\d+\.\s+", "", line).strip()
            lines.append(line)

        if not lines:
            return ""
        if len(lines) > 1:
            lines = [line for line in lines if line != "No durable context." and line != "- No durable context."]
        if not lines:
            return "No durable context."
        if len(lines) == 1 and lines[0] != "No durable context.":
            return f"- {re.sub(r'^[-*]\s+', '', lines[0]).strip()}"
        return "\n".join(lines)
