"""Jane proxy with shared context/memory and pluggable CLI brain adapters."""
import asyncio
import contextlib
import json
import logging
import os
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from agent_skills.conversation_manager import ConversationManager
from agent_skills.memory_retrieval import build_memory_sections, invalidate_memory_summary_cache
from jane.brain_adapters import BrainAdapterError, ExecutionProfile, build_execution_profile, get_brain_adapter, resolve_timeout_seconds
from jane.context_builder import build_jane_context_async
from jane.config import ENV_FILE_PATH, LOGS_DIR
from jane.persistent_gemini import get_gemini_persistent_manager
from jane.session_summary import format_session_summary, load_session_summary, update_session_summary_async
from jane_web.broadcast import StreamBroadcaster

logger = logging.getLogger("jane.proxy")


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
        from jane.gemini_api_brain import get_gemini_api_brain
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
        from jane.persistent_claude import get_claude_persistent_manager
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
        from jane.persistent_codex import get_codex_persistent_manager
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
        from jane.gemini_api_brain import get_gemini_api_brain
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
        from jane.persistent_claude import get_claude_persistent_manager
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
        from jane.persistent_codex import get_codex_persistent_manager
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
            from jane.gemini_api_brain import get_gemini_api_brain
            get_gemini_api_brain().remove_session(session_id)
            logger.info("[%s] Removed Gemini API brain session", _session_log_id(session_id))
        except Exception:
            logger.exception("[%s] Failed to remove Gemini API brain session", _session_log_id(session_id))
    if _use_persistent_codex(brain_name):
        try:
            from jane.persistent_codex import get_codex_persistent_manager
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
            from jane.persistent_claude import get_claude_persistent_manager
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

        # Thematic short-term memory update (Sonnet-powered, may take 5-15s)
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
    resolved_file_context = _resolve_file_context(state, message, file_context)
    persisted_user_message = _message_for_persistence(message, resolved_file_context)
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
    from jane.standing_brain import get_standing_brain_manager
    _sb_mgr = get_standing_brain_manager()
    _sb_bp = _sb_mgr.brain
    _skip_ctx = (
        _sb_mgr._started and _sb_bp and _sb_bp.alive and _sb_bp.turn_count > 0
    )

    stage_start = time.perf_counter()
    if _skip_ctx:
        from jane.context_builder import JaneRequestContext, _format_recent_history
        # Standing brain already has session context from turn 1's system prompt.
        # Only inject [Recent exchanges] for pronoun resolution; skip [Session context]
        # to avoid accumulating duplicate summaries across turns.
        safety_parts = []
        recent = _format_recent_history(state.history, max_turns=6, max_chars=2400)
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
        try:
            request_ctx = await build_jane_context_async(
                message,
                state.history,
                file_context=resolved_file_context,
                conversation_summary=summary_text,
                session_id=session_id,
                enable_memory_retrieval=True,
                memory_summary_fallback=_memory_fallback,
                platform=platform,
                tts_enabled=tts_enabled,
            )
        except Exception as exc:
            logger.exception("[%s] Context build failed (sync)", session_id[:12])
            _log_stage(session_id, "context_build_error", stage_start, error=type(exc).__name__)
            _sync_broadcaster.error(str(exc))
            return {"text": f"⚠️ Jane could not prepare context for this request: {exc}", "files": []}
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

    try:
        stage_start = time.perf_counter()
        response = await _execute_brain_sync(session_id, brain_name, adapter, request_ctx)
        elapsed_ms = int((time.perf_counter() - stage_start) * 1000)
        logger.info("[%s] Brain responded (sync) in %dms, %d chars", session_id[:12], elapsed_ms, len(response or ""))
        _log_stage(session_id, "brain_execute", stage_start, response_chars=len(response or ""))
    except BrainAdapterError as exc:
        logger.error("[%s] BrainAdapterError (sync): %s", session_id[:12], exc)
        _log_stage(session_id, "brain_execute_error", stage_start, error="BrainAdapterError")
        _sync_broadcaster.error(str(exc))
        return {"text": f"⚠️ Jane is unavailable: {exc}", "files": []}
    except (ConnectionError, OSError) as exc:
        logger.warning("[%s] Connection error (sync): %s", session_id[:12], exc)
        _log_stage(session_id, "brain_execute_error", stage_start, error="ConnectionError")
        _sync_broadcaster.error(str(exc))
        return {"text": "⚠️ Connection lost. Please try again.", "files": []}
    except Exception as exc:
        logger.exception("[%s] Brain execution failed (sync)", session_id[:12])
        _log_stage(session_id, "brain_execute_error", stage_start, error=type(exc).__name__)
        _sync_broadcaster.error(str(exc))
        return {"text": f"⚠️ Error contacting Jane: {exc}", "files": []}

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

    return {"text": response, "files": []}


