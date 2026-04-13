"""Jane proxy with shared context/memory and pluggable CLI brain adapters."""
import asyncio
import contextlib
import json
import logging
import os
import threading
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from memory.v1.conversation_manager import ConversationManager
from memory.v1.memory_retrieval import build_memory_sections, invalidate_memory_summary_cache
from llm_brain.v1.brain_adapters import BrainAdapterError, ExecutionProfile, build_execution_profile, get_brain_adapter, resolve_timeout_seconds
from context_builder.v1.context_builder import build_jane_context_async
from jane.config import ENV_FILE_PATH, LOGS_DIR
from llm_brain.v1.persistent_gemini import get_gemini_persistent_manager
from jane.session_summary import format_session_summary, load_session_summary, update_session_summary_async
from jane_web.broadcast import StreamBroadcaster

logger = logging.getLogger("jane.proxy")

# ── Jane Phone Tools: marker extraction ──────────────────────────────────────
#
# Jane's mind emits `[[CLIENT_TOOL:<name>:<json>]]` markers inline in her
# streaming response to invoke client-side (Android) tools. This extractor
# pulls them out of the delta stream, emits structured `client_tool_call`
# SSE events, and strips the markers from the user-visible text.
#
# Implementation notes (per design spec §R1):
#   - Streaming-safe: handles markers split across delta chunks by holding
#     back any trailing text that could be a partial opener.
#   - JSON-aware: the payload is a JSON object, so we count braces and track
#     string-escape state to find the correct close; we do NOT search for `]]`
#     naively because JSON strings may contain `]]`.
#   - Code-fence aware: tracks triple-backtick state across chunks and skips
#     marker scanning inside fenced code blocks to prevent prompt injection
#     and avoid mis-triggering on prose examples.
#   - Fail-open: on malformed tool name, invalid JSON, or buffer overflow
#     (more than _MAX_HOLD bytes buffered between opener and close), the
#     held text is flushed as visible and the marker is dropped. Safer to
#     reveal the raw text than to execute an unvalidated tool call.

import re as _re
import uuid as _uuid


