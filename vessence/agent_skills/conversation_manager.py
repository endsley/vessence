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
    get_chroma_client,
    LOCAL_LLM_MODEL_LITELLM, OLLAMA_BASE_URL as LOCAL_LLM_BASE_URL,
    VAULT_DIR as VAULT_PATH,
    VECTOR_DB_LONG_TERM  as LONG_TERM_MEMORY_PATH,
    VECTOR_DB_SHORT_TERM as SHORT_TERM_MEMORY_PATH,
    LEDGER_DB_PATH, IDLE_TIMEOUT_SECS as IDLE_TIMEOUT_SECONDS,
    SHORT_TERM_TTL_DAYS, SHORT_TERM_MAX_THEMES, CONTEXT_COMPACTION_RATIO,
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
        self._thematic_lock = threading.Lock()
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
            self.short_term_db_client = get_chroma_client(path=SHORT_TERM_MEMORY_PATH)
            self.short_term_collection = self.short_term_db_client.get_or_create_collection(
                name=CHROMA_COLLECTION_SHORT_TERM,
                embedding_function=embedding_functions.DefaultEmbeddingFunction()
            )

        # 3. Initialize long-term memory (persistent ChromaDB)
        os.makedirs(LONG_TERM_MEMORY_PATH, exist_ok=True)
        with silence_stderr_fd():
            self.long_term_db_client = get_chroma_client(path=LONG_TERM_MEMORY_PATH)
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
        resets the idle timer, and compacts the context window if needed.
        Short-term thematic memory is updated via update_thematic_memory()
        called from the persistence worker in jane_proxy.py.
        """
        self.conversation_history.append(message)
        # Hard-cap: drop oldest entries if compaction is not keeping up
        if len(self.conversation_history) > self._MAX_HISTORY_ENTRIES:
            excess = len(self.conversation_history) - self._MAX_HISTORY_ENTRIES
            self.conversation_history = self.conversation_history[excess:]
        self._log_to_ledger(message, latency_ms)

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

    def _fetch_session_transcript(self) -> str:
        """Retrieves the full raw transcript for this session from the SQLite ledger."""
        if not self.db_conn:
            return ""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT role, content FROM turns WHERE session_id = ? ORDER BY timestamp ASC",
                (self.session_id,)
            )
            rows = cursor.fetchall()
            lines = []
            for role, content in rows:
                if content:
                    lines.append(f"{role.upper()}: {content}")
            return "\n\n".join(lines)
        except Exception as e:
            logger.warning("Failed to fetch session transcript: %s", e)
            return ""

    def _thematic_archival(self):
        """
        Synthesizes the entire session into high-value thematic arcs using the Agent tier.
        Stores them in long-term knowledge with 'Sweet 16' category metadata.
        """
        transcript = self._fetch_session_transcript()
        if not transcript or len(transcript) < 200:
            return

        prompt = (
            "You are The Thematic Archivist. Analyze the following session transcript. "
            "Identify the 'Arcs of Lasting Value'—the meaningful developments that should be remembered "
            "long-term. Ignore greetings, noise, and transient state.\n\n"
            "Categories to search for (The Sweet 16):\n"
            "1. Identity Evolution (User preferences, family, life events)\n"
            "2. Architectural Milestones (System design changes, new components)\n"
            "3. Project State (Ground truth of active projects)\n"
            "4. Debugging Wisdom (Root causes, fix patterns, why things failed)\n"
            "5. Collaborative Habits (Communication style, preferred workflows)\n"
            "6. Resource Mapping (Key files, URLs, entities, people)\n"
            "7. Tech Stack Fingerprint (Specific library versions, environment quirks)\n"
            "8. Risk & Mitigation (Safety rules, dangerous command handling)\n"
            "9. User Eureka Moments (Shifts in logic, breakthroughs)\n"
            "10. Future Speculations (Discussed but unimplemented ideas)\n"
            "11. Aesthetic Preferences (UI/UX tastes, font sizes, colors)\n"
            "12. Cross-Agent Coordination (Division of labor between Jane and Amber)\n"
            "13. File Anchors (Direct paths to important code or data)\n"
            "14. Don't Search List (Known noise paths or irrelevant directories)\n"
            "15. Symbolic Shorthand (Frequent constants, Lexicon items)\n"
            "16. Proven Command Snippets (Bash commands that worked perfectly)\n\n"
            "Output each Arc as a JSON object within a list. Each object must have:\n"
            "- 'theme': A concise title\n"
            "- 'category': One of the 16 categories above\n"
            "- 'content': A clear, comprehensive summary including context and outcomes.\n\n"
            "Format: [ { \"theme\": \"...\", \"category\": \"...\", \"content\": \"...\" }, ... ]\n\n"
            f"Transcript:\n{transcript}"
        )

        try:
            from agent_skills.claude_cli_llm import completion_json
            arcs = completion_json(prompt, tier="agent")
            for arc in arcs:
                theme = arc.get("theme", "Unnamed Theme")
                category = arc.get("category", "General")
                content = arc.get("content", "")
                if content:
                    full_memory = f"Theme: {theme}\nCategory: {category}\n\n{content}"
                    self._promote_to_long_term(full_memory, category=category)
            logger.info("Thematic archival complete: %d arcs stored.", len(arcs))
        except Exception as e:
            logger.warning("Thematic archival failed: %s", e)

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
        Retrieves unprocessed entries for this session from the shared short-term DB.
        - If session is closed: Runs thematic synthesis (Holistic session summary).
        - If idle: Runs turn-by-turn triage (Fast incremental archival).
        """
        with self._archival_lock:
            # 1. Holistic Thematic Archival (Runs only when session is ending)
            if self._session_closed:
                logger.info("Session closed. Starting holistic thematic archival...")
                self._thematic_archival()

            # 2. Cleanup Short-term (Mark with TTL or discard)
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

            logger.info("Cleaning up %d short-term entries...", len(untriaged))
            promoted = kept_short = discarded = retried = 0
            ids_to_delete = []
            archivist_model = self._select_archivist_model(idle_seconds)

            for id_, doc, meta in untriaged:
                # If session is closed, we've already done thematic archival,
                # so we just mark everything as Forgettable (TTL) or Discard (noise).
                # We don't promote raw turns to long-term anymore; themes handle that.
                verdict = self._triage_memory(doc, archivist_model)
                
                # Special rule: raw turns never go to long-term if thematic is active
                # but we keep them in short-term for 14 days if they aren't noise.
                if verdict == "Keep" or verdict == "Forgettable":
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
            logger.info("Short-term cleanup done: %d kept (TTL), %d discarded, %d deferred.",
                        kept_short, discarded, retried)

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
        """
        # --- Noise Pre-Filter (Saves LLM tokens and prevents low-signal archive) ---
        text = str(memory_content or "").strip()
        noise_patterns = [
            r"^User logged in with Google account.*",
            r"^System in 'Waiting for auth' state.*",
            r"^User interface ready for interaction.*",
            r"^Deprecation warning for --allowed-tools.*",
            r"^Automatic Gemini CLI update.*",
            r"^Gemini CLI update available.*",
            r"^What does Jane web streaming mean\?.*",
            r"^User interface includes YOLO shortcut.*",
            r"^No relevant context found.*",
            r"^jane you still thinking\?.*",
            r"^jane/.*"
        ]
        for pat in noise_patterns:
            if re.search(pat, text, re.IGNORECASE):
                return "Discard"

        prompt = (
            "You are The Archivist. Respond with ONLY one word: 'Keep', 'Forgettable', or 'Discard'.\n\n"
            "Rules:\n"
            "- Keep: permanent-ish facts — user-specific details (family, profession, preferences), "
            "architecture changes, project goals, fixed root causes, and hard-won implementation "
            "knowledge. If it's something the user explicitly wants me to remember, classify it as Keep.\n"
            "- Forgettable: temporary context — current session progress, recent code changes, "
            "bugs just fixed, test results. These will expire after 14 days.\n"
            "- Discard: noise, greetings, trivial state updates (e.g., 'system ready', 'login successful'), "
            "filler, and redundant repetition of things I already know.\n\n"
            "BE RUTHLESS. When in doubt, Discard or Forgettable. Only Keep durable, high-value knowledge.\n\n"
            f"Memory: {memory_content}"
        )
        try:
            from agent_skills.claude_cli_llm import completion
            decision = completion(prompt, max_tokens=5, timeout=30)
            return decision if decision in ["Keep", "Forgettable", "Discard"] else "Retry"
        except Exception as e:
            logger.warning("Triage failed: %s", e)
            return "Retry"

    def _promote_to_long_term(self, content: str, category: str = "General"):
        """
        Writes a single memory entry to the long-term ChromaDB collection.
        Uses Sonnet to decide if the new memory should be merged into an existing
        entry or added as a new one.
        """
        try:
            # 1. Fetch top 2 nearest neighbors in this category
            existing = self.long_term_collection.query(
                query_texts=[content],
                n_results=2,
                where={"topic": category},
                include=["documents", "metadatas"]
            )
            
            best_match_id = None
            if existing and existing['documents'] and existing['documents'][0]:
                matches = []
                for i in range(len(existing['documents'][0])):
                    matches.append({
                        "id": existing['ids'][0][i],
                        "doc": existing['documents'][0][i],
                        "dist": existing['distances'][0][i]
                    })
                
                # 2. Ask Sonnet if we should merge
                prompt = (
                    "You are a Memory Architect. I want to add a new memory arc to the long-term knowledge base.\n\n"
                    f"New Memory Category: {category}\n"
                    f"New Memory Content: {content}\n\n"
                    "Here are the most similar existing memories in this category:\n"
                )
                for i, m in enumerate(matches):
                    prompt += f"Match {i+1} (ID: {m['id']}, Distance: {m['dist']:.4f}):\n{m['doc']}\n\n"
                
                prompt += (
                    "Decision Criteria:\n"
                    "- MERGE: If the new memory is a continuation, update, or near-duplicate of an existing one. "
                    "Provide a single comprehensive summary that includes ALL unique details from both.\n"
                    "- NEW: If the new memory represents a distinct event, different architectural component, or unrelated fact.\n\n"
                    "Respond ONLY with a JSON object:\n"
                    "{ \"decision\": \"MERGE\" | \"NEW\", \"target_id\": \"id_to_overwrite\", \"merged_content\": \"new_summary_if_merge\" }"
                )

                from agent_skills.claude_cli_llm import completion_json
                result = completion_json(prompt, tier="agent")
                
                if result.get("decision") == "MERGE" and result.get("target_id") and result.get("merged_content"):
                    best_match_id = result["target_id"]
                    new_doc = result["merged_content"]
                    logger.info("Intelligent MERGE: Integrating new memory into ID: %s", best_match_id)
                    self.long_term_collection.update(
                        ids=[best_match_id],
                        documents=[new_doc],
                        metadatas=[{
                            "source": "conversation_archivist",
                            "session_id": self.session_id,
                            "topic": category,
                            "timestamp": datetime.datetime.utcnow().isoformat(),
                            "status": "updated_thematic"
                        }]
                    )
                    return

            # 3. If NEW or no matches found, add as a fresh entry
            self.long_term_collection.add(
                documents=[content],
                metadatas=[{
                    "source": "conversation_archivist",
                    "session_id": self.session_id,
                    "topic": category,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                }],
                ids=[str(uuid.uuid4())]
            )
        except Exception as e:
            logger.warning("Promotion failed: %s", e)



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

    # ─── Thematic short-term memory ────────────────────────────────────────
    # Instead of storing one entry per turn, we maintain up to 20 thematic
    # memory slots that get updated in place as the conversation evolves.
    # Uses Sonnet (via claude_cli_llm.completion_agent) for high-quality
    # theme classification and summary updates.

    def update_thematic_memory(self, user_msg: str, assistant_msg: str) -> None:
        """Classify the turn into a theme and update/create the theme slot.

        Called from the persistence worker thread. Acquires _thematic_lock
        to serialize updates for this session.
        """
        if not user_msg and not assistant_msg:
            return
        if not self.short_term_collection:
            return

        with self._thematic_lock:
            start = time.perf_counter()
            try:
                self._do_thematic_update(user_msg, assistant_msg)
            except Exception as exc:
                logger.exception(
                    "Thematic memory update failed for session %s: %s",
                    self.session_id[:12], exc,
                )
                self._fallback_raw_theme(user_msg, assistant_msg)
            finally:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                _append_writeback_log(
                    f"session={self.session_id} stage=thematic_update "
                    f"duration_ms={elapsed_ms}"
                )

    def _do_thematic_update(self, user_msg: str, assistant_msg: str) -> None:
        """Fetch themes, classify turn, update or create theme."""
        from agent_skills.claude_cli_llm import completion_agent

        themes = self._fetch_session_themes()
        turn_text = f"User: {user_msg}\nJane: {assistant_msg}"
        now_iso = datetime.datetime.utcnow().isoformat()
        expires_iso = (
            datetime.datetime.utcnow()
            + datetime.timedelta(days=SHORT_TERM_TTL_DAYS)
        ).isoformat()

        classification = self._classify_turn_theme(themes, turn_text)

        if classification["action"] == "existing":
            theme = themes[classification["theme_index"]]
            updated_summary = self._update_theme_summary(
                theme["document"], turn_text
            )
            self.short_term_collection.update(
                ids=[theme["id"]],
                documents=[updated_summary],
                metadatas=[{
                    **theme["metadata"],
                    "turn_count": theme["metadata"].get("turn_count", 1) + 1,
                    "last_updated_at": now_iso,
                    "expires_at": expires_iso,
                }],
            )
            _append_writeback_log(
                f"session={self.session_id} stage=theme_update "
                f"theme_index={classification['theme_index']} "
                f"title={theme['metadata'].get('theme_title', '?')}"
            )
        else:
            new_title = classification["title"]
            new_summary = self._update_theme_summary("", turn_text)

            if len(themes) < SHORT_TERM_MAX_THEMES:
                new_index = len(themes)
                new_id = f"session_{self.session_id}_theme_{new_index}"
                self.short_term_collection.add(
                    ids=[new_id],
                    documents=[new_summary],
                    metadatas=[{
                        "session_id": self.session_id,
                        "theme_title": new_title,
                        "theme_index": new_index,
                        "turn_count": 1,
                        "first_turn_at": now_iso,
                        "last_updated_at": now_iso,
                        "memory_type": "short_term_theme",
                        "expires_at": expires_iso,
                    }],
                )
                _append_writeback_log(
                    f"session={self.session_id} stage=theme_create "
                    f"theme_index={new_index} title={new_title}"
                )
            else:
                oldest = min(
                    themes,
                    key=lambda t: t["metadata"].get("last_updated_at", ""),
                )
                self.short_term_collection.update(
                    ids=[oldest["id"]],
                    documents=[new_summary],
                    metadatas=[{
                        "session_id": self.session_id,
                        "theme_title": new_title,
                        "theme_index": oldest["metadata"]["theme_index"],
                        "turn_count": 1,
                        "first_turn_at": now_iso,
                        "last_updated_at": now_iso,
                        "memory_type": "short_term_theme",
                        "expires_at": expires_iso,
                    }],
                )
                _append_writeback_log(
                    f"session={self.session_id} stage=theme_evict_and_create "
                    f"evicted={oldest['metadata'].get('theme_title', '?')} "
                    f"new_title={new_title}"
                )

    def _fetch_session_themes(self) -> list[dict]:
        """Return all short_term_theme entries for this session, sorted by index."""
        try:
            results = self.short_term_collection.get(
                where={
                    "$and": [
                        {"session_id": {"$eq": self.session_id}},
                        {"memory_type": {"$eq": "short_term_theme"}},
                    ]
                },
                include=["documents", "metadatas"],
            )
        except Exception:
            # Fallback: ChromaDB version may not support compound where
            results = self.short_term_collection.get(
                where={"session_id": {"$eq": self.session_id}},
                include=["documents", "metadatas"],
            )
            # Post-filter for theme entries
            filtered = {"ids": [], "documents": [], "metadatas": []}
            for i, meta in enumerate(results.get("metadatas", [])):
                if (meta or {}).get("memory_type") == "short_term_theme":
                    filtered["ids"].append(results["ids"][i])
                    filtered["documents"].append(results["documents"][i])
                    filtered["metadatas"].append(meta)
            results = filtered

        themes = []
        for i, doc_id in enumerate(results.get("ids", [])):
            themes.append({
                "id": doc_id,
                "document": results["documents"][i],
                "metadata": results["metadatas"][i] or {},
            })
        themes.sort(key=lambda t: t["metadata"].get("theme_index", 0))
        return themes

    def _classify_turn_theme(self, themes: list[dict], turn_text: str) -> dict:
        """Ask Sonnet whether this turn belongs to an existing theme or is new.

        Returns {"action": "existing", "theme_index": int}
             or {"action": "new", "title": str}
        """
        from agent_skills.claude_cli_llm import completion_agent

        if not themes:
            try:
                title = completion_agent(
                    f"Give a short (3-8 word) theme title for this conversation turn. "
                    f"Return ONLY the title, nothing else.\n\n{turn_text[:500]}",
                    max_tokens=30, timeout=30,
                ).strip().strip('"').strip("'")
            except Exception:
                title = turn_text[:50].replace("\n", " ").strip()
            return {"action": "new", "title": title or "General discussion"}

        theme_list = "\n".join(
            f'{i}. "{t["metadata"].get("theme_title", "Untitled")}" — '
            f'{t["document"][:100]}'
            for i, t in enumerate(themes)
        )
        prompt = (
            f"Given these existing conversation themes:\n{theme_list}\n\n"
            f"New turn:\n{turn_text[:800]}\n\n"
            f"Does this turn add detail to an existing theme, or introduce a "
            f"genuinely new topic?\n"
            f"Prefer matching existing themes — only say NEW if this is "
            f"clearly a different subject.\n\n"
            f"Respond with EXACTLY one of:\n"
            f"- EXISTING: <number>\n"
            f"- NEW: <short theme title, 3-8 words>\n"
            f"No other text."
        )
        try:
            response = completion_agent(prompt, max_tokens=50, timeout=45).strip()
            if response.upper().startswith("EXISTING:"):
                idx = int(response.split(":", 1)[1].strip())
                if 0 <= idx < len(themes):
                    return {"action": "existing", "theme_index": idx}
                return {"action": "existing", "theme_index": len(themes) - 1}
            elif response.upper().startswith("NEW:"):
                title = response.split(":", 1)[1].strip().strip('"').strip("'")
                return {"action": "new", "title": title or "General discussion"}
            else:
                logger.warning("Unparseable theme classification: %s", response[:100])
                return {"action": "existing", "theme_index": len(themes) - 1}
        except Exception as exc:
            logger.warning("Theme classification LLM failed: %s", exc)
            return {"action": "existing", "theme_index": len(themes) - 1}

    def _update_theme_summary(self, current_summary: str, turn_text: str) -> str:
        """Ask Sonnet to incorporate the new turn into the theme summary.

        Returns the updated summary text (max ~600 chars).
        """
        from agent_skills.claude_cli_llm import completion_agent

        if current_summary:
            prompt = (
                f"Here is the current summary for a conversation theme:\n"
                f"---\n{current_summary}\n---\n\n"
                f"Incorporate the key details from this new turn. "
                f"Keep it concise (3-6 sentences). Preserve all important facts, "
                f"decisions, file paths, errors, and open items. Drop filler.\n\n"
                f"New turn:\n{turn_text[:800]}\n\n"
                f"Return ONLY the updated summary."
            )
        else:
            prompt = (
                f"Summarize this conversation turn into a concise memory note "
                f"(2-4 sentences). Keep concrete facts, decisions, file paths, "
                f"errors, and open items. Drop filler.\n\n"
                f"{turn_text[:800]}\n\n"
                f"Return ONLY the summary."
            )
        try:
            summary = completion_agent(prompt, max_tokens=300, timeout=45)
            return summary.strip()[:600]
        except Exception as exc:
            logger.warning("Theme summary LLM failed: %s", exc)
            combined = (current_summary + "\n" + turn_text).strip()
            return combined[:500]

    def _fallback_raw_theme(self, user_msg: str, assistant_msg: str) -> None:
        """Store raw text in the most recent theme slot when LLM fails."""
        if not self.short_term_collection:
            return
        themes = self._fetch_session_themes()
        now_iso = datetime.datetime.utcnow().isoformat()
        expires_iso = (
            datetime.datetime.utcnow()
            + datetime.timedelta(days=SHORT_TERM_TTL_DAYS)
        ).isoformat()
        raw_text = f"User: {(user_msg or '')[:200]}\nJane: {(assistant_msg or '')[:200]}"

        if themes:
            most_recent = max(
                themes,
                key=lambda t: t["metadata"].get("last_updated_at", ""),
            )
            updated = (most_recent["document"] + "\n" + raw_text)[:600]
            self.short_term_collection.update(
                ids=[most_recent["id"]],
                documents=[updated],
                metadatas=[{
                    **most_recent["metadata"],
                    "turn_count": most_recent["metadata"].get("turn_count", 1) + 1,
                    "last_updated_at": now_iso,
                    "expires_at": expires_iso,
                }],
            )
        else:
            new_id = f"session_{self.session_id}_theme_0"
            self.short_term_collection.add(
                ids=[new_id],
                documents=[raw_text],
                metadatas=[{
                    "session_id": self.session_id,
                    "theme_title": "General discussion",
                    "theme_index": 0,
                    "turn_count": 1,
                    "first_turn_at": now_iso,
                    "last_updated_at": now_iso,
                    "memory_type": "short_term_theme",
                    "expires_at": expires_iso,
                }],
            )

    # ─── Legacy short-term helpers (kept for backward compat during migration) ──

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