def _detect_music_play(message: str) -> tuple[str, str, int] | None:
    """Detect 'play X' music requests and create a playlist deterministically.

    Returns (playlist_id, display_name, track_count) or None if not a music request.
    """
    import re as _re
    msg = (message or "").strip().lower()

    # Match patterns like "play the scientist", "play some coldplay", "play a random song"
    # But NOT "play the video", "play the game", etc.
    play_match = _re.match(
        r"^(?:play|put on|throw on|queue up)\s+(?:me\s+|some\s+|a\s+)?(.+?)(?:\s+(?:for me|please))?$",
        msg,
    )
    if not play_match:
        return None

    query = play_match.group(1).strip()
    # Avoid false positives on non-music requests
    non_music = {"video", "game", "movie", "clip", "episode", "show", "trailer", "youtube"}
    if any(word in query.split() for word in non_music):
        return None

    try:
        import glob, random
        from pathlib import Path
        vault_music = Path(os.environ.get("VAULT_HOME", os.path.expanduser("~/ambient/vault"))) / "Music"
        all_files = sorted(glob.glob(str(vault_music / "**" / "*.mp3"), recursive=True))
        if not all_files:
            return None

        if query in ("random", "anything", "something", "song", "music", "random song",
                     "a song", "some music", "something random"):
            selected = random.sample(all_files, min(10, len(all_files)))
            playlist_name = "Playing a random mix"
        else:
            # Search by filename
            selected = [f for f in all_files if query in f.lower().split("/")[-1].lower()]
            if not selected:
                words = query.split()
                selected = [f for f in all_files if any(w in f.lower().split("/")[-1].lower() for w in words)]
            if not selected:
                return None  # No matches — let Claude handle it (might suggest alternatives)
            playlist_name = f"Playing {query.title()}"

        # Build track list and create playlist
        from playlists import create_playlist
        tracks = []
        for filepath in selected:
            rel_path = str(Path(filepath).relative_to(vault_music.parent.parent))
            filename = Path(filepath).stem
            tracks.append({"path": rel_path, "title": filename})

        playlist = create_playlist(playlist_name, tracks)
        return (playlist["id"], playlist_name, len(tracks))
    except Exception as e:
        logger.warning("Music play detection error: %s", e)
        return None


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
            "Hey Chieh!",
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
    resolved_file_context = _resolve_file_context(state, message, file_context)
    persisted_user_message = _message_for_persistence(message, resolved_file_context)
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
        # If gemma router already emitted an ack, suppress Claude's [ACK] block.
        # If gemma didn't handle it (delegate/unknown), let Claude provide its own ack.
        _raw_emit(event_type, payload)

    emit("start")
    emit("status", "Reviewing the current thread and loading session context.")
    await asyncio.sleep(0)  # flush start+status immediately so UI isn't blank

    # ── Music play shortcut: detect "play X" and handle deterministically ──
    _music_handled = False
    _music_response = None
    try:
        _music_result = _detect_music_play(message)
        if _music_result is not None:
            playlist_id, playlist_name, track_count = _music_result
            _music_response = f"{playlist_name} ({track_count} track{'s' if track_count != 1 else ''}). [MUSIC_PLAY:{playlist_id}]"
            _music_handled = True
            logger.info("[%s] Music play shortcut: %s", session_id[:12], _music_response)
    except Exception as _music_err:
        logger.warning("[%s] Music play detection failed: %s", session_id[:12], _music_err)

    if _music_handled:
        _raw_emit("delta", _music_response)
        _raw_emit("done", _music_response)
        broadcaster.finish(_music_response)
        user_turn = {"role": "user", "content": persisted_user_message}
        assistant_turn = {"role": "assistant", "content": _music_response}
        state.history.extend([user_turn, assistant_turn])
        state.history = state.history[-24:]
        _persist_turns_async(session_id, state.conv_manager, user_turn, assistant_turn, persisted_user_message, _music_response)
        total_ms = int((time.perf_counter() - request_start) * 1000)
        logger.info("[%s] Music play complete in %dms", session_id[:12], total_ms)
        while not queue.empty():
            evt_type, evt_payload = queue.get_nowait()
            yield json.dumps({"type": evt_type, "data": evt_payload}, ensure_ascii=True) + "\n"
        return

    # Gemma4 router: classify prompt and short-circuit if self-handleable.
    # Runs async with a 2s timeout — on timeout/error, falls through to Claude.
    _gemma_short_circuit = False
    _gemma_delegate_ack = None  # quick ack emitted by Gemma when delegating to Claude
    try:
        from jane_web.gemma_router import classify_prompt, ROUTER_MODEL
        _router_history = [{"role": h["role"], "content": h.get("content", "")}
                           for h in state.history[-10:]
                           if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str)]
        _classification, _router_response = await classify_prompt(message, _router_history)
        if _classification == "self_handle" and _router_response:
            _gemma_short_circuit = True
            logger.info("[%s] Gemma router: self_handle — short-circuiting Claude", session_id[:12])
        else:
            logger.info("[%s] Gemma router: %s → Claude", session_id[:12], _classification)
            _gemma_delegate_ack = _router_response  # None if gemma4 didn't produce one
            if _gemma_delegate_ack:
                _raw_emit("model", ROUTER_MODEL)
                _raw_emit("ack", _gemma_delegate_ack)
                _ack_seen = True  # suppress Claude's [ACK] block since Gemma already acked
                logger.info("[%s] Gemma router: delegate ack emitted: %s", session_id[:12], _gemma_delegate_ack[:60])
            else:
                logger.info("[%s] Gemma router: no ack — letting Claude handle it", session_id[:12])
    except Exception as _router_err:
        logger.warning("[%s] Gemma router failed: %s — letting Claude handle ack", session_id[:12], _router_err)

    if _gemma_short_circuit:
        # Gemma handled it — emit model label, response, and done event.
        _raw_emit("model", ROUTER_MODEL)
        _raw_emit("delta", _router_response)
        _raw_emit("done", _router_response)
        broadcaster.finish(_router_response)
        user_turn = {"role": "user", "content": persisted_user_message}
        assistant_turn = {"role": "assistant", "content": _router_response}
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
        return

    # Register emitter with permission broker so tool-approval requests
    # can be relayed to this SSE stream in real time.
    from jane_web.permission_broker import get_permission_broker
    _permission_broker = get_permission_broker()
    _permission_broker.register_emitter(session_id, emit)

    brain_stop = asyncio.Event()

    async def _emit_keepalive(stop: asyncio.Event, interval: float = 15.0) -> None:
        """Send periodic heartbeat events to keep the HTTP stream alive through proxies/tunnels."""
        while not stop.is_set():
            await asyncio.sleep(interval)
            if not stop.is_set():
                emit("heartbeat", "")

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

            # Standing brain with existing session: skip expensive context build
            # (context was sent on first turn, CLI remembers it)
            from jane.standing_brain import get_standing_brain_manager
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
                from jane.context_builder import JaneRequestContext, _format_recent_history, TTS_SPOKEN_BLOCK_INSTRUCTION
                safety_parts = []
                recent = _format_recent_history(state.history, max_turns=6, max_chars=2400)
                if recent:
                    safety_parts.append(f"[Recent exchanges]\n{recent}")
                # Re-inject TTS instruction on every turn when TTS is active,
                # since the standing brain only got the system prompt on turn 1
                # and the user may have toggled TTS on mid-session.
                if tts_enabled:
                    safety_parts.append(f"[TTS MODE ACTIVE]\n{TTS_SPOKEN_BLOCK_INSTRUCTION}")
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
            else:
                _memory_fallback = state.bootstrap_memory_summary or get_prefetch_result(session_id)
                request_ctx = await build_jane_context_async(
                    message,
                    state.history,
                    file_context=resolved_file_context,
                    conversation_summary=summary_text,
                    session_id=session_id,
                    enable_memory_retrieval=True,
                    memory_summary_fallback=_memory_fallback,
                    platform=platform,
                    tts_enabled=tts_enabled,
                    on_status=lambda s: emit("status", s),
                )

            # If Gemma already emitted a quick ack, inject context so Claude follows up naturally
            from jane.context_builder import JaneRequestContext as _JRC
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