class ToolMarkerExtractor:
    """Streaming extractor for ``[[CLIENT_TOOL:name:json]]`` markers.

    Create one per request. Feed delta chunks in via :meth:`feed`; receive
    (sanitized_text, list_of_tool_calls). Call :meth:`flush` at stream end
    to reveal any residual buffered text.
    """

    _OPEN = "[[CLIENT_TOOL:"
    _CLOSE = "]]"
    _MAX_HOLD = 4096  # bail out if we're mid-marker for more than this
    _FENCE = "```"
    _TOOL_NAME_RE = _re.compile(r"^[a-z][a-z0-9_.]*$")

    def __init__(self) -> None:
        self._buffer: str = ""          # unflushed tail (may contain partial marker)
        self._in_fence: bool = False    # inside a ``` ... ``` code block

    # ── public API ──────────────────────────────────────────────────────────
    def feed(self, chunk: str) -> tuple[str, list[dict]]:
        """Consume a delta chunk, return (safe_visible_text, tool_calls)."""
        if not chunk:
            return "", []
        self._buffer += chunk
        if len(self._buffer) > self._MAX_HOLD * 2:
            # Runaway: flush and reset to avoid unbounded memory growth.
            visible = self._buffer
            self._buffer = ""
            return visible, []
        return self._drain()

    def flush(self) -> tuple[str, list[dict]]:
        """Called on stream end. Reveal any residual buffered text as visible.

        If a marker was opened but never closed, the partial marker becomes
        visible text (fail-open) — users see raw `[[CLIENT_TOOL:...` which is
        a clear signal something went wrong server-side, not a silent miss.
        """
        visible, calls = self._drain(final=True)
        tail = self._buffer
        self._buffer = ""
        return visible + tail, calls

    # ── internals ───────────────────────────────────────────────────────────
    def _drain(self, final: bool = False) -> tuple[str, list[dict]]:
        """Extract complete markers from ``self._buffer``.

        Updates ``self._buffer`` in place (removing consumed text) and returns
        the safe-to-forward prefix plus any complete tool calls. When not
        ``final``, holds back any trailing chars that could be a partial
        opener or an unclosed marker.
        """
        out_visible_parts: list[str] = []
        out_calls: list[dict] = []

        while True:
            if self._in_fence:
                # Inside a code fence — forward everything up to the next ``` (which closes it).
                close_idx = self._buffer.find(self._FENCE)
                if close_idx < 0:
                    # Still inside; flush all but a possible partial fence tail.
                    hold = self._partial_fence_suffix_len(self._buffer)
                    if hold > 0:
                        out_visible_parts.append(self._buffer[:-hold])
                        self._buffer = self._buffer[-hold:]
                    else:
                        out_visible_parts.append(self._buffer)
                        self._buffer = ""
                    break
                end = close_idx + len(self._FENCE)
                out_visible_parts.append(self._buffer[:end])
                self._buffer = self._buffer[end:]
                self._in_fence = False
                continue  # re-scan for more

            # Not in fence — look for either an opener or a fence.
            opener_idx = self._buffer.find(self._OPEN)
            fence_idx = self._buffer.find(self._FENCE)

            # Decide which comes first (if any).
            next_opener = opener_idx if opener_idx >= 0 else len(self._buffer) + 1
            next_fence = fence_idx if fence_idx >= 0 else len(self._buffer) + 1

            if next_opener >= len(self._buffer) and next_fence >= len(self._buffer):
                # Neither present in the buffer.
                # Still hold back any suffix that could be the start of an opener OR a fence.
                hold = max(
                    self._partial_opener_suffix_len(self._buffer),
                    self._partial_fence_suffix_len(self._buffer),
                )
                if hold > 0:
                    out_visible_parts.append(self._buffer[:-hold])
                    self._buffer = self._buffer[-hold:]
                else:
                    out_visible_parts.append(self._buffer)
                    self._buffer = ""
                break

            if next_fence < next_opener:
                # A fence comes first — forward text up to and including the fence, enter fence state.
                end = next_fence + len(self._FENCE)
                out_visible_parts.append(self._buffer[:end])
                self._buffer = self._buffer[end:]
                self._in_fence = True
                continue

            # An opener comes first (or they tied — opener wins).
            # Flush anything before the opener.
            if next_opener > 0:
                out_visible_parts.append(self._buffer[:next_opener])
                self._buffer = self._buffer[next_opener:]
            # Now self._buffer starts with "[[CLIENT_TOOL:". Try to find the close.
            close_end = self._find_marker_end(self._buffer)
            if close_end is None:
                # Incomplete marker. If we're at stream end, fail-open (flush as visible).
                if final or len(self._buffer) > self._MAX_HOLD:
                    out_visible_parts.append(self._buffer)
                    self._buffer = ""
                # else: hold entire buffer until next chunk arrives
                break
            # We have a complete marker from 0 to close_end.
            marker_text = self._buffer[:close_end]
            parsed = self._parse_marker(marker_text)
            if parsed is not None:
                out_calls.append(parsed)
            else:
                # Malformed — fail-open, reveal as visible text.
                out_visible_parts.append(marker_text)
            self._buffer = self._buffer[close_end:]
            # Loop to look for more markers in the remainder.

        return "".join(out_visible_parts), out_calls

    @staticmethod
    def _partial_opener_suffix_len(buf: str) -> int:
        """Length of the longest suffix of buf that is a proper prefix of _OPEN."""
        open_tok = ToolMarkerExtractor._OPEN
        max_check = min(len(buf), len(open_tok) - 1)
        for i in range(max_check, 0, -1):
            if buf.endswith(open_tok[:i]):
                return i
        return 0

    @staticmethod
    def _partial_fence_suffix_len(buf: str) -> int:
        """Length of longest suffix of buf that is a proper prefix of ```."""
        fence = ToolMarkerExtractor._FENCE
        max_check = min(len(buf), len(fence) - 1)
        for i in range(max_check, 0, -1):
            if buf.endswith(fence[:i]):
                return i
        return 0

    @classmethod
    def _find_marker_end(cls, buf: str) -> int | None:
        """Given a buffer starting with ``[[CLIENT_TOOL:``, find the byte index
        where the matching ``]]`` ends (exclusive). Returns None if the marker
        is not yet complete.

        Parses name (up to first `:` after opener), then scans the JSON object
        with brace/string-escape tracking, then requires the literal ``]]``.

        Hard cap: if we scan past _MAX_HOLD characters without finding the
        closing ``]]``, return a pseudo-complete position so the caller
        fail-opens the marker. Prevents a runaway model (or injected giant
        JSON payload) from forcing the extractor into an unbounded single
        marker scan.
        """
        assert buf.startswith(cls._OPEN)
        if len(buf) > cls._MAX_HOLD:
            # Overflow — try to find a nearby ']]' and fail-open the whole
            # span as visible text. If we can't find one, consume everything
            # up to _MAX_HOLD and fail-open.
            close = buf.find(cls._CLOSE, len(cls._OPEN))
            if 0 < close < cls._MAX_HOLD:
                return close + len(cls._CLOSE)
            return cls._MAX_HOLD  # fail-open visible
        i = len(cls._OPEN)
        # Scan the tool name until the next ':'
        name_start = i
        while i < len(buf) and buf[i] != ":":
            i += 1
        if i >= len(buf):
            return None  # name not yet terminated
        if i == name_start:
            # Empty name — malformed. Return a "pseudo-complete" position so the
            # caller can fail-open the marker by parsing (which will also fail).
            # Find the next ]] so we consume it all.
            close = buf.find(cls._CLOSE, i)
            return close + len(cls._CLOSE) if close >= 0 else None
        i += 1  # skip the ':'
        # Now at the start of the JSON object. Scan with brace + string state.
        if i >= len(buf):
            return None
        if buf[i] != "{":
            # JSON must start with an object per the spec. Malformed — fail-open.
            close = buf.find(cls._CLOSE, i)
            return close + len(cls._CLOSE) if close >= 0 else None
        depth = 0
        in_str = False
        escape = False
        json_end: int | None = None
        while i < len(buf):
            ch = buf[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break
            i += 1
        if json_end is None:
            return None  # JSON not yet complete
        # Expect ']]' immediately after the JSON.
        if buf.startswith(cls._CLOSE, json_end):
            return json_end + len(cls._CLOSE)
        # Tolerate a few whitespace chars between '}' and ']]'
        j = json_end
        while j < len(buf) and buf[j] in " \t\r\n":
            j += 1
        if j >= len(buf):
            return None
        if buf.startswith(cls._CLOSE, j):
            return j + len(cls._CLOSE)
        # Any other char → malformed. Find the next ]] and fail-open the whole span.
        close = buf.find(cls._CLOSE, j)
        return close + len(cls._CLOSE) if close >= 0 else None

    @classmethod
    def _parse_marker(cls, marker_text: str) -> dict | None:
        """Parse ``[[CLIENT_TOOL:name:{json}]]`` into {tool, args, call_id}.
        Returns None on malformed input (caller fails-open).
        """
        if not marker_text.startswith(cls._OPEN) or not marker_text.endswith(cls._CLOSE):
            return None
        inner = marker_text[len(cls._OPEN):-len(cls._CLOSE)].rstrip()
        colon = inner.find(":")
        if colon < 0:
            return None
        name = inner[:colon].strip()
        if not cls._TOOL_NAME_RE.match(name):
            return None
        json_str = inner[colon + 1:].strip()
        try:
            args = json.loads(json_str)
        except Exception:
            return None
        if not isinstance(args, dict):
            return None
        return {
            "tool": name,
            "args": args,
            "call_id": str(_uuid.uuid4()),
        }


# SMS draft open detection moved to tools/phone/server/__init__.py — see
# jane.tool_loader.should_skip_initial_ack(). This used to be duplicated here
# as a transitional fallback; now the tool loader is the single source of
# truth and the fallback path has been removed so the two cannot drift.


# ── Jane Phone Tools: TOOL_RESULT feedback channel ───────────────────────────
#
# Android prepends [TOOL_RESULT:{json}] markers to the next user message when
# a tool completes/fails/is cancelled. We strip those off before showing the
# user bubble, but pass the parsed results to Jane's mind in her context so
# she knows what actually happened on the phone.

class _SkipRouterSignal(Exception):
    """Silent sentinel raised to skip the Gemma router without logging a
    warning — used when an SMS draft is open and we must route the turn
    straight to Jane's mind.
    """


_TOOL_RESULT_OPEN = "[TOOL_RESULT:"
_TOOL_RESULT_CLOSE = "]"


def _extract_tool_results(user_message: str) -> tuple[str, list[dict]]:
    """Strip leading [TOOL_RESULT:{json}] markers from a user message.

    Uses brace-counting + string-escape tracking (same technique as
    ToolMarkerExtractor) instead of a non-greedy regex, so nested JSON
    objects and string values containing ``}]`` are parsed correctly.

    Returns (clean_message, list_of_parsed_results). Any malformed marker
    stops the scan; the remaining text (with the bad marker intact) is
    returned as the cleaned message so the user sees the raw failure
    rather than a silent drop.
    """
    results: list[dict] = []
    cleaned = user_message
    while True:
        # Skip leading whitespace between markers.
        stripped = cleaned.lstrip()
        if not stripped.startswith(_TOOL_RESULT_OPEN):
            break
        # Position of the '{' inside the marker.
        json_start = len(cleaned) - len(stripped) + len(_TOOL_RESULT_OPEN)
        # Skip optional whitespace after the "[TOOL_RESULT:" prefix.
        while json_start < len(cleaned) and cleaned[json_start] in " \t":
            json_start += 1
        if json_start >= len(cleaned) or cleaned[json_start] != "{":
            break
        # Brace-count scan to find the matching closing '}'.
        depth = 0
        in_str = False
        escape = False
        i = json_start
        json_end: int | None = None
        while i < len(cleaned):
            ch = cleaned[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break
            i += 1
        if json_end is None:
            break  # incomplete JSON — leave marker in place
        # Expect ']' immediately after the JSON (allow whitespace between).
        j = json_end
        while j < len(cleaned) and cleaned[j] in " \t":
            j += 1
        if j >= len(cleaned) or cleaned[j] != _TOOL_RESULT_CLOSE:
            break
        try:
            payload = json.loads(cleaned[json_start:json_end])
        except Exception:
            break
        if not isinstance(payload, dict):
            break
        results.append(payload)
        # Consume the marker and any trailing whitespace.
        cleaned = cleaned[j + 1:].lstrip()
    return cleaned, results


_DELIM_OPEN = (
    "[PHONE TOOL RESULTS — results from tools that ran on the Android client since the last turn. "
    "Use these as background context, but ALWAYS prioritize the user's current message below. "
    "If the user has moved on to a new topic, respond to THEIR message first — "
    "do not fixate on stale tool results. Only mention tool results if they are "
    "directly relevant to what the user is asking NOW.]"
)
_DELIM_CLOSE = "[END PHONE TOOL RESULTS]"


def _neutralize_delimiters(s: str) -> str:
    """Defuse any substring that could be mistaken for the tool-result block
    delimiter by an attacker-supplied message body or tool payload.

    Strategy: replace newlines in the untrusted string with literal ``\\n``
    escape sequences (so the tool result block stays single-line per entry
    and can't inject newlines of its own) and replace the literal delimiter
    strings with a zero-width-marked variant that cannot be mistaken for the
    real delimiter by a downstream regex.
    """
    if not isinstance(s, str):
        return str(s)
    # Collapse newlines so tool content can't inject block boundaries.
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    # Neutralize anything that looks like our delimiter markers.
    s = s.replace("[PHONE TOOL RESULTS", "[phone_tool_results")
    s = s.replace("[END PHONE TOOL RESULTS", "[end_phone_tool_results")
    # Cap length to prevent absurd strings blowing up the context.
    if len(s) > 2000:
        s = s[:2000] + "…(truncated)"
    return s


def _format_tool_results_for_brain(results: list[dict]) -> str:
    """Format a list of parsed tool results as a context block that will be
    prepended to the user message the standing brain sees.

    All untrusted string fields (message, tool name, data values) are run
    through ``_neutralize_delimiters`` before interpolation so that a
    compromised tool payload or a malicious SMS body cannot forge the block
    boundary and inject fake high-priority context into Jane's mind.
    """
    if not results:
        return ""
    lines = [_DELIM_OPEN]
    for r in results:
        tool = _neutralize_delimiters(r.get("tool", "?"))
        status = _neutralize_delimiters(r.get("status", "?"))
        message = _neutralize_delimiters(r.get("message", ""))
        lines.append(f"- tool={tool} status={status} message={message!r}")
        data = r.get("data")
        if isinstance(data, dict) and data:
            try:
                # Serialize to compact JSON, then neutralize the resulting
                # string. This preserves data structure for Jane while
                # defending against delimiter injection inside JSON string
                # values (e.g., a message body that contains the literal
                # "[END PHONE TOOL RESULTS]" text).
                json_str = _neutralize_delimiters(
                    json.dumps(data, ensure_ascii=True)
                )
                lines.append(f"  data={json_str}")
            except Exception:
                pass
        extra = r.get("extra")
        if isinstance(extra, dict) and extra:
            try:
                lines.append(
                    f"  extra={_neutralize_delimiters(json.dumps(extra, ensure_ascii=True))}"
                )
            except Exception:
                pass
    lines.append(_DELIM_CLOSE)
    return "\n".join(lines)


def _execute_email_tool_serverside(tc: dict) -> str:
    """Execute an email.* tool call server-side and return a human-readable
    result string. Called from the emit() function when the brain emits
    [[CLIENT_TOOL:email.*:...]] markers — these are intercepted before reaching
    the Android client because email is a server-side capability (Gmail API).

    Returns a short status string (or empty string on failure) that gets
    appended to the visible delta stream.
    """
    tool = tc.get("tool", "")
    args = tc.get("args", {})
    try:
        if tool == "email.read_inbox":
            from agent_skills.email_tools import read_inbox
            limit = args.get("limit", 10)
            query = args.get("query", "is:unread")
            emails = read_inbox(limit=limit, query=query)
            if not emails:
                return "\n\nNo unread emails found."
            lines = [f"\n\nFound {len(emails)} email(s):\n"]
            for e in emails:
                status = "NEW" if e.get("is_unread") else "read"
                lines.append(f"- [{status}] From: {e['sender']} — {e['subject']}")
                if e.get("snippet"):
                    lines.append(f"  Preview: {e['snippet'][:150]}")
            return "\n".join(lines)
        elif tool == "email.read":
            from agent_skills.email_tools import read_email
            msg_id = args.get("message_id", "")
            if not msg_id:
                return "\n\nError: no message_id provided."
            email_data = read_email(msg_id)
            body = (email_data.get("body") or "")[:2000]
            return (
                f"\n\nEmail from {email_data.get('sender', '?')}:\n"
                f"Subject: {email_data.get('subject', '?')}\n"
                f"Date: {email_data.get('date', '?')}\n\n"
                f"{body}"
            )
        elif tool == "email.search":
            from agent_skills.email_tools import search_emails
            query = args.get("query", "")
            limit = args.get("limit", 10)
            emails = search_emails(query=query, limit=limit)
            if not emails:
                return f"\n\nNo emails found for query: {query}"
            lines = [f"\n\nSearch results ({len(emails)} emails):\n"]
            for e in emails:
                lines.append(f"- From: {e['sender']} — {e['subject']}")
            return "\n".join(lines)
        elif tool == "email.send":
            # Send requires confirmation — don't auto-execute, just note it
            return "\n\n[Email send requires user confirmation — not auto-executed]"
        elif tool == "email.delete":
            return "\n\n[Email delete requires user confirmation — not auto-executed]"
        else:
            logger.warning("Unknown email tool: %s", tool)
            return ""
    except RuntimeError as e:
        logger.warning("Email tool %s failed (no credentials): %s", tool, e)
        return f"\n\nGmail is not set up yet. Please sign in with Google on the Vessence web UI to enable email."
    except Exception as e:
        logger.error("Email tool %s failed: %s", tool, e)
        return f"\n\nEmail error: {e}"


CODE_MAP_KEYWORDS = (
    # Code navigation
    "function", "class", "file", "route", "endpoint", "handler",
    "module", "script", "config", "dockerfile",
    # Actions on code
    "refactor", "rewrite", "modify", "update", "change",
    "create", "build", "remove", "delete",
    # Debugging
    "crash", "error", "log", "timeout", "broke", "broken", "fail",
    "investigate", "trace", "inspect",
    # Vessence components
    "jane", "amber", "essence", "vault", "proxy", "brain",
    "librarian", "archivist", "session", "context",
    # Infrastructure
    "docker", "install", "hook", "startup",
    # Auto-evolved from daily conversations
    "web",
    # Auto-evolved from daily conversations
    "text",
    "believe",
    "mode",
    "speech",
    # Auto-evolved from daily conversations
    "guide",
    "user",
    "gemini",
    "claude",
    "system",
    "tools",
    # Auto-evolved from daily conversations
    "google",
    # Auto-evolved from daily conversations
    "switch",
    "msg",
    "switching",
    "switched",
    "openai",
    # Auto-evolved from daily conversations
    "stop",
    "accent",
    # Auto-evolved from daily conversations
    "briefing",
    "send",
    "daily",
    "news",
    "article",
    "server",
    "vessence",
    "don",
    "link",
    "chrome",
    # Auto-evolved from daily conversations
    "message",
    "wife",
    "love",
    "version",
    # Auto-evolved from daily conversations
    "currently",
    "gemma",
    "xtps",
    "single",
    "using",
    "warmed",
    "initial",
    "sync",
    "push",
    "button",
    # Auto-evolved from daily conversations
    "play",
    # Auto-evolved from daily conversations
    "stars",
    "full",
    "sky",
    "check",
    # Auto-evolved from daily conversations
    "online",
    # Auto-evolved from daily conversations
    "skill",
    "stage",
)


def _maybe_prepend_code_map(message: str) -> tuple[str, bool]:
    """Disabled — the brain has tools (Grep/Read) to find symbols on demand,
    which costs fewer tokens than pre-loading the full 12K-token index.
    Returns (message, False) unconditionally."""
    return message, False


@dataclass
class JaneSessionState:
    history: list[dict] = field(default_factory=list)
    conv_manager: ConversationManager | None = None
    bootstrap_memory_summary: str = ""
    bootstrap_complete: bool = False
    bootstrap_in_progress: bool = False
    bootstrap_ready: threading.Event = field(default_factory=threading.Event)
    recent_file_context: str = ""
    last_accessed_at: float = field(default_factory=time.time)
    # Per-session semaphore to serialize concurrent requests and prevent history race conditions.
    # Without this, two requests to the same session can interleave history reads/writes,
    # causing Jane to answer the wrong question ("conversation offset" bug).
    # Semaphore(1) ensures only one stream_message runs at a time per session.
    request_gate: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(1))


_sessions: dict[str, JaneSessionState] = {}
_MAX_SESSIONS = 50  # hard cap on in-memory sessions to prevent unbounded growth
REQUEST_TIMING_LOG = Path(LOGS_DIR) / "jane_request_timing.log"
PROMPT_DUMP_LOG = Path(LOGS_DIR) / "jane_prompt_dump.jsonl"
SESSION_IDLE_TTL_SECONDS = max(int(os.environ.get("JANE_SESSION_IDLE_TTL_SECONDS", "21600")), 60)

# ── Prefetch cache ─────────────────────────────────────────────────────────────
_prefetch_cache: dict[str, dict] = {}  # {session_id: {"result": str, "timestamp": float}}
_PREFETCH_CACHE_MAX = 100  # hard cap on entries to prevent unbounded growth
PREFETCH_TTL = 60  # seconds


def run_prefetch_memory(session_id: str) -> None:
    """Query ChromaDB with a broad context query and cache the result for 60s.

    Called from the /api/jane/prefetch-memory endpoint. Runs the query in a
    background thread so the HTTP response returns immediately.
    """
    now = time.time()
    cached = _prefetch_cache.get(session_id)
    if cached and (now - cached["timestamp"]) < PREFETCH_TTL:
        logger.debug("[%s] Prefetch: still fresh, skipping", _session_log_id(session_id))
        return

    def _worker() -> None:
        start = time.perf_counter()
        try:
            import urllib.parse
            import urllib.request as _req
            import json as _json
            query = "recent context and topics"
            url = f"http://127.0.0.1:8083/query?q={urllib.parse.quote(query)}"
            with _req.urlopen(url, timeout=5) as resp:
                data = _json.loads(resp.read())
                result = data.get("result", "")
        except Exception:
            result = ""
        _prefetch_cache[session_id] = {"result": result, "timestamp": time.time()}
        # Prune expired entries to prevent unbounded growth
        if len(_prefetch_cache) > _PREFETCH_CACHE_MAX:
            now = time.time()
            expired = [k for k, v in _prefetch_cache.items() if now - v["timestamp"] > PREFETCH_TTL]
            for k in expired:
                _prefetch_cache.pop(k, None)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("[%s] Prefetch memory cached in %dms (%d chars)", _session_log_id(session_id), elapsed_ms, len(result))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def get_prefetch_result(session_id: str) -> str:
    """Return a cached prefetch memory result if it is still within TTL, else ''."""
    cached = _prefetch_cache.get(session_id)
    if cached and (time.time() - cached["timestamp"]) < PREFETCH_TTL:
        return cached.get("result", "")
    return ""


def _get_brain_name() -> str:
    env_path = Path(ENV_FILE_PATH) if ENV_FILE_PATH else None
    if env_path and env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "JANE_BRAIN":
                provider = value.strip().lower()
                if provider in {"claude", "gemini", "openai"}:
                    os.environ["JANE_BRAIN"] = provider
                    return provider
    return os.environ.get("JANE_BRAIN", "gemini").lower()


def _session_log_id(session_id: str | None) -> str:
    return session_id[:12] if session_id else "none"


def _get_timeout_seconds(brain_name: str) -> int:
    return resolve_timeout_seconds(brain_name)


def _get_execution_profile(brain_name: str | None = None) -> ExecutionProfile:
    return build_execution_profile(brain_name or _get_brain_name())


def _use_gemini_api(brain_name: str) -> bool:
    """Use Gemini API brain instead of CLI-based persistent Gemini."""
    return brain_name == "gemini" and os.environ.get("JANE_WEB_GEMINI_API", "1") != "0"

def _use_persistent_gemini(brain_name: str) -> bool:
    # Disabled by default — Gemini API brain is preferred
    return brain_name == "gemini" and os.environ.get("JANE_WEB_PERSISTENT_GEMINI", "0") == "1"


def _use_persistent_claude(brain_name: str) -> bool:
    return brain_name == "claude" and os.environ.get("JANE_WEB_PERSISTENT_CLAUDE", "1") != "0"


def _use_persistent_codex(brain_name: str) -> bool:
    return brain_name in {"openai", "codex"} and os.environ.get("JANE_WEB_PERSISTENT_CODEX", "1") != "0"


def _get_web_chat_model(brain_name: str) -> str:
    env_vars = {
        "claude": "JANE_MODEL_CLAUDE",
        "gemini": "JANE_MODEL_GEMINI",
        "openai": "JANE_MODEL_OPENAI",
        "codex": "JANE_MODEL_OPENAI",
    }
    defaults = {
        "claude": "claude-opus-4-6",
        "gemini": "gemini-2.5-pro",
        "openai": "gpt-5.4",
        "codex": "gpt-5.4",
    }
    normalized = (brain_name or "").lower()
    env_var = env_vars.get(normalized)
    if env_var:
        configured = os.environ.get(env_var, "").strip()
        if configured:
            return configured
    return defaults.get(normalized, defaults["claude"])


def _prune_stale_sessions(now: float | None = None) -> None:
    now_ts = time.time() if now is None else now
    expired_ids = [
        session_id
        for session_id, state in list(_sessions.items())
        if now_ts - state.last_accessed_at > SESSION_IDLE_TTL_SECONDS
    ]
    for session_id in expired_ids:
        logger.info(
            "[%s] Expiring idle Jane web session after %ds",
            session_id[:12],
            int(now_ts - _sessions[session_id].last_accessed_at),
        )
        end_session(session_id)


async def _execute_brain_sync(session_id: str, brain_name: str, adapter, request_ctx) -> str:
    if _use_gemini_api(brain_name):
        from llm_brain.v1.gemini_api_brain import get_gemini_api_brain
        brain = get_gemini_api_brain()
        return await brain.send_streaming(
            session_id=session_id,
            system_prompt=request_ctx.system_prompt,
            message=request_ctx.transcript,
            model=os.environ.get("GEMINI_MODEL", "gemini-2.5-pro"),
        )
    if _use_persistent_gemini(brain_name):
        manager = get_gemini_persistent_manager("/tmp")
        worker = await manager.get(session_id)
        prompt_text = f"{request_ctx.system_prompt}\n\n{request_ctx.transcript}".strip()
        return await worker.run_turn(
            prompt_text,
            timeout_seconds=_get_execution_profile(brain_name).timeout_seconds,
        )
    if _use_persistent_claude(brain_name):
        from llm_brain.v1.persistent_claude import get_claude_persistent_manager
        manager = get_claude_persistent_manager()
        profile = _get_execution_profile(brain_name)
        # First turn sends full context; subsequent turns only send the new message
        session = await manager.get(session_id)
        if session.is_fresh():
            prompt_text = f"{request_ctx.system_prompt}\n\n{request_ctx.transcript}".strip()
        elif not request_ctx.system_prompt:
            # Skip-context path: safety transcript (session summary + recent
            # history) is already baked into request_ctx.transcript — send it
            # whole so the brain sees conversation context after rotation.
            prompt_text = request_ctx.transcript
        else:
            # Only send the latest user message — Claude remembers the rest
            prompt_text = request_ctx.transcript.split("User:")[-1].strip().removesuffix("Jane:").strip()
            # Inject code map on-demand for code-related follow-up messages
            prompt_text, _cm = _maybe_prepend_code_map(prompt_text)
            if _cm:
                logger.info("[%s] Code map injected (persistent claude sync)", session_id[:12] if 'session_id' in dir() else "?")
        return await manager.run_turn(
            session_id,
            prompt_text,
            timeout_seconds=profile.timeout_seconds,
            model=_get_web_chat_model(brain_name),
            yolo=profile.mode == "yolo",
        )
    if _use_persistent_codex(brain_name):
        from llm_brain.v1.persistent_codex import get_codex_persistent_manager
        manager = get_codex_persistent_manager()
        profile = _get_execution_profile(brain_name)
        session = await manager.get(session_id)
        if session.is_fresh():
            prompt_text = f"{request_ctx.system_prompt}\n\n{request_ctx.transcript}".strip()
        elif not request_ctx.system_prompt:
            prompt_text = request_ctx.transcript
        else:
            prompt_text = request_ctx.transcript.split("User:")[-1].strip().removesuffix("Jane:").strip()
            prompt_text, _cm = _maybe_prepend_code_map(prompt_text)
            if _cm:
                logger.info("[%s] Code map injected (persistent codex sync)", session_id[:12])
        return await manager.run_turn(
            session_id,
            prompt_text,
            timeout_seconds=profile.timeout_seconds,
            model=_get_web_chat_model(brain_name),
            yolo=profile.mode == "yolo",
        )
    return await asyncio.to_thread(adapter.execute, request_ctx.system_prompt, request_ctx.transcript)


async def _execute_brain_stream(session_id: str, brain_name: str, adapter, request_ctx, emit) -> str:
    if _use_gemini_api(brain_name):
        from llm_brain.v1.gemini_api_brain import get_gemini_api_brain
        brain = get_gemini_api_brain()
        return await brain.send_streaming(
            session_id=session_id,
            system_prompt=request_ctx.system_prompt,
            message=request_ctx.transcript,
            on_delta=lambda d: emit("delta", d),
            on_status=lambda s: emit("status", s),
            on_tool_use=lambda n, a: emit("tool_use", f"🔧 {n}: {a[:100]}"),
            model=os.environ.get("GEMINI_MODEL", "gemini-2.5-pro"),
        )
    if _use_persistent_gemini(brain_name):
        manager = get_gemini_persistent_manager("/tmp")
        worker = await manager.get(session_id)
        prompt_text = f"{request_ctx.system_prompt}\n\n{request_ctx.transcript}".strip()
        return await worker.run_turn(
            prompt_text,
            on_delta=lambda delta: emit("delta", delta),
            timeout_seconds=_get_execution_profile(brain_name).timeout_seconds,
        )
    if _use_persistent_claude(brain_name):
        from llm_brain.v1.persistent_claude import get_claude_persistent_manager
        manager = get_claude_persistent_manager()
        profile = _get_execution_profile(brain_name)
        session = await manager.get(session_id)
        if session.is_fresh():
            prompt_text = f"{request_ctx.system_prompt}\n\n{request_ctx.transcript}".strip()
        elif not request_ctx.system_prompt:
            # Skip-context path: safety transcript already contains session
            # summary + recent history — send whole so brain keeps context.
            prompt_text = request_ctx.transcript
        else:
            prompt_text = request_ctx.transcript.split("User:")[-1].strip().removesuffix("Jane:").strip()
            # Inject code map on-demand for code-related follow-up messages
            prompt_text, _cm = _maybe_prepend_code_map(prompt_text)
            if _cm:
                emit("status", "Loading code map for code-related query...")
                logger.info("[%s] Code map injected (persistent claude stream)", session_id[:12])
        return await manager.run_turn(
            session_id,
            prompt_text,
            on_delta=lambda delta: emit("delta", delta),
            on_status=lambda status: emit("status", status),
            timeout_seconds=profile.timeout_seconds,
            model=_get_web_chat_model(brain_name),
            yolo=profile.mode == "yolo",
        )
    if _use_persistent_codex(brain_name):
        from llm_brain.v1.persistent_codex import get_codex_persistent_manager
        manager = get_codex_persistent_manager()
        profile = _get_execution_profile(brain_name)
        session = await manager.get(session_id)
        if session.is_fresh():
            prompt_text = f"{request_ctx.system_prompt}\n\n{request_ctx.transcript}".strip()
        elif not request_ctx.system_prompt:
            prompt_text = request_ctx.transcript
        else:
            prompt_text = request_ctx.transcript.split("User:")[-1].strip().removesuffix("Jane:").strip()
            prompt_text, _cm = _maybe_prepend_code_map(prompt_text)
            if _cm:
                emit("status", "Loading code map for code-related query...")
                logger.info("[%s] Code map injected (persistent codex stream)", session_id[:12])
        return await manager.run_turn(
            session_id,
            prompt_text,
            on_delta=lambda delta: emit("delta", delta),
            on_status=lambda status: emit("status", status),
            on_thought=lambda thought: emit("thought", thought),
            on_tool_use=lambda tool: emit("tool_use", tool),
            on_tool_result=lambda result: emit("tool_result", result),
            timeout_seconds=profile.timeout_seconds,
            model=_get_web_chat_model(brain_name),
            yolo=profile.mode == "yolo",
        )
    return await asyncio.to_thread(
        adapter.execute_stream,
        request_ctx.system_prompt,
        request_ctx.transcript,
        lambda delta: emit("delta", delta),
    )


def _get_session(session_id: str) -> JaneSessionState:
    _prune_stale_sessions()
    state = _sessions.get(session_id)
    if state is None:
        # Evict oldest session if at capacity
        if len(_sessions) >= _MAX_SESSIONS:
            oldest_id = min(_sessions, key=lambda sid: _sessions[sid].last_accessed_at)
            logger.info("[%s] Evicting oldest session to stay under %d cap", oldest_id[:12], _MAX_SESSIONS)
            end_session(oldest_id)
        state = JaneSessionState(conv_manager=ConversationManager(session_id))
        _sessions[session_id] = state
        logger.info("[%s] Created in-memory Jane session state (total=%d)", _session_log_id(session_id), len(_sessions))
    elif state.conv_manager is None:
        state.conv_manager = ConversationManager(session_id)
        logger.info("[%s] Recreated ConversationManager for existing session state", _session_log_id(session_id))
    state.last_accessed_at = time.time()
    return state


_FOLLOWUP_FILE_MARKERS = (
    "delete it",
    "remove it",
    "rename it",
    "move it",
    "open it",
    "show it",
    "send it",
    "that file",
    "that image",
    "that photo",
    "that picture",
    "the image",
    "the photo",
    "the picture",
    "the file",
    "this image",
    "this photo",
    "this picture",
)


def _resolve_file_context(state: JaneSessionState, message: str, file_context: str | None) -> str | None:
    if file_context:
        state.recent_file_context = file_context
        logger.info("Resolved file context from request payload chars=%d", len(file_context or ""))
        return file_context
    lowered = (message or "").strip().lower()
    if state.recent_file_context and any(marker in lowered for marker in _FOLLOWUP_FILE_MARKERS):
        logger.info("Resolved file context from recent follow-up context chars=%d", len(state.recent_file_context or ""))
        return state.recent_file_context
    return file_context


def _message_for_persistence(message: str, file_context: str | None) -> str:
    base = (message or "").strip()
    if not file_context:
        return base
    return f"{base}\n\n{file_context}".strip()


def prewarm_session(session_id: str) -> None:
    state = _get_session(session_id)
    if state.bootstrap_complete or state.bootstrap_in_progress:
        logger.info(
            "[%s] Skipping prewarm complete=%s in_progress=%s",
            _session_log_id(session_id),
            state.bootstrap_complete,
            state.bootstrap_in_progress,
        )
        return
    logger.info("[%s] Starting session prewarm in background thread", session_id[:12])
    state.bootstrap_in_progress = True
    state.bootstrap_ready.clear()

    def _worker() -> None:
        start = time.perf_counter()
        try:
            summary_text = format_session_summary(load_session_summary(session_id))
            query = "What durable context would most help Jane respond in this session?"
            # Fast path: use memory daemon
            memory_summary = ""
            try:
                import urllib.parse, urllib.request, json as _json
                url = f"http://127.0.0.1:8083/query?q={urllib.parse.quote(query)}"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = _json.loads(resp.read())
                    memory_summary = data.get("result", "")
            except Exception:
                # Fallback to slow path (direct ChromaDB, no Ollama librarian)
                sections = build_memory_sections(query, assistant_name="Jane")
                memory_summary = "\n\n".join(sections) if sections else ""
            if memory_summary and memory_summary != "No relevant context found.":
                state.bootstrap_memory_summary = memory_summary
            state.bootstrap_complete = True
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info("[%s] Prewarm complete in %dms (summary=%d chars, memory=%d chars)",
                        session_id[:12], elapsed_ms, len(summary_text or ""), len(state.bootstrap_memory_summary or ""))
            _log_stage(
                session_id,
                "session_prewarm",
                start,
                summary_chars=len(summary_text or ""),
                bootstrap_summary_chars=len(state.bootstrap_memory_summary or ""),
            )
        except Exception:
            logger.exception("[%s] Prewarm failed", session_id[:12])
        finally:
            state.bootstrap_in_progress = False
            state.bootstrap_ready.set()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


async def _await_prewarm_if_running(session_id: str, state: JaneSessionState, timeout_seconds: float = 2.5) -> None:
    if state.bootstrap_complete or not state.bootstrap_in_progress:
        return
    logger.info(
        "[%s] Waiting up to %.1fs for in-flight prewarm bootstrap_complete=%s",
        _session_log_id(session_id),
        timeout_seconds,
        state.bootstrap_complete,
    )
    start = time.perf_counter()
    await asyncio.to_thread(state.bootstrap_ready.wait, timeout_seconds)
    _log_stage(
        session_id,
        "prewarm_wait",
        start,
        completed=state.bootstrap_complete,
        in_progress=state.bootstrap_in_progress,
    )


def end_session(session_id: str) -> None:
    state = _sessions.pop(session_id, None)
    if state and state.conv_manager:
        conv_manager = state.conv_manager
        state.conv_manager = None

        def _close_conversation_manager() -> None:
            try:
                logger.info("[%s] Background-closing Jane session state", _session_log_id(session_id))
                conv_manager.close()
                logger.info("[%s] Background session close complete", _session_log_id(session_id))
            except Exception:
                logger.exception("[%s] Failed while background-closing ConversationManager", _session_log_id(session_id))

        logger.info("[%s] Detaching ConversationManager close to background thread", _session_log_id(session_id))
        thread = threading.Thread(target=_close_conversation_manager, daemon=True)
        thread.start()
    elif state:
        logger.info("[%s] Removed Jane session state without ConversationManager", _session_log_id(session_id))

    # Clean up persistent brain sessions so next message starts fresh
    brain_name = _get_brain_name()
    if _use_gemini_api(brain_name):
        try:
            from llm_brain.v1.gemini_api_brain import get_gemini_api_brain
            get_gemini_api_brain().remove_session(session_id)
            logger.info("[%s] Removed Gemini API brain session", _session_log_id(session_id))
        except Exception:
            logger.exception("[%s] Failed to remove Gemini API brain session", _session_log_id(session_id))
    if _use_persistent_codex(brain_name):
        try:
            from llm_brain.v1.persistent_codex import get_codex_persistent_manager
            manager = get_codex_persistent_manager()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.end(session_id))
            except RuntimeError:
                def _end_codex_session():
                    try:
                        asyncio.run(asyncio.wait_for(manager.end(session_id), timeout=10))
                    except asyncio.TimeoutError:
                        logger.warning("[%s] Persistent Codex shutdown timed out", _session_log_id(session_id))
                    except Exception as exc:
                        logger.error("[%s] Error in Codex session cleanup: %s", _session_log_id(session_id), exc)
                thread = threading.Thread(target=_end_codex_session, daemon=True)
                thread.start()
            logger.info("[%s] Ended persistent Codex session", _session_log_id(session_id))
        except Exception:
            logger.exception("[%s] Failed to end persistent Codex session", _session_log_id(session_id))
    if _use_persistent_claude(brain_name):
        try:
            from llm_brain.v1.persistent_claude import get_claude_persistent_manager
            manager = get_claude_persistent_manager()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.end(session_id))
            except RuntimeError:
                # No running event loop — create one in a background thread to avoid
                # conflicts with event loops in other threads
                def _end_session():
                    try:
                        asyncio.run(asyncio.wait_for(manager.end(session_id), timeout=10))
                    except asyncio.TimeoutError:
                        logger.warning("[%s] Persistent Claude shutdown timed out, proceeding with force kill", _session_log_id(session_id))
                    except Exception as exc:
                        logger.error("[%s] Error in background session cleanup: %s", _session_log_id(session_id), exc)
                thread = threading.Thread(target=_end_session, daemon=True)
                thread.start()
            logger.info("[%s] Ended persistent Claude session", _session_log_id(session_id))
        except Exception:
            logger.exception("[%s] Failed to end persistent Claude session", _session_log_id(session_id))
    else:
        logger.info("[%s] end_session called with no active session state", _session_log_id(session_id))


def _progress_snapshot(request_ctx, summary_text: str, file_context: str | None) -> str:
    findings: list[str] = []
    if summary_text:
        findings.append("loaded prior conversation summary")
    if "## Retrieved Memory\n" in request_ctx.system_prompt:
        findings.append("found relevant memory")
    if "## Current Task State\n" in request_ctx.system_prompt:
        findings.append("loaded task state")
    if "## Research Brief\n" in request_ctx.system_prompt:
        findings.append("prepared research brief")
    if file_context:
        findings.append("attached file context")
    if not findings:
        return "Context is ready."
    return "Context is ready: " + ", ".join(findings) + "."


_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB cap for rotating log files


def _truncate_log_if_needed(log_path: Path) -> None:
    """Truncate a log file to its last 2000 lines if it exceeds _LOG_MAX_BYTES."""
    try:
        if log_path.exists() and log_path.stat().st_size > _LOG_MAX_BYTES:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            log_path.write_text("\n".join(lines[-2000:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def _log_stage(session_id: str, stage: str, start_ts: float, **extra) -> None:
    duration_ms = int((time.perf_counter() - start_ts) * 1000)
    details = " ".join(f"{k}={v}" for k, v in extra.items())
    REQUEST_TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    _truncate_log_if_needed(REQUEST_TIMING_LOG)
    with REQUEST_TIMING_LOG.open("a", encoding="utf-8") as fh:
        fh.write(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"jane_request session={session_id} stage={stage} duration_ms={duration_ms}"
            + (f" {details}" if details else "")
            + "\n"
        )


def _log_start(session_id: str, mode: str, message: str, history_turns: int, brain_label: str, file_context: str | None) -> None:
    REQUEST_TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with REQUEST_TIMING_LOG.open("a", encoding="utf-8") as fh:
        fh.write(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"jane_request session={session_id} stage=start mode={mode}"
            f" message_chars={len(message or '')} history_turns={history_turns}"
            f" brain={brain_label} file_context={bool(file_context)}\n"
        )


def _dump_prompt(
    session_id: str,
    mode: str,
    message: str,
    summary_text: str,
    request_ctx,
    bootstrap_retrieval: bool,
    bootstrap_summary: str,
    file_context: str | None,
) -> None:
    PROMPT_DUMP_LOG.parent.mkdir(parents=True, exist_ok=True)
    _truncate_log_if_needed(PROMPT_DUMP_LOG)
    record = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": session_id,
        "mode": mode,
        "message": message,
        "message_chars": len(message or ""),
        "conversation_summary": summary_text,
        "conversation_summary_chars": len(summary_text or ""),
        "bootstrap_retrieval": bootstrap_retrieval,
        "bootstrap_memory_summary": bootstrap_summary,
        "bootstrap_memory_summary_chars": len(bootstrap_summary or ""),
        "retrieved_memory_summary": request_ctx.retrieved_memory_summary or "",
        "retrieved_memory_summary_chars": len(request_ctx.retrieved_memory_summary or ""),
        "system_prompt": request_ctx.system_prompt or "",
        "system_prompt_chars": len(request_ctx.system_prompt or ""),
        "transcript": request_ctx.transcript or "",
        "transcript_chars": len(request_ctx.transcript or ""),
        "file_context": file_context or "",
    }
    with PROMPT_DUMP_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _persist_turns_async(
    session_id: str,
    conv_manager: ConversationManager | None,
    user_turn: dict,
    assistant_turn: dict,
    user_message: str,
    assistant_message: str,
) -> None:
    def _worker() -> None:
        logger.info(
            "[%s] Persistence worker started user_chars=%d assistant_chars=%d",
            _session_log_id(session_id),
            len(user_message or ""),
            len(assistant_message or ""),
        )
        try:
            stage_start = time.perf_counter()
            if conv_manager:
                conv_manager.add_messages([user_turn, assistant_turn])
                invalidate_memory_summary_cache(session_id)
                _log_stage(session_id, "short_term_writeback_async", stage_start)
            else:
                logger.warning("[%s] No ConversationManager available for writeback", _session_log_id(session_id))
        except Exception as exc:
            logger.exception("[%s] Short-term writeback failed", session_id[:12])
            _log_stage(session_id, "short_term_writeback_async_error", stage_start, error=type(exc).__name__)

        # Thematic short-term memory update (Haiku-powered, 1-3s typical).
        # This ALSO dual-writes the Haiku-generated summary into the
        # recent_turns FIFO (see vault_web.recent_turns) so v2's ack
        # generator and classifier can fetch recent context cheaply
        # without a ChromaDB similarity search. No extra LLM calls —
        # the FIFO reuses the summary Haiku already produced for Chroma.
        try:
            stage_start = time.perf_counter()
            if conv_manager:
                conv_manager.update_thematic_memory(user_message, assistant_message)
                _log_stage(session_id, "thematic_memory_update_async", stage_start)
        except Exception as exc:
            logger.exception("[%s] Thematic memory update failed", session_id[:12])
            _log_stage(session_id, "thematic_memory_update_async_error", stage_start, error=type(exc).__name__)

        try:
            stage_start = time.perf_counter()
            update_session_summary_async(session_id, user_message, assistant_message)
            _log_stage(session_id, "session_summary_update_dispatch_async", stage_start)
        except Exception as exc:
            logger.exception("[%s] Session summary update failed", session_id[:12])
            _log_stage(session_id, "session_summary_update_dispatch_async_error", stage_start, error=type(exc).__name__)
        finally:
            logger.info("[%s] Persistence worker finished", _session_log_id(session_id))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


    # _emit_periodic_status and _ResponseSummarizer removed —
    # stream-json with --verbose now provides real tool_use events as status updates,
    # making Haiku-based summarization redundant for the active client.


async def send_message(user_id: str, session_id: str, message: str, file_context: str = None, platform: str = None, tts_enabled: bool = False) -> dict:
    broadcast_user_id = user_id
    del user_id  # single-user system for now
    request_start = time.perf_counter()
    # Broadcast start
    _sync_broadcaster = StreamBroadcaster(broadcast_user_id, session_id, platform or "", message)
    _sync_broadcaster.start()
    state = _get_session(session_id)
    # Serialize requests per session — prevents conversation desync where
    # concurrent requests race on history, causing Jane to answer the wrong question.
    # Previously only the stream path had this gate; the sync path was unprotected.
    _gate_acquired = False
    try:
        await asyncio.wait_for(state.request_gate.acquire(), timeout=90)
        _gate_acquired = True
    except asyncio.TimeoutError:
        logger.warning("[%s] Session request_gate timed out after 90s (sync) — failing request to prevent desync", session_id[:12])
        _sync_broadcaster.error("Request serialization timeout")
        return {"text": "⚠️ Jane is busy with another request. Please try again in a moment.", "files": []}

    try:
        return await _send_message_inner(
            state, session_id, message, file_context, platform, tts_enabled,
            _sync_broadcaster, broadcast_user_id, request_start,
        )
    finally:
        if _gate_acquired:
            state.request_gate.release()


async def _send_message_inner(
    state, session_id: str, message: str, file_context: str,
    platform: str, tts_enabled: bool, _sync_broadcaster, broadcast_user_id: str,
    request_start: float,
) -> dict:
    """Inner send_message logic, always runs under request_gate."""
    # Phone tools: extract any [TOOL_RESULT:{json}] markers the Android client
    # prepended. Same treatment as the stream path — strip from user-visible
    # bubble, prepend a [PHONE TOOL RESULTS] block onto the brain-visible
    # message so Jane knows what the last phone-tool invocation did.
    _cleaned_message, _tool_results = _extract_tool_results(message or "")
    if _tool_results:
        logger.info("[%s] (sync) received %d tool result(s) from client",
                    session_id[:12], len(_tool_results))
    _user_visible_message = _cleaned_message
    if _tool_results:
        _result_block = _format_tool_results_for_brain(_tool_results)
        if _result_block:
            message = _result_block + "\n\n" + _cleaned_message
        else:
            message = _cleaned_message
    else:
        message = _cleaned_message
    resolved_file_context = _resolve_file_context(state, _user_visible_message, file_context)
    persisted_user_message = _message_for_persistence(_user_visible_message, resolved_file_context)
    brain_name = _get_brain_name()
    adapter = get_brain_adapter(brain_name, _get_execution_profile(brain_name))
    logger.info("[%s] send_message (sync) brain=%s history=%d msg_len=%d file_ctx=%s",
                session_id[:12], adapter.label, len(state.history), len(message or ""), bool(resolved_file_context))
    _log_start(session_id, "sync", message, len(state.history), adapter.label, resolved_file_context)

    stage_start = time.perf_counter()
    summary_text = format_session_summary(load_session_summary(session_id))
    _log_stage(session_id, "session_summary_load", stage_start, summary_chars=len(summary_text or ""))
    await _await_prewarm_if_running(session_id, state)
    # Standing brain cache: skip context build on turn 2+ (brain remembers)
    from llm_brain.v1.standing_brain import get_standing_brain_manager
    _sb_mgr = get_standing_brain_manager()
    _sb_bp = _sb_mgr.brain
    _skip_ctx = (
        _sb_mgr._started and _sb_bp and _sb_bp.alive and _sb_bp.turn_count > 0
    )

    stage_start = time.perf_counter()
    if _skip_ctx:
        from context_builder.v1.context_builder import JaneRequestContext, _format_recent_history
        # Standing brain already has session context from turn 1's system prompt.
        # Only inject [Recent exchanges] for pronoun resolution; skip [Session context]
        # to avoid accumulating duplicate summaries across turns.
        safety_parts = []
        recent = _format_recent_history(list(state.history), max_turns=6, max_chars=2400)
        if recent:
            safety_parts.append(f"[Recent exchanges]\n{recent}")
        safety_ctx = "\n\n".join(safety_parts)
        user_msg, _cm_loaded = _maybe_prepend_code_map(message)
        if _cm_loaded:
            logger.info("[%s] Code map injected (standing brain sync)", session_id[:12])
        transcript = f"{safety_ctx}\n\nUser: {user_msg}" if safety_ctx else user_msg
        request_ctx = JaneRequestContext(
            system_prompt="", transcript=transcript,
            retrieved_memory_summary=state.bootstrap_memory_summary or "",
        )
        _log_stage(session_id, "context_build", stage_start,
                   system_prompt_chars=0, transcript_chars=len(transcript),
                   fresh_memory_retrieval=False, bootstrap_summary_chars=0)
        logger.info("[%s] Standing brain turn %d — injected recent history only", session_id[:12], _sb_bp.turn_count)
    else:
        _memory_fallback = state.bootstrap_memory_summary or get_prefetch_result(session_id)
        request_ctx = await build_jane_context_async(
            message,
            list(state.history),  # snapshot: prevent race if another request mutates history
            file_context=resolved_file_context,
            conversation_summary=summary_text,
            session_id=session_id,
            enable_memory_retrieval=True,
            memory_summary_fallback=_memory_fallback,
            platform=platform,
            tts_enabled=tts_enabled,
        )
    if request_ctx.retrieved_memory_summary:
        state.bootstrap_memory_summary = request_ctx.retrieved_memory_summary
    state.bootstrap_complete = True
    _log_stage(
        session_id,
        "context_build",
        stage_start,
        system_prompt_chars=len(request_ctx.system_prompt or ""),
        transcript_chars=len(request_ctx.transcript or ""),
        fresh_memory_retrieval=True,
        bootstrap_summary_chars=len(state.bootstrap_memory_summary or ""),
    )
    _dump_prompt(
        session_id,
        "sync",
        message,
        summary_text,
        request_ctx,
        False,
        state.bootstrap_memory_summary,
        resolved_file_context,
    )

    stage_start = time.perf_counter()
    response = await _execute_brain_sync(session_id, brain_name, adapter, request_ctx)
    elapsed_ms = int((time.perf_counter() - stage_start) * 1000)
    logger.info("[%s] Brain responded (sync) in %dms, %d chars", session_id[:12], elapsed_ms, len(response or ""))
    _log_stage(session_id, "brain_execute", stage_start, response_chars=len(response or ""))

    user_turn = {"role": "user", "content": persisted_user_message}
    assistant_turn = {"role": "assistant", "content": response}
    state.history.extend([user_turn, assistant_turn])
    state.history = state.history[-24:]
    logger.info("[%s] Updated in-memory history to %d turns after sync response", _session_log_id(session_id), len(state.history))

    stage_start = time.perf_counter()
    _persist_turns_async(
        session_id,
        state.conv_manager,
        user_turn,
        assistant_turn,
        persisted_user_message,
        response,
    )
    _log_stage(session_id, "persistence_dispatch", stage_start)
    _log_stage(session_id, "request_total", request_start, mode="sync")
    _sync_broadcaster.finish(response or "")

    # Phone tools: strip any [[CLIENT_TOOL:...]] markers from the sync response
    # text so they never appear in the user-visible bubble. Sync mode cannot
    # emit structured client_tool_call events (no SSE stream), so any tool
    # invocations in sync mode are currently no-ops — but at minimum the raw
    # markers should not leak to the UI. Tool calls in sync mode are logged
    # for drift detection.
    if response and "[[CLIENT_TOOL:" in response:
        _sync_extractor = ToolMarkerExtractor()
        _visible, _sync_tool_calls = _sync_extractor.feed(response)
        _tail, _sync_tail_calls = _sync_extractor.flush()
        response = _visible + _tail
        _total_sync_calls = len(_sync_tool_calls) + len(_sync_tail_calls)
        if _total_sync_calls > 0:
            logger.warning(
                "[%s] (sync) response contained %d client_tool_call marker(s) "
                "that cannot be dispatched in non-streaming mode — stripped from "
                "response text",
                session_id[:12], _total_sync_calls,
            )

    return {"text": response, "files": []}


def _pick_ack(user_message: str) -> str:
    """Pick a context-appropriate quick ack based on the user's message.
    Mix of professional, warm, casual, and occasionally humorous.
    """
    import random
    msg = (user_message or "").lower().strip()

    # Questions — informational / lookup
    if any(msg.startswith(w) for w in ("is ", "are ", "was ", "were ", "do ", "does ", "did ",
                                        "can ", "could ", "will ", "would ", "should ",
                                        "how ", "what ", "where ", "when ", "why ", "who ",
                                        "have you", "has ", "which ")):
        return random.choice([
            # Original
            "Let me check.",
            "Good question — looking into it.",
            "Let me look into that.",
            "Checking now.",
            "Hmm, let me find out.",
            "One sec, let me see.",
            "Let me pull that up.",
            "Give me a moment to check.",
            "Interesting question — looking into it.",
            "Let me think about that.",
            "Let me take a look.",
            "Digging into it now.",
            "Hold on, checking.",
            "Let me look that up.",
            "Good one — let me see.",
            # Warmer / casual
            "Ooh, good question. Let me check.",
            "One sec — I know this one... or I will in a moment.",
            "Let me look into that real quick.",
            "Give me a sec, I'll dig that up.",
            "Let me poke around and find out.",
            "That's a good one. Checking now.",
            "Hold that thought — checking.",
            "Curious about that too, actually. Let me check.",
            "I should know this... let me verify.",
            "Let me take a peek.",
            "Hmm, good question. Digging in.",
            "Fair question — checking now.",
            "One moment while I track that down.",
        ])

    # Status/progress questions
    if any(kw in msg for kw in ("status", "progress", "update", "how's it going",
                                 "what's happening", "working on", "where are we",
                                 "current state", "what happened")):
        return random.choice([
            # Original
            "Let me check on that.",
            "One sec, pulling up the status.",
            "Checking the current state.",
            "Let me see where things stand.",
            "Pulling up the details now.",
            "Let me get you caught up.",
            "Checking what's happened.",
            "Give me a sec to review.",
            # Warmer
            "One sec — pulling up the latest.",
            "Let me see what's been going on.",
            "Ah, good timing — let me review.",
            "Hold on, let me see where we left off.",
            "Let me take stock real quick.",
        ])

    # Requests to fix/debug
    if any(kw in msg for kw in ("fix", "bug", "broken", "error", "crash", "wrong",
                                 "doesn't work", "not working", "failed", "failing",
                                 "issue", "problem")):
        return random.choice([
            # Original
            "On it — let me investigate.",
            "Looking into it now.",
            "Let me dig into this.",
            "I'll take a look at what's going on.",
            "Let me trace through this.",
            "Investigating now.",
            "Let me figure out what happened.",
            "On it — give me a moment.",
            "Let me hunt this down.",
            "Diving into the logs now.",
            "I see — let me look into it.",
            "Let me check what went wrong.",
            # Warmer / humor
            "Ugh, let me see what happened.",
            "On it — detective mode activated.",
            "Alright, let's figure this out.",
            "Time to put on the debugging hat.",
            "Let me take a look under the hood.",
            "Hmm, that's not right. Let me investigate.",
            "Ok, let's track this down.",
            "I'll get to the bottom of this.",
            "On the case. Give me a moment.",
            "Something's off — let me look.",
            "Alright, diving in.",
        ])

    # Opinions / thoughts / advice
    if any(kw in msg for kw in ("think", "opinion", "suggest", "recommend", "advice",
                                 "better", "prefer", "thoughts on", "feel about",
                                 "makes sense", "good idea")):
        return random.choice([
            # Original
            "Let me think about that.",
            "Good question — let me consider the options.",
            "Hmm, let me weigh in on that.",
            "Let me think this through.",
            "Interesting — give me a sec to think.",
            "Let me consider that.",
            # Warmer
            "Hmm, let me think on that.",
            "Let me chew on that for a moment.",
            "Interesting angle. Let me consider...",
            "Let me weigh the options real quick.",
            "That's worth thinking about. One sec.",
            "Hmm, I have thoughts. Let me organize them.",
            "Good point — let me consider that.",
            "Let me mull that over for a sec.",
        ])

    # Explanations / learning
    if any(kw in msg for kw in ("explain", "tell me about", "what is", "what's a",
                                 "how does", "why does", "meaning of", "difference between")):
        return random.choice([
            # Original
            "Sure, let me explain.",
            "Good question — here's the deal.",
            "Let me break that down.",
            "Here's how it works.",
            "Let me walk you through it.",
            "Alright, let me explain that.",
            # Warmer
            "Oh, this is a fun one. Let me explain.",
            "Sure thing — here's the rundown.",
            "Let me break that down for you.",
            "Alright, storytime. Kind of.",
            "So basically, here's what's going on.",
            "Let me lay it out.",
            "Happy to explain — here goes.",
            "This is a good one to know. Let me explain.",
        ])

    # Greetings
    if any(kw in msg for kw in ("hello", "hey", "hi ", "good morning", "good evening",
                                 "good night", "what's up", "sup", "yo")):
        return random.choice([
            # Original
            "Hey!",
            "Hi there!",
            "Hey, what's up?",
            "Hey!",
            "What's up?",
            "Hi! What can I help with?",
            "Hey! Good to hear from you.",
            # Warmer
            "Hey! What's on your mind?",
            "Hi! Ready when you are.",
            "Hey there! What are we working on?",
            "Yo! What's the plan?",
            "Hi! What's cooking?",
            "Hey! Fire away.",
        ])

    # Thanks / appreciation
    if any(kw in msg for kw in ("thank", "thanks", "appreciate", "nice work", "good job",
                                 "well done", "awesome", "great job", "perfect")):
        return random.choice([
            # Original
            "Glad to help!",
            "Anytime!",
            "Happy to help.",
            "No problem!",
            "Of course!",
            "You got it.",
            # Warmer
            "Glad that worked out!",
            "No sweat!",
            "That's what I'm here for.",
            "Teamwork!",
            "We make a good team.",
            "Appreciate you saying that!",
            "Always happy to help.",
        ])

    # Show / list / display requests
    if any(kw in msg for kw in ("show me", "list ", "display", "print", "give me",
                                 "pull up", "let me see")):
        return random.choice([
            # Original
            "Sure, pulling that up.",
            "One moment.",
            "Let me get that for you.",
            "Coming right up.",
            "Sure thing.",
            "On it.",
            "Grabbing that now.",
            # Warmer
            "Pulling it up now.",
            "On it — here you go in a sec.",
            "Sure thing, just a moment.",
            "Let me fetch that.",
            "Right away.",
            "Give me a sec to pull that together.",
        ])

    # Build / deploy / create
    if any(kw in msg for kw in ("build", "deploy", "create", "make", "set up",
                                 "install", "add ", "implement", "write")):
        return random.choice([
            # Original
            "On it.",
            "Let me get that set up.",
            "Building now.",
            "Working on it.",
            "Sure — putting that together.",
            "Alright, let me build that out.",
            "Let me handle that.",
            "Starting on it now.",
            "Sure, let me set that up.",
            "Got it — getting started.",
            # Warmer / humor
            "On it!",
            "Let's build this.",
            "Rolling up my sleeves. Let's go.",
            "Consider it started.",
            "Building time. On it.",
            "Sure — let me wire that up.",
            "Alright, let's make it happen.",
            "Let me cook something up.",
            "Time to build. Let's go.",
        ])

    # Remove / delete / clean up
    if any(kw in msg for kw in ("remove", "delete", "clean up", "get rid of", "drop")):
        return random.choice([
            # Original
            "Got it — cleaning that up.",
            "Removing it now.",
            "On it.",
            "Sure, taking care of that.",
            "Let me handle that.",
            # Warmer / humor
            "Got it — cleaning house.",
            "Gone in a sec.",
            "Consider it gone.",
            "Sweeping that away now.",
            "On it — poof.",
        ])

    # Frustration / urgency
    if any(kw in msg for kw in ("again", "still", "keeps", "annoying", "frustrated",
                                 "seriously", "come on", "ugh", "wtf")):
        return random.choice([
            "I hear you. Let me take another look.",
            "Sorry about that — let me fix this properly.",
            "Understood. Let me dig deeper this time.",
            "Fair. Let me get this right.",
            "Yeah, that's not great. On it.",
            "Let me approach this differently.",
            "I got you — let me sort this out.",
        ])

    # Default — no obvious category match.
    # Return None so Opus can generate a more nuanced, context-aware ack.
    return None


async def stream_message(
    user_id: str,
    session_id: str,
    message: str,
    file_context: str = None,
    platform: str = None,
    tts_enabled: bool = False,
) -> AsyncIterator[str]:
    broadcast_user_id = user_id  # keep for broadcast; not used for anything else yet
    del user_id  # single-user system for now
    request_start = time.perf_counter()
    state = _get_session(session_id)
    # Serialize requests per session — prevents conversation offset bug where
    # concurrent requests race on history, causing Jane to answer the wrong question.
    # Timeout after 90s to prevent permanent deadlock if a previous request got stuck.
    _gate_acquired = False
    try:
        await asyncio.wait_for(state.request_gate.acquire(), timeout=90)
        _gate_acquired = True
    except asyncio.TimeoutError:
        logger.warning("[%s] Session request_gate timed out after 90s (stream) — failing request to prevent desync", session_id[:12])
        yield json.dumps({"type": "error", "error": "Jane is busy with another request. Please try again."})
        return
    # Phone tools: extract any [TOOL_RESULT:{json}] markers the Android client
    # prepended to this user turn. Strip them from the user-visible bubble
    # (via persisted_user_message) but prepend a formatted context block onto
    # the message the brain actually sees, so Jane knows what the last phone-
    # tool invocation did without the user seeing raw JSON in their chat.
    _cleaned_message, _tool_results = _extract_tool_results(message or "")
    if _tool_results:
        logger.info("[%s] received %d tool result(s) from client", session_id[:12], len(_tool_results))
        # Verbose diagnostic: dump each tool result so a failed/needs_user
        # status has its full reason visible in the log. Previously the only
        # trace was a 60-char-truncated echo in Jane's next ack, which hid
        # the actual failure reason from the logs.
        for _idx, _tr in enumerate(_tool_results):
            _tr_tool = _tr.get("tool", "?")
            _tr_status = _tr.get("status", "?")
            _tr_msg = str(_tr.get("message", ""))[:300]
            _tr_data = _tr.get("data")
            _tr_data_str = ""
            if isinstance(_tr_data, (dict, list)):
                try:
                    _tr_data_str = " data=" + json.dumps(_tr_data, ensure_ascii=True)[:500]
                except Exception:
                    _tr_data_str = " data=<unserializable>"
            logger.info(
                "[%s]   tool_result[%d]: tool=%s status=%s msg=%r%s",
                session_id[:12], _idx, _tr_tool, _tr_status, _tr_msg, _tr_data_str,
            )
    _brain_visible_message = _cleaned_message  # what the brain will see
    _user_visible_message = _cleaned_message   # what the user will see in the bubble
    if _tool_results:
        _result_block = _format_tool_results_for_brain(_tool_results)
        if _result_block:
            _brain_visible_message = _result_block + "\n\n" + _cleaned_message
    # From this point on, `message` is what the brain sees (includes tool
    # results context); `persisted_user_message` uses the user-visible text.
    message = _brain_visible_message
    resolved_file_context = _resolve_file_context(state, _user_visible_message, file_context)
    persisted_user_message = _message_for_persistence(_user_visible_message, resolved_file_context)
    brain_name = _get_brain_name()
    adapter = get_brain_adapter(brain_name, _get_execution_profile(brain_name))
    logger.info("[%s] stream_message brain=%s history=%d msg_len=%d file_ctx=%s",
                session_id[:12], adapter.label, len(state.history), len(message or ""), bool(resolved_file_context))
    _log_start(session_id, "stream", message, len(state.history), adapter.label, resolved_file_context)

    loop = asyncio.get_running_loop()
    loop_thread_id = threading.get_ident()

    # Broadcast: summarized progress to other connected clients
    broadcaster = StreamBroadcaster(broadcast_user_id, session_id, platform or "", message, loop)
    broadcaster.start()
    queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()

    _intermediary_steps: list[str] = []
    first_visible_event_logged = False
    final_response: str | None = None
    _ack_seen = False  # tracks whether brain has emitted an [ACK] block
    _accumulated_deltas = ""  # accumulates delta text to detect [ACK]
    _tool_extractor = ToolMarkerExtractor()  # phone-tools marker extraction (see class docstring)

    def _raw_emit(event_type: str, payload: str | None = None) -> None:
        item = (event_type, payload)
        # Log status and thought events for intermediary step history
        if event_type in ("status", "thought") and payload:
            _intermediary_steps.append(f"[{event_type}] {payload}")
        if threading.get_ident() == loop_thread_id:
            queue.put_nowait(item)
            return
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def emit(event_type: str, payload: str | None = None) -> None:
        nonlocal _ack_seen, _accumulated_deltas
        # Track ACK in delta text
        if event_type == "delta" and payload:
            _accumulated_deltas += payload
            if not _ack_seen and "[/ACK]" in _accumulated_deltas:
                _ack_seen = True
            # Phone tools: extract [[CLIENT_TOOL:...]] markers and emit them as
            # structured client_tool_call SSE events; forward only the
            # sanitized text to the client so markers don't appear in the
            # chat bubble. _accumulated_deltas retains the raw text (with
            # markers) for history persistence so Jane's mind can see her
            # own prior emissions when continuing a draft state machine.
            visible, tool_calls = _tool_extractor.feed(payload)
            for tc in tool_calls:
                _tc_tool = tc.get("tool", "")
                if _tc_tool.startswith("email."):
                    # Email tools are server-side — do NOT send to Android client.
                    # Execute server-side and inject result as visible text.
                    logger.info("[%s] Intercepting server-side email tool: %s",
                                session_id[:12], _tc_tool)
                    _email_result_text = _execute_email_tool_serverside(tc)
                    if _email_result_text:
                        visible = (visible or "") + _email_result_text
                else:
                    logger.info("[%s] Emitting client_tool_call: tool=%s call_id=%s",
                                session_id[:12], _tc_tool, tc.get("call_id", "?")[:12])
                    _raw_emit("client_tool_call", json.dumps(tc, ensure_ascii=True))
            if visible:
                _raw_emit("delta", visible)
            return
        if event_type == "done":
            # Final flush of any buffered tool markers at stream end.
            visible_tail, tail_calls = _tool_extractor.flush()
            for tc in tail_calls:
                _tc_tool = tc.get("tool", "")
                if _tc_tool.startswith("email."):
                    logger.info("[%s] Intercepting server-side email tool (flush): %s",
                                session_id[:12], _tc_tool)
                    _email_result_text = _execute_email_tool_serverside(tc)
                    if _email_result_text:
                        visible_tail = (visible_tail or "") + _email_result_text
                else:
                    logger.info("[%s] Emitting client_tool_call (flush): tool=%s call_id=%s",
                                session_id[:12], _tc_tool, tc.get("call_id", "?")[:12])
                    _raw_emit("client_tool_call", json.dumps(tc, ensure_ascii=True))
            if visible_tail:
                _raw_emit("delta", visible_tail)

            # Opus music fallback: if Opus emitted [MUSIC_PLAY:<query>] with a
            # non-UUID query (track name, artist), intercept it, create the
            # playlist on the fly, and replace the query with the real UUID.
            # Gemma normally handles this via the MUSIC_PLAY short-circuit, but
            # if Gemma misclassified or was skipped, Opus writes the raw marker
            # and the Android client would 404 on /api/playlists/<track name>.
            import re as _re_local
            _music_re = _re_local.compile(r"\[MUSIC_PLAY:([^\]]+)\]")
            _music_match = _music_re.search(payload or "")
            if _music_match:
                _music_query = _music_match.group(1).strip()
                # UUIDs from Gemma's path are hex strings (16 chars). Non-UUID
                # means Opus used a query string — create the playlist now.
                if not _re_local.match(r"^[0-9a-f]{16}$", _music_query):
                    logger.info("[%s] Opus music fallback: creating playlist for query '%s'",
                                session_id[:12], _music_query[:60])
                    try:
                        from jane_web.main import create_music_playlist_from_query
                        _fb_playlist = create_music_playlist_from_query(_music_query)
                        if _fb_playlist:
                            _old_marker = _music_match.group(0)
                            _new_marker = f"[MUSIC_PLAY:{_fb_playlist['id']}]"
                            payload = payload.replace(_old_marker, _new_marker)
                            logger.info("[%s] Opus music fallback: replaced with playlist id=%s (%d tracks)",
                                        session_id[:12], _fb_playlist['id'], len(_fb_playlist.get('tracks', [])))
                        else:
                            logger.info("[%s] Opus music fallback: no matches for '%s'",
                                        session_id[:12], _music_query[:60])
                    except Exception as _fb_err:
                        logger.warning("[%s] Opus music fallback failed: %s", session_id[:12], _fb_err)

        # If gemma router already emitted an ack, suppress Claude's [ACK] block.
        # If gemma didn't handle it (delegate/unknown), let Claude provide its own ack.

        # Strip [[CLIENT_TOOL:...]] markers from the done payload so Android
        # TTS never speaks raw tool syntax.  Delta events are already stripped
        # by _tool_extractor above, but the done event carries the full raw
        # response text — Android uses done.data for TTS when present.
        if event_type == "done" and payload and "[[CLIENT_TOOL:" in payload:
            _done_extractor = ToolMarkerExtractor()
            _done_visible, _ = _done_extractor.feed(payload)
            _done_tail, _ = _done_extractor.flush()
            payload = _done_visible + _done_tail

        _raw_emit(event_type, payload)

    emit("start")
    emit("status", "Reviewing the current thread and loading session context.")
    await asyncio.sleep(0)  # flush start+status immediately so UI isn't blank

    # Gemma classification runs on EVERY message (text AND voice) because it
    # handles music routing (MUSIC_PLAY → playlist creation) and self-handle
    # (trivia, weather, greetings) which are valuable regardless of input
    # method. What changes between text and voice mode is whether the DELEGATE
    # ACK is emitted:
    #   - Voice mode: ack is emitted (fills the silence gap while Opus thinks)
    #   - Text mode: ack is SUPPRESSED (user sees typing indicator instead)
    #
    # Pre-dispatch filters (e.g., open SMS draft) skip classification entirely
    # because the message MUST reach Opus for the draft state machine.
    _suppress_delegate_ack = not tts_enabled  # text mode: classify but don't ack
    _skip_initial_ack = False
    try:
        from jane.tool_loader import should_skip_initial_ack
        _skip_initial_ack = should_skip_initial_ack(state.history)
    except Exception as _tool_err:
        logger.warning("tool_loader pre-dispatch filter failed: %s", _tool_err)
    if _skip_initial_ack:
        logger.info("[%s] pre-dispatch filter matched — skipping classification entirely",
                    session_id[:12])

    # Gemma4 router: classify prompt and short-circuit if self-handleable.
    # Runs async with a 2s timeout — on timeout/error, falls through to Claude.
    # Skipped entirely when an SMS draft is open (see _skip_initial_ack above)
    # so edit instructions like "make it 30" route straight to Jane's mind.
    _gemma_short_circuit = False
    _gemma_delegate_ack = None  # quick ack emitted by Gemma when delegating to Claude
    _gemma_conversation_end = False  # v2 pipeline: END_CONVERSATION signal to client
    _gemma_client_tools = []  # v2 pipeline: client tool calls from Stage 2 fast path
    _shopping_list_active = False  # set by shopping_list classification
    # Always initialize _classification so run_pipeline_async() can access it as a
    # free variable even when the v2 pipeline is used and the old pipeline is skipped.
    _classification = None
    try:
        if _skip_initial_ack:
            # Fall-through sentinel: raise a silent skip marker caught below.
            raise _SkipRouterSignal()
        if os.environ.get("JANE_USE_V2_PIPELINE") == "1":
            # ── v2 pipeline: Stage 1 classify → build context → Stage 2 execute ────
            from intent_classifier.v2.classifier import stage1_classify as _s1_fn
            from intent_classifier.v1.gemma_stage2 import stage2_execute as _s2_fn
            ROUTER_MODEL = "embedding-v2"
            _stage1 = await _s1_fn(message, session_id)
            _s1_cls = _stage1.get("classification", "DELEGATE_OPUS")
            _stage1["classification"] = _s1_cls
            # Sync _classification so run_pipeline_async()'s CLASSIFICATION_TO_INTENT
            # lookup works for v2 pipeline turns that delegate to Opus.
            _classification = _s1_cls.lower()
            # ── Build task context (fetch data for data-intensive intents) ─────────
            _v2_task_ctx = ""
            if _s1_cls == "READ_MESSAGES":
                _gemma_delegate_ack = "Checking your messages..."
                try:
                    from vault_web.database import get_db as _v2_get_db
                    import json as _v2j
                    _v2_filter = _stage1.get("filter", "")
                    _v2_since_ms = int((time.time() - 5 * 86400) * 1000)
                    with _v2_get_db() as _v2c:
                        if _v2_filter:
                            _v2_fq = f"%{_v2_filter}%"
                            _v2_rows = _v2c.execute(
                                "SELECT sender, body, timestamp_ms, is_read, is_contact, msg_type "
                                "FROM synced_messages WHERE timestamp_ms > ? "
                                "AND (sender LIKE ? OR body LIKE ?) "
                                "ORDER BY timestamp_ms DESC LIMIT 30",
                                (_v2_since_ms, _v2_fq, _v2_fq),
                            ).fetchall()
                        else:
                            _v2_rows = _v2c.execute(
                                "SELECT sender, body, timestamp_ms, is_read, is_contact, msg_type "
                                "FROM synced_messages WHERE timestamp_ms > ? "
                                "ORDER BY timestamp_ms DESC LIMIT 30",
                                (_v2_since_ms,),
                            ).fetchall()
                    _v2_msgs = [dict(r) for r in _v2_rows]
                    if _v2_msgs:
                        from datetime import datetime as _v2dt
                        for _m2 in _v2_msgs:
                            try:
                                _m2["time"] = _v2dt.fromtimestamp(_m2["timestamp_ms"] / 1000).strftime("%b %d %I:%M %p")
                            except Exception:
                                pass
                        _v2_task_ctx = (
                            "[SMS INBOX DATA — fetched from synced messages DB]\n"
                            + _v2j.dumps(_v2_msgs, indent=2, default=str)
                            + "\n[END SMS INBOX DATA]\n\n"
                            "msg_type guide: personal=important contacts, reminder=appointments, "
                            "notification=shipping/delivery, spam=skip, unknown=mention if important."
                        )
                    else:
                        _v2_task_ctx = "[SMS INBOX DATA]\nNo text messages found in the last 5 days.\n[END SMS INBOX DATA]"
                    logger.info("[%s] v2 READ_MESSAGES: fetched %d msgs%s",
                                session_id[:12], len(_v2_msgs),
                                f" (filter: {_v2_filter})" if _v2_filter else "")
                except Exception as _v2_sms_err:
                    logger.error("[%s] v2 SMS fetch failed: %s", session_id[:12], _v2_sms_err)
                    _v2_task_ctx = f"[SMS ERROR]\nFailed to fetch messages: {_v2_sms_err}\n[END SMS ERROR]"
            elif _s1_cls == "READ_EMAIL":
                _gemma_delegate_ack = "Let me check your email..."
                try:
                    from agent_skills.email_tools import read_inbox as _v2_read_inbox
                    _v2_emails = _v2_read_inbox(limit=10, query="is:unread")
                    if _v2_emails:
                        import json as _v2ej
                        _v2_task_ctx = (
                            "[EMAIL INBOX DATA — fetched server-side]\n"
                            + _v2ej.dumps(_v2_emails, indent=2, default=str)
                            + "\n[END EMAIL INBOX DATA]"
                        )
                    else:
                        _v2_task_ctx = "[EMAIL INBOX DATA]\nNo unread emails found.\n[END EMAIL INBOX DATA]"
                    logger.info("[%s] v2 READ_EMAIL: fetched %d emails", session_id[:12], len(_v2_emails) if _v2_emails else 0)
                except RuntimeError as _v2_email_err:
                    _v2_task_ctx = f"[EMAIL ERROR]\nGmail not set up: {_v2_email_err}\n[END EMAIL ERROR]"
                except Exception as _v2_email_err:
                    logger.error("[%s] v2 email fetch failed: %s", session_id[:12], _v2_email_err)
                    _v2_task_ctx = f"[EMAIL ERROR]\nFailed to fetch emails: {_v2_email_err}\n[END EMAIL ERROR]"
            elif _s1_cls == "MUSIC_PLAY":
                _v2_query = _stage1.get("query", "")
                _gemma_delegate_ack = f"Playing {_v2_query}..." if _v2_query else "Playing music..."
                try:
                    from jane_web.main import create_music_playlist_from_query as _v2_pl_fn
                    _v2_pl = _v2_pl_fn(_v2_query)
                    if _v2_pl and _v2_pl.get("tracks"):
                        _v2_tnames = ", ".join(t.get("title", t.get("path", "?")) for t in _v2_pl["tracks"][:10])
                        _v2_task_ctx = (
                            f"[MUSIC DATA]\n"
                            f"Playlist ID: {_v2_pl['id']}\n"
                            f"Name: {_v2_pl['name']}\n"
                            f"Tracks ({len(_v2_pl['tracks'])}): {_v2_tnames}\n"
                            f"[END MUSIC DATA]"
                        )
                    else:
                        _v2_task_ctx = "[MUSIC DATA]\nNo matching tracks found.\n[END MUSIC DATA]"
                except Exception as _v2_music_err:
                    logger.warning("[%s] v2 music playlist failed: %s", session_id[:12], _v2_music_err)
                    _v2_task_ctx = f"[MUSIC ERROR]\n{_v2_music_err}\n[END MUSIC ERROR]"
            elif _s1_cls == "SHOPPING_LIST":
                _v2_action = (_stage1.get("action") or "").lower().strip()
                try:
                    from agent_skills.shopping_list import (
                        add_item as _v2_add_item,
                        remove_item as _v2_rm_item,
                        clear_list as _v2_clear_list,
                    )
                    _v2_store = "default"
                    if _v2_action.startswith("add "):
                        _v2_item = _v2_action[4:].strip()
                        for _v2_kw in (" to costco", " to the costco", " to walmart",
                                       " to the walmart", " to grocery", " to the grocery",
                                       " to target", " to the target"):
                            if _v2_kw in _v2_item.lower():
                                _v2_store = _v2_kw.split("to ")[-1].strip().rstrip(" list").strip()
                                _v2_item = _v2_item[:_v2_item.lower().index(_v2_kw)].strip()
                                break
                        _v2_updated = _v2_add_item(_v2_item, _v2_store)
                        _v2_task_ctx = (f"Added {_v2_item!r} to the {_v2_store} list. "
                                        f"Current list: {', '.join(_v2_updated) or '(empty)'}")
                    elif _v2_action.startswith("remove "):
                        _v2_item = _v2_action[7:].strip()
                        for _v2_kw in (" from costco", " from the costco",
                                       " from walmart", " from grocery"):
                            if _v2_kw in _v2_item.lower():
                                _v2_store = _v2_kw.split("from ")[-1].strip().rstrip(" list").strip()
                                _v2_item = _v2_item[:_v2_item.lower().index(_v2_kw)].strip()
                                break
                        _v2_updated = _v2_rm_item(_v2_item, _v2_store)
                        _v2_task_ctx = (f"Removed {_v2_item!r} from the {_v2_store} list. "
                                        f"Current list: {', '.join(_v2_updated) or '(empty)'}")
                    elif _v2_action.startswith("clear"):
                        _v2_store = _v2_action.replace("clear", "").strip() or "default"
                        _v2_clear_list(_v2_store)
                        _v2_task_ctx = f"Cleared the {_v2_store} shopping list."
                except Exception as _v2_shop_err:
                    logger.warning("[%s] v2 shopping list failed: %s", session_id[:12], _v2_shop_err)
            # ── Execute Stage 2 ────────────────────────────────────────────────────
            _stage2 = await _s2_fn(_s1_cls, _stage1, _v2_task_ctx, session_id, message)
            logger.info(
                "[%s] v2 stage2: cls=%s delegate=%s conv_end=%s tools=%d resp=%r",
                session_id[:12], _s1_cls, _stage2.get("delegate"),
                _stage2.get("conversation_end"), len(_stage2.get("client_tools") or []),
                (_stage2.get("response") or "")[:60],
            )
            if _stage2.get("conversation_end"):
                _gemma_conversation_end = True
                _gemma_short_circuit = True
                _router_response = _stage2["response"]
            elif _stage2.get("delegate"):
                _gemma_short_circuit = False
                _gemma_delegate_ack = _stage2.get("response") or _gemma_delegate_ack
                # Inject delegate context into message so Opus sees it
                _v2_dctx = _stage2.get("delegate_context", "") or _v2_task_ctx
                if _v2_dctx:
                    message = message + "\n\n" + _v2_dctx
                if _gemma_delegate_ack and not _suppress_delegate_ack:
                    _raw_emit("model", ROUTER_MODEL)
                    _raw_emit("ack", _gemma_delegate_ack)
                    _ack_seen = True
                    logger.info("[%s] v2 delegate ack: %s", session_id[:12], (_gemma_delegate_ack or "")[:60])
                elif _gemma_delegate_ack and _suppress_delegate_ack:
                    logger.info("[%s] v2 delegate (ack suppressed, text mode): %s",
                                session_id[:12], (_gemma_delegate_ack or "")[:60])
            else:
                # Stage 2 handled it completely — short-circuit
                _gemma_short_circuit = True
                _router_response = _stage2["response"]
                _gemma_client_tools = _stage2.get("client_tools") or []
            raise _SkipRouterSignal()  # skip old pipeline
        # ── Old pipeline (JANE_USE_V2_PIPELINE not set) ───────────────────────────
        from intent_classifier.v1.gemma_router import classify_prompt, ROUTER_MODEL
        _router_history = [{"role": h["role"], "content": h.get("content", "")}
                           for h in state.history[-10:]
                           if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str)]
        _classification, _router_response = await classify_prompt(message, _router_history)
        # Keyword safety net: override Gemma if it misclassifies obvious intents
        _msg_lower = (message or "").lower()
        if _classification != "read_email" and any(kw in _msg_lower for kw in ("email", "inbox", "gmail")):
            if any(kw in _msg_lower for kw in ("read", "check", "see", "show", "any new", "what")):
                logger.info("[%s] Keyword override: %s → read_email", session_id[:12], _classification)
                _classification = "read_email"
                _router_response = "read_email"
        if _classification != "read_messages" and _classification != "sync_messages" and any(kw in _msg_lower for kw in ("text msg", "text message", "texts", "sms")):
            if any(kw in _msg_lower for kw in ("read", "check", "see", "show", "any new", "what")):
                logger.info("[%s] Keyword override: %s → read_messages", session_id[:12], _classification)
                _classification = "read_messages"
                _router_response = "read_inbox"
        if _classification != "sync_messages" and any(kw in _msg_lower for kw in ("sync", "resync", "re-sync")):
            if any(kw in _msg_lower for kw in ("message", "messages", "texts", "sms", "text")):
                logger.info("[%s] Keyword override: %s → sync_messages", session_id[:12], _classification)
                _classification = "sync_messages"
                _router_response = "sync"
        if _classification == "music_play" and _router_response:
            # Music: delegate to Opus for nuanced handling (e.g., "play something
            # relaxing", "skip the piano tutorials"). Server pre-creates the playlist
            # so Opus can reference it, but Opus decides the response.
            logger.info("[%s] Gemma router: music_play query='%s' → delegating to Opus",
                        session_id[:12], _router_response)
            _gemma_delegate_ack = f"Playing {_router_response}..."
            _gemma_short_circuit = False
            try:
                from jane_web.main import create_music_playlist_from_query
                playlist = create_music_playlist_from_query(_router_response)
                if playlist is not None and len(playlist.get("tracks", [])) > 0:
                    track_count = len(playlist["tracks"])
                    track_names = ", ".join(t.get("title", t.get("path", "?")) for t in playlist["tracks"][:10])
                    _music_ctx = (
                        f"\n\n[MUSIC DATA — playlist created server-side]\n"
                        f"Playlist ID: {playlist['id']}\n"
                        f"Name: {playlist['name']}\n"
                        f"Tracks ({track_count}): {track_names}\n"
                        f"[END MUSIC DATA]\n\n"
                        f"To play this playlist, include [MUSIC_PLAY:{playlist['id']}] in your response.\n"
                        f"Tell the user what you're playing. If tracks include duplicates or "
                        f"unwanted versions (e.g., tutorials vs originals), mention it."
                    )
                    message = message + _music_ctx
                else:
                    message = message + "\n\n[MUSIC DATA]\nNo matching tracks found for this query.\n[END MUSIC DATA]\nTell the user you couldn't find matching music."
            except Exception as _music_err:
                logger.warning("[%s] Music playlist creation failed: %s", session_id[:12], _music_err)
                message = message + f"\n\n[MUSIC ERROR]\nFailed to search music library: {_music_err}\n[END MUSIC ERROR]"
        elif _classification == "read_messages":
            # Read messages server-side from synced_messages DB (synced by Android).
            # Same pattern as read_email: inject data into the brain context.
            logger.info("[%s] Gemma router: read_messages → fetching from synced DB",
                        session_id[:12])
            _gemma_delegate_ack = "Checking your messages..."
            _gemma_short_circuit = False
            _sms_data_ctx = ""
            try:
                from vault_web.database import get_db as _get_sms_db
                import json as _sms_json
                # Parse optional sender filter from router response
                _sms_resp = (_router_response or "").lower().strip()
                _sms_days = 5
                _sms_limit = 30
                _sender_filter = None
                # Check for sender name in response (e.g., "read_inbox kathia")
                import re as _sms_re
                _sms_parts = _sms_resp.replace("read_inbox", "").replace("read_messages", "").strip()
                if _sms_parts and not _sms_parts.isdigit():
                    _sender_filter = _sms_parts.strip()
                _limit_match = _sms_re.search(r"\b(\d+)\b", _sms_resp)
                if _limit_match:
                    _sms_limit = min(int(_limit_match.group(1)), 50)

                _since_ms = int((time.time() - _sms_days * 86400) * 1000)
                with _get_sms_db() as _sms_conn:
                    if _sender_filter:
                        _filter_q = f"%{_sender_filter}%"
                        _sms_rows = _sms_conn.execute(
                            """SELECT sender, body, timestamp_ms, is_read, is_contact, msg_type
                               FROM synced_messages
                               WHERE timestamp_ms > ? AND (sender LIKE ? OR body LIKE ?)
                               ORDER BY timestamp_ms DESC LIMIT ?""",
                            (_since_ms, _filter_q, _filter_q, _sms_limit),
                        ).fetchall()
                    else:
                        _sms_rows = _sms_conn.execute(
                            """SELECT sender, body, timestamp_ms, is_read, is_contact, msg_type
                               FROM synced_messages
                               WHERE timestamp_ms > ?
                               ORDER BY timestamp_ms DESC LIMIT ?""",
                            (_since_ms, _sms_limit),
                        ).fetchall()
                    _sms_list = [dict(r) for r in _sms_rows]

                if _sms_list:
                    from datetime import datetime as _dt
                    for _m in _sms_list:
                        try:
                            _m["time"] = _dt.fromtimestamp(_m["timestamp_ms"] / 1000).strftime("%b %d %I:%M %p")
                        except Exception:
                            pass
                    _sms_data_ctx = (
                        "\n\n[SMS INBOX DATA — fetched from synced messages DB]\n"
                        + _sms_json.dumps(_sms_list, indent=2, default=str)
                        + "\n[END SMS INBOX DATA]\n\n"
                        "Summarize these text messages. Each message has a msg_type field:\n"
                        "- 'personal' (is_contact=true): from known contacts — read these first, they're important\n"
                        "- 'reminder': appointments, due dates, renewals — mention briefly\n"
                        "- 'notification': shipping, delivery, order updates — mention briefly\n"
                        "- 'spam': promotions, deals, marketing — skip unless user asks\n"
                        "- 'unknown': unrecognized sender — mention only if content seems important\n"
                        "Group personal messages by sender. If the user asked about a specific person, focus on those."
                    )
                else:
                    _sms_data_ctx = (
                        "\n\n[SMS INBOX DATA — fetched from synced messages DB]\n"
                        "No text messages found in the last 5 days.\n"
                        "[END SMS INBOX DATA]\n\n"
                        "Tell the user no recent text messages were found. "
                        "If messages haven't synced yet, suggest they open the Vessence app on their phone."
                    )
                logger.info("[%s] Fetched %d SMS messages from synced DB%s",
                            session_id[:12], len(_sms_list),
                            f" (filter: {_sender_filter})" if _sender_filter else "")
            except Exception as _sms_err:
                _sms_data_ctx = (
                    "\n\n[SMS ERROR]\n"
                    f"Failed to fetch messages from DB: {_sms_err}\n"
                    "Apologize and suggest the user open the Vessence app to trigger a sync.\n"
                    "[END SMS ERROR]"
                )
                logger.error("[%s] SMS DB fetch failed: %s", session_id[:12], _sms_err)
            if _sms_data_ctx:
                message = message + _sms_data_ctx
        elif _classification == "sync_messages":
            # Force SMS sync: inject instruction for the brain to emit
            # [[CLIENT_TOOL:sync.force_sms:{}]] so the Android app re-syncs.
            logger.info("[%s] Gemma router: sync_messages → delegating to brain with sync tool instruction",
                        session_id[:12])
            _gemma_delegate_ack = "Syncing your messages..."
            _gemma_short_circuit = False
            message = message + (
                "\n\n[SYNC REQUEST]\n"
                "The user wants to sync/resync their text messages. "
                "Emit the sync tool marker to trigger a full SMS re-sync on their phone:\n"
                "[[CLIENT_TOOL:sync.force_sms:{}]]\n"
                "Tell the user you're syncing their messages now and it should take a moment.\n"
                "[END SYNC REQUEST]"
            )
        elif _classification == "read_email":
            # Email is server-side (not a phone tool). Fetch emails here and
            # inject them into the brain context so Jane can respond with actual
            # email content in a single turn — no CLIENT_TOOL round-trip needed.
            logger.info("[%s] Gemma router: read_email → fetching server-side",
                        session_id[:12])
            _gemma_delegate_ack = "Let me check your email..."
            _gemma_short_circuit = False
            _email_data_ctx = ""
            try:
                from agent_skills.email_tools import read_inbox as _read_inbox
                # Parse limit and query from router response
                _email_resp = (_router_response or "").lower().strip()
                _email_limit = 10
                _email_query = "is:unread"
                # Check for number in response (e.g., "read_email 3")
                import re as _email_re
                _limit_match = _email_re.search(r"\b(\d+)\b", _email_resp)
                if _limit_match:
                    _email_limit = min(int(_limit_match.group(1)), 20)
                # Check for sender filter (e.g., "from:bob")
                _from_match = _email_re.search(r"from:(\S+)", _email_resp)
                if _from_match:
                    _email_query = f"from:{_from_match.group(1)}"
                _emails = _read_inbox(limit=_email_limit, query=_email_query)
                if _emails:
                    import json as _ej
                    _email_data_ctx = (
                        "\n\n[EMAIL INBOX DATA — fetched server-side just now]\n"
                        + _ej.dumps(_emails, indent=2, default=str)
                        + "\n[END EMAIL INBOX DATA]\n\n"
                        "Summarize these emails for the user. Triage: personal/important emails first, "
                        "skip spam/promos. Quote sender and subject. If the user asked about a specific "
                        "sender or count, honor that."
                    )
                else:
                    _email_data_ctx = (
                        "\n\n[EMAIL INBOX DATA — fetched server-side just now]\n"
                        "No unread emails found.\n"
                        "[END EMAIL INBOX DATA]\n\n"
                        "Tell the user their inbox is clear."
                    )
                logger.info("[%s] Fetched %d emails server-side", session_id[:12], len(_emails))
            except RuntimeError as _email_err:
                # No Gmail credentials — tell the brain so it can explain
                _email_data_ctx = (
                    "\n\n[EMAIL ERROR]\n"
                    f"Gmail is not set up yet: {_email_err}\n"
                    "Tell the user they need to sign in with Google on the Vessence web UI "
                    "to enable email access. The sign-in page is at their Jane web URL.\n"
                    "[END EMAIL ERROR]"
                )
                logger.warning("[%s] Email fetch failed (no credentials): %s",
                               session_id[:12], _email_err)
            except Exception as _email_err:
                _email_data_ctx = (
                    "\n\n[EMAIL ERROR]\n"
                    f"Failed to fetch emails: {_email_err}\n"
                    "Apologize and suggest trying again.\n"
                    "[END EMAIL ERROR]"
                )
                logger.error("[%s] Email fetch failed: %s", session_id[:12], _email_err)
            # Inject email data into the brain message
            if _email_data_ctx:
                message = message + _email_data_ctx
        elif _classification == "shopping_list":
            # Shopping list intent — handle add/remove directly, delegate queries to brain.
            logger.info("[%s] Gemma router: shopping_list action='%s'", session_id[:12], _router_response)
            from agent_skills.shopping_list import add_item, remove_item, clear_list, get_all_lists, format_for_context as _fmt_shopping
            _action = (_router_response or "").lower().strip()
            if _action.startswith("add "):
                _item = _action[4:].strip()
                # Detect store name: "add X to costco" or "add X to the costco list"
                _store = "default"
                for _kw in (" to costco", " to the costco", " to walmart", " to the walmart",
                            " to grocery", " to the grocery", " to target", " to the target"):
                    if _kw in _item.lower():
                        _store = _kw.split("to ")[-1].strip().rstrip(" list").strip()
                        _item = _item[:_item.lower().index(_kw)].strip()
                        break
                _updated = add_item(_item, _store)
                _list_display = ", ".join(_updated) if _updated else "(empty)"
                _router_response = f"Added **{_item}** to the {_store} list. Current list: {_list_display}"
                _gemma_short_circuit = True
            elif _action.startswith("remove "):
                _item = _action[7:].strip()
                _store = "default"
                for _kw in (" from costco", " from the costco", " from walmart", " from grocery"):
                    if _kw in _item.lower():
                        _store = _kw.split("from ")[-1].strip().rstrip(" list").strip()
                        _item = _item[:_item.lower().index(_kw)].strip()
                        break
                _updated = remove_item(_item, _store)
                _list_display = ", ".join(_updated) if _updated else "(empty)"
                _router_response = f"Removed **{_item}** from the {_store} list. Current list: {_list_display}"
                _gemma_short_circuit = True
            elif _action.startswith("clear"):
                _store = _action.replace("clear", "").strip() or "default"
                clear_list(_store)
                _router_response = f"Cleared the {_store} shopping list."
                _gemma_short_circuit = True
            else:
                # Show/check/query — delegate to brain with list in context
                _shopping_list_active = True
        elif _classification == "self_handle" and _router_response:
            # Only short-circuit for weather (Gemma has cached data) and STT garbage.
            # Everything else goes to Opus for a smarter response.
            _resp_lower = (_router_response or "").lower()
            if ("°f" in _resp_lower or "°c" in _resp_lower or "weather" in _resp_lower
                    or "a high of" in _resp_lower or "air quality" in _resp_lower
                    or "was that meant for me" in _resp_lower):
                _gemma_short_circuit = True
                logger.info("[%s] Gemma router: self_handle (weather/stt) — short-circuiting", session_id[:12])
            else:
                # Delegate to Opus for greetings, math, trivia, etc.
                _gemma_short_circuit = False
                _gemma_delegate_ack = _router_response
                logger.info("[%s] Gemma router: self_handle → delegating to Opus", session_id[:12])
        else:
            logger.info("[%s] Gemma router: %s → Claude", session_id[:12], _classification)
            _gemma_delegate_ack = _router_response  # None if gemma4 didn't produce one
            if _gemma_delegate_ack and not _suppress_delegate_ack:
                # Voice mode: emit the ack so the user hears something while Opus thinks.
                _raw_emit("model", ROUTER_MODEL)
                _raw_emit("ack", _gemma_delegate_ack)
                _ack_seen = True  # suppress Claude's [ACK] block since Gemma already acked
                logger.info("[%s] Gemma router: delegate ack emitted: %s", session_id[:12], _gemma_delegate_ack[:60])
            elif _gemma_delegate_ack and _suppress_delegate_ack:
                # Text mode: classification happened (for routing) but ack is suppressed.
                # Don't set _ack_seen — let Claude produce its own [ACK] naturally.
                logger.info("[%s] Gemma router: delegate (ack suppressed, text mode): %s", session_id[:12], _gemma_delegate_ack[:60])
            else:
                logger.info("[%s] Gemma router: no ack — letting Claude handle it", session_id[:12])
    except _SkipRouterSignal:
        pass  # intentional skip (open SMS draft); no warning
    except Exception as _router_err:
        logger.warning("[%s] Gemma router failed: %s — letting Claude handle ack", session_id[:12], _router_err)

    if _gemma_short_circuit:
        # Gemma handled it — emit model label, response, and done event.
        _raw_emit("model", ROUTER_MODEL)
        if _gemma_conversation_end:
            _raw_emit("conversation_end", "true")
        for _v2_ct in _gemma_client_tools:
            _raw_emit("client_tool_call", json.dumps(
                {"name": _v2_ct["name"], "args": _v2_ct.get("args", {})},
                ensure_ascii=True,
            ))
        _raw_emit("delta", _router_response)
        _raw_emit("done", _router_response)
        broadcaster.finish(_router_response)
        user_turn = {"role": "user", "content": persisted_user_message}
        # Tag Gemma-handled turns so the standing brain knows it didn't see them.
        # Without this tag, [Recent exchanges] includes turns Claude never processed,
        # causing its internal conversation memory to diverge from the injected history.
        assistant_turn = {"role": "assistant", "content": _router_response, "handler": "gemma"}
        state.history.extend([user_turn, assistant_turn])
        state.history = state.history[-24:]
        _persist_turns_async(
            session_id, state.conv_manager,
            user_turn, assistant_turn,
            persisted_user_message, _router_response,
        )
        total_ms = int((time.perf_counter() - request_start) * 1000)
        logger.info("[%s] Gemma short-circuit complete in %dms, response=%d chars",
                    session_id[:12], total_ms, len(_router_response))
        _log_stage(session_id, "request_total", request_start, mode="gemma_short_circuit")
        # Yield the queued events as JSON lines (same format as normal stream)
        while not queue.empty():
            evt_type, evt_payload = queue.get_nowait()
            yield json.dumps({"type": evt_type, "data": evt_payload}, ensure_ascii=True) + "\n"
        if _gate_acquired:
            state.request_gate.release()
            _gate_acquired = False
        return

    # Register emitter with permission broker so tool-approval requests
    # can be relayed to this SSE stream in real time.
    from jane_web.permission_broker import get_permission_broker
    _permission_broker = get_permission_broker()
    _permission_broker.register_emitter(session_id, emit)

    brain_stop = asyncio.Event()

    async def _emit_keepalive(stop: asyncio.Event, interval: float = 15.0) -> None:
        """Send periodic heartbeat events to keep the HTTP stream alive through
        proxies, mobile NATs, Cloudflare, etc.

        Previously this emitted an empty-string payload. Some middleboxes
        (especially mobile carrier NATs) buffer or drop empty-data SSE events
        at the chunked-encoding boundary, meaning the keepalive never reaches
        the client and the connection silently ages out of the client's read
        timeout. We now include a small non-empty payload (timestamp +
        sequence number) so every heartbeat guarantees real bytes on the wire.
        """
        _seq = 0
        while not stop.is_set():
            await asyncio.sleep(interval)
            if not stop.is_set():
                _seq += 1
                emit("heartbeat", f"{int(time.time())}:{_seq}")

    async def run_pipeline_async() -> None:
        nonlocal final_response
        stage_start = time.perf_counter()
        try:
            stage_start = time.perf_counter()
            summary_text = format_session_summary(load_session_summary(session_id))
            _log_stage(session_id, "session_summary_load", stage_start, summary_chars=len(summary_text or ""))
            await _await_prewarm_if_running(session_id, state)
            if summary_text:
                emit("status", "Loaded prior conversation summary.")
            else:
                emit("status", "No prior conversation summary yet. Building context from the latest message.")

            emit("status", "Loading memory and building context...")
            request_ctx = None

            # ── Map Gemma classification → intent_level + tool_context ──
            # This determines how heavy the context build is. Tool turns get
            # minimal context (no memory, no history) + only the relevant tool
            # rules. Data turns (read email/messages) get pre-fetched data but
            # no tool protocols. Full turns get everything.
            from context_builder.v1.context_builder import CLASSIFICATION_TO_INTENT
            _intent_level, _tool_context = CLASSIFICATION_TO_INTENT.get(
                (_classification or "").lower(),
                (None, None),  # default: full context
            )
            if _intent_level:
                logger.info("[%s] Intent mapping: %s → intent_level=%s",
                            session_id[:12], _classification, _intent_level)

            # Standing brain with existing session: skip expensive context build
            # (context was sent on first turn, CLI remembers it)
            from llm_brain.v1.standing_brain import get_standing_brain_manager
            manager = get_standing_brain_manager()
            _sb_brain = manager.brain
            _skip_context = (
                manager._started
                and _sb_brain
                and _sb_brain.alive
                and _sb_brain.turn_count > 0
            )

            ctx_stage_start = time.perf_counter()
            if _skip_context:
                from context_builder.v1.context_builder import JaneRequestContext, _format_recent_history, TTS_SPOKEN_BLOCK_INSTRUCTION
                safety_parts = []
                # For tool_mode/data_mode, skip recent history — it's not needed
                # for mechanical tool execution and wastes tokens.
                if _intent_level in ("tool_mode", "data_mode"):
                    pass  # no recent history for tool turns
                else:
                    recent = _format_recent_history(list(state.history), max_turns=6, max_chars=2400)
                    if recent:
                        # Check if any recent turns were handled by Gemma (not by this brain).
                        # The brain's internal memory won't have those turns, so we must tell it
                        # to trust [Recent exchanges] as the authoritative conversation record.
                        _recent_history_slice = state.history[-6:]
                        _has_gemma_turns = any(
                            h.get("handler") == "gemma" for h in _recent_history_slice
                        )
                        if _has_gemma_turns:
                            safety_parts.append(
                                f"[Recent exchanges]\n{recent}\n\n"
                                "IMPORTANT: Some recent exchanges above were handled by the fast "
                                "router (not by you), so they won't be in your conversation memory. "
                                "Trust this [Recent exchanges] block as the authoritative record of "
                                "what the user said and what was answered. Respond to the user's "
                                "CURRENT message below, not to an earlier one from your memory."
                            )
                        else:
                            safety_parts.append(f"[Recent exchanges]\n{recent}")
                # Retrieve fresh memory from ChromaDB for EVERY standing brain turn
                # (not just turn 1). Without this, Jane has no memory of who the user
                # is, their preferences, or context — making her feel "dumb."
                if _intent_level not in ("tool_mode", "data_mode", "greeting"):
                    try:
                        from context_builder.v1.context_builder import _safe_get_memory_summary
                        _sb_memory = _safe_get_memory_summary(
                            message,
                            conversation_summary=summary_text or "",
                            session_id=session_id,
                            fallback_summary=state.bootstrap_memory_summary or "",
                        )
                        if _sb_memory and _sb_memory != "No relevant context found.":
                            safety_parts.append(f"[Retrieved Memory]\n{_sb_memory}")
                            if not state.bootstrap_memory_summary:
                                state.bootstrap_memory_summary = _sb_memory
                    except Exception as _mem_err:
                        logger.warning("[%s] Standing brain memory retrieval failed: %s", session_id[:12], _mem_err)
                # Re-inject TTS instruction on every turn when TTS is active,
                # since the standing brain only got the system prompt on turn 1
                # and the user may have toggled TTS on mid-session.
                if tts_enabled:
                    safety_parts.append(f"[TTS MODE ACTIVE]\n{TTS_SPOKEN_BLOCK_INSTRUCTION}")
                # Inject tool-specific context for tool_mode turns
                if _tool_context:
                    safety_parts.append(_tool_context)
                safety_ctx = "\n\n".join(safety_parts)
                user_msg, _cm_loaded = _maybe_prepend_code_map(message)
                if _cm_loaded:
                    emit("status", "Loading code map for code-related query...")
                    logger.info("[%s] Code map injected (standing brain stream)", session_id[:12])
                transcript = f"{safety_ctx}\n\nUser: {user_msg}" if safety_ctx else user_msg
                # If Gemma already emitted a quick ack, tell Claude so it can follow up naturally
                if _gemma_delegate_ack:
                    transcript += f'\n\n[ALREADY SPOKEN] A brief acknowledgment was already spoken to the user: "{_gemma_delegate_ack}" — do NOT repeat it or generate your own [ACK] block. Continue naturally from where that ack left off.'
                request_ctx = JaneRequestContext(
                    system_prompt="",
                    transcript=transcript,
                    retrieved_memory_summary=state.bootstrap_memory_summary or "",
                )
                _log_stage(
                    session_id,
                    "context_build",
                    ctx_stage_start,
                    system_prompt_chars=0,
                    transcript_chars=len(transcript),
                    fresh_memory_retrieval=False,
                    bootstrap_summary_chars=0,
                )
                logger.info("[%s] Standing brain turn %d — injected recent history only", session_id[:12], _sb_brain.turn_count)
            elif _shopping_list_active:
                # Shopping list mode: inject list data as file_context, skip ChromaDB
                from agent_skills.shopping_list import format_for_context as _fmt_shopping
                _shopping_ctx = _fmt_shopping()
                _shopping_file_ctx = (
                    f"## Shopping Lists\n{_shopping_ctx}\n\n"
                    "You can add/remove items, show lists, or answer questions about them. "
                    "When modifying the list, tell the user what you did and show the updated list."
                )
                if resolved_file_context:
                    _shopping_file_ctx = f"{resolved_file_context}\n\n{_shopping_file_ctx}"
                request_ctx = await build_jane_context_async(
                    message,
                    list(state.history),
                    file_context=_shopping_file_ctx,
                    conversation_summary=summary_text,
                    session_id=session_id,
                    enable_memory_retrieval=False,  # skip ChromaDB for speed
                    memory_summary_fallback=state.bootstrap_memory_summary or "",
                    platform=platform,
                    tts_enabled=tts_enabled,
                    on_status=lambda s: emit("status", s),
                )
                logger.info("[%s] Shopping list context injected, ChromaDB skipped", session_id[:12])
            else:
                _memory_fallback = state.bootstrap_memory_summary or get_prefetch_result(session_id)
                # For tool_mode/data_mode, skip memory retrieval entirely
                _enable_memory = _intent_level not in ("tool_mode", "data_mode", "greeting")
                request_ctx = await build_jane_context_async(
                    message,
                    list(state.history),  # snapshot copy — prevents race with concurrent writes
                    file_context=resolved_file_context,
                    conversation_summary=summary_text,
                    session_id=session_id,
                    enable_memory_retrieval=_enable_memory,
                    memory_summary_fallback=_memory_fallback,
                    platform=platform,
                    tts_enabled=tts_enabled,
                    intent_level=_intent_level,
                    tool_context=_tool_context,
                    on_status=lambda s: emit("status", s),
                )

            # If Gemma already emitted a quick ack, inject context so Claude follows up naturally
            from context_builder.v1.context_builder import JaneRequestContext as _JRC
            if _gemma_delegate_ack and request_ctx:
                _ack_note = f'\n\n[ALREADY SPOKEN] A brief acknowledgment was already spoken to the user: "{_gemma_delegate_ack}" — do NOT repeat it or generate your own [ACK] block. Continue naturally from where that ack left off.'
                if request_ctx.transcript:
                    request_ctx = _JRC(
                        system_prompt=request_ctx.system_prompt,
                        transcript=request_ctx.transcript + _ack_note,
                        retrieved_memory_summary=request_ctx.retrieved_memory_summary,
                    )
                elif request_ctx.system_prompt:
                    request_ctx = _JRC(
                        system_prompt=request_ctx.system_prompt + _ack_note,
                        transcript=request_ctx.transcript,
                        retrieved_memory_summary=request_ctx.retrieved_memory_summary,
                    )

            if request_ctx.retrieved_memory_summary:
                state.bootstrap_memory_summary = request_ctx.retrieved_memory_summary
            state.bootstrap_complete = True
            _log_stage(
                session_id,
                "context_build",
                ctx_stage_start,
                system_prompt_chars=len(request_ctx.system_prompt or ""),
                transcript_chars=len(request_ctx.transcript or ""),
                fresh_memory_retrieval=True,
                bootstrap_summary_chars=len(state.bootstrap_memory_summary or ""),
            )
            _dump_prompt(
                session_id,
                "stream",
                message,
                summary_text,
                request_ctx,
                False,
                state.bootstrap_memory_summary,
                resolved_file_context,
            )

            emit("status", _progress_snapshot(request_ctx, summary_text, resolved_file_context))

            # ── Execution path selection ──────────────────────────────────────
            # Gemini web requests intentionally use the Gemini API brain, not
            # the standing-brain shortcut. If we let the generic standing-brain
            # path win first, a provider switch from Claude → Gemini can still
            # route the request into the manager path and produce an empty
            # response instead of using the API-backed Gemini executor.
            stage_start = time.perf_counter()
            use_standing_brain = (
                manager._started
                and manager.brain
                and manager.brain.alive
                and not _use_gemini_api(brain_name)
                and not _use_persistent_codex(brain_name)
            )
            if use_standing_brain:
                model_name = await manager.get_model()
                emit("model", model_name)
                emit("status", f"Jane is thinking ({model_name})...")
                response_parts = []
                brain_message = request_ctx.transcript if _skip_context and request_ctx.transcript else message

                _permission_broker.register_emitter("standing_brain", emit)
                try:
                    async for event_type, chunk in manager.send(
                        message=brain_message,
                        system_prompt=request_ctx.system_prompt,
                    ):
                        if event_type == "provider_error":
                            emit("provider_error", chunk)
                        elif event_type in ("thought", "tool_use", "tool_result"):
                            emit(event_type, chunk)
                        else:
                            response_parts.append(chunk)
                            emit("delta", chunk)
                finally:
                    _permission_broker.unregister_emitter("standing_brain")
                response = "".join(response_parts)
            else:
                # ── Provider-specific direct execution path ───────────────────
                if _use_gemini_api(brain_name):
                    emit("model", os.environ.get("GEMINI_MODEL", "gemini-2.5-pro"))
                    emit("status", "Handing the request to Jane's Gemini API brain.")
                elif _use_persistent_gemini(brain_name):
                    emit("model", "gemini-2.5-pro")
                    emit("status", "Handing the request to Jane's persistent Gemini brain.")
                elif _use_persistent_codex(brain_name):
                    model_name = _get_web_chat_model(brain_name)
                    emit("model", model_name)
                    emit("status", f"Handing the request to Jane's Codex brain ({model_name}).")
                else:
                    emit("model", adapter.label)
                    emit("status", f"Handing the request to Jane's {adapter.label} brain.")
                response = await _execute_brain_stream(session_id, brain_name, adapter, request_ctx, emit)
            elapsed_ms = int((time.perf_counter() - stage_start) * 1000)
            logger.info("[%s] Brain responded (stream) in %dms, %d chars", session_id[:12], elapsed_ms, len(response or ""))
            _log_stage(session_id, "brain_execute", stage_start, response_chars=len(response or ""))
            if not (response or "").strip():
                logger.warning("[%s] Brain returned empty response after %dms — emitting error instead of empty done",
                               session_id[:12], elapsed_ms)
                emit("error", "⚠️ Jane's brain returned an empty response. This usually means the model is overloaded — please try again.")
            else:
                final_response = response
                emit("done", response)
        except asyncio.CancelledError:
            elapsed_ms = int((time.perf_counter() - stage_start) * 1000)
            logger.warning(
                "[%s] Brain execution cancelled (stream) after %dms — likely client disconnect or timeout. "
                "Stack:\n%s",
                session_id[:12], elapsed_ms, traceback.format_stack(),
            )
            _log_stage(session_id, "brain_execute_cancelled", stage_start, elapsed_ms=elapsed_ms)
            emit("error", "⚠️ Jane's response stream was interrupted before completion.")
            raise
        except BrainAdapterError as exc:
            logger.error("[%s] BrainAdapterError (stream): %s", session_id[:12], exc)
            _log_stage(session_id, "brain_execute_error", stage_start, error="BrainAdapterError")
            emit("error", f"⚠️ Jane is unavailable: {exc}")
        except (ConnectionError, OSError) as exc:
            logger.warning("[%s] Connection error during brain execution: %s", session_id[:12], exc)
            _log_stage(session_id, "brain_execute_error", stage_start, error="ConnectionError")
            emit("error", "⚠️ Connection lost during response. Please try again.")
        except Exception as exc:
            if request_ctx is None:
                logger.exception("[%s] Context build failed (stream)", session_id[:12])
                _log_stage(session_id, "context_build_error", stage_start, error=type(exc).__name__)
                emit("error", f"⚠️ Jane could not prepare context for this request: {exc}")
            else:
                logger.exception("[%s] Brain execution failed (stream)", session_id[:12])
                _log_stage(session_id, "brain_execute_error", stage_start, error=type(exc).__name__)
                emit("error", f"⚠️ Error contacting Jane: {exc}")
        finally:
            brain_stop.set()
            logger.info("[%s] Jane stream pipeline task finished", _session_log_id(session_id))

    task = asyncio.create_task(run_pipeline_async())
    keepalive_task = asyncio.create_task(_emit_keepalive(brain_stop, interval=3.0))

    try:
        while True:
            queue_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                {queue_task, task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            # Only cancel the queue_task if it didn't finish — NEVER cancel the
            # adapter task, which must run to completion.
            if queue_task in pending:
                queue_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await queue_task
            if queue_task not in done:
                # Adapter task completed before a queue event was dequeued.
                # The adapter likely already put a "done" or "error" event in
                # the queue — drain it instead of injecting a false error.
                if task.done():
                    exc = task.exception()
                    if exc is not None:
                        logger.error("[%s] Stream task raised exception: %s\n%s",
                                     session_id[:12], exc, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
                        emit("error", f"⚠️ Error contacting Jane: {exc}")
                    else:
                        logger.info("[%s] Adapter task finished; draining queue for final event (qsize=%d)",
                                    session_id[:12], queue.qsize())
                    # Drain remaining events from the queue until we find
                    # "done" or "error", yielding anything in between.
                    while True:
                        try:
                            event_type, payload = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            # Queue truly empty and task finished without done/error
                            logger.warning("[%s] Stream task finished without emitting done/error (queue empty)",
                                           session_id[:12])
                            event_type, payload = "error", "⚠️ Jane stopped before finishing the response."
                        yield json.dumps({"type": event_type, "data": payload}, ensure_ascii=True) + "\n"
                        if event_type == "delta":
                            broadcaster.feed_delta(payload or "")
                        elif event_type == "done":
                            final_response = payload or ""
                            broadcaster.finish(final_response)
                            break
                        elif event_type == "error":
                            broadcaster.error(payload or "")
                            logger.warning("[%s] Stream exiting after error event (drain)", _session_log_id(session_id))
                            break
                    break
                else:
                    continue
            else:
                event_type, payload = queue_task.result()
            if not first_visible_event_logged and event_type in ("status", "delta", "done", "error"):
                _log_stage(session_id, "first_visible_event", request_start, event_type=event_type)
                first_visible_event_logged = True
            yield json.dumps({"type": event_type, "data": payload}, ensure_ascii=True) + "\n"
            if event_type == "delta":
                broadcaster.feed_delta(payload or "")
            elif event_type == "done":
                final_response = payload or ""
                broadcaster.finish(final_response)
                break
            elif event_type == "error":
                broadcaster.error(payload or "")
                logger.warning("[%s] Stream exiting after error event", _session_log_id(session_id))
                break
    finally:
        # ── Gate release: innermost try/finally so it runs even if cleanup raises ──
        # Two reasons this MUST be here and not after this block:
        #  1. When the client disconnects, Python calls aclose() on the generator.
        #     The finally block runs, but ALL code after it is skipped. If the gate
        #     release is post-finally, it never runs → gate stays locked forever.
        #  2. If anything inside this finally raises unexpectedly, a gate release
        #     placed at the end of finally would also be skipped. The nested
        #     try/finally below ensures it runs unconditionally.
        try:
            brain_stop.set()
            # NEVER cancel the adapter task — let it finish even if the client disconnected.
            # The brain is still working server-side; we need its response for history + writeback.
            if not task.done():
                logger.info("[%s] Client disconnected — waiting for adapter task to finish (brain still working)",
                            _session_log_id(session_id))
                try:
                    await asyncio.wait_for(task, timeout=300)  # 5 min max wait
                except asyncio.TimeoutError:
                    logger.warning("[%s] Adapter task still running after 5min post-disconnect, cancelling",
                                   _session_log_id(session_id))
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                except asyncio.CancelledError:
                    pass
            else:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            with contextlib.suppress(asyncio.CancelledError):
                keepalive_task.cancel()
                await keepalive_task
        finally:
            # Unconditional gate release — runs even if cleanup above raises.
            if _gate_acquired:
                state.request_gate.release()
                _gate_acquired = False
                logger.info("[%s] Gate released in finally", _session_log_id(session_id))

        # Drain any remaining events from the queue to capture final_response
        if final_response is None:
            while not queue.empty():
                try:
                    event_type, payload = queue.get_nowait()
                    if event_type == "done" and payload:
                        final_response = payload
                        break
                except asyncio.QueueEmpty:
                    break

        logger.info("[%s] Stream cleanup complete final_response=%s", _session_log_id(session_id), final_response is not None)

    # Unregister permission broker emitter
    _permission_broker.unregister_emitter(session_id)

    # Always persist if we got a response, even if client disconnected
    if final_response is None:
        logger.warning("[%s] Stream finished without final response payload", _session_log_id(session_id))
        if _gate_acquired:
            state.request_gate.release()
            _gate_acquired = False
        return

    user_turn = {"role": "user", "content": persisted_user_message}
    assistant_turn = {"role": "assistant", "content": final_response}
    state.history.extend([user_turn, assistant_turn])
    state.history = state.history[-24:]
    logger.info("[%s] Updated in-memory history to %d turns after streamed response", _session_log_id(session_id), len(state.history))

    stage_start = time.perf_counter()
    _persist_turns_async(
        session_id,
        state.conv_manager,
        user_turn,
        assistant_turn,
        persisted_user_message,
        final_response,
    )
    _log_stage(session_id, "persistence_dispatch", stage_start)
    # Log intermediary steps to request timing log
    if _intermediary_steps:
        _log_stage(session_id, "intermediary_steps", request_start,
                   step_count=len(_intermediary_steps),
                   steps="; ".join(_intermediary_steps[:20]))  # cap at 20 to avoid huge lines
    total_ms = int((time.perf_counter() - request_start) * 1000)
    logger.info("[%s] Stream request complete in %dms, response=%d chars, %d intermediary steps",
                session_id[:12], total_ms, len(final_response or ""), len(_intermediary_steps))
    _log_stage(session_id, "request_total", request_start, mode="stream")
    if _gate_acquired:
        state.request_gate.release()
        _gate_acquired = False


def _log_chat_to_work_log(user_message: str, response: str) -> None:
    """Skip chat responses — Work Log only tracks code repairs and bigger jobs."""
    pass


def get_active_brain() -> str:
    brain_name = _get_brain_name()
    return get_brain_adapter(brain_name, _get_execution_profile(brain_name)).label


def get_tunnel_url() -> str:
    domain = os.environ.get("CLOUDFLARE_DOMAIN", "")
    if domain:
        return f"https://jane.{domain}"
    return ""
