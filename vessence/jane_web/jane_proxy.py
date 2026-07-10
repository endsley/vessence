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
from memory.v1.memory_retrieval import invalidate_memory_summary_cache
from llm_brain.v1.brain_adapters import BrainAdapterError, ExecutionProfile, build_execution_profile, get_brain_adapter, resolve_timeout_seconds
from context_builder.v1.context_builder import build_jane_context_async
from jane.config import ENV_FILE_PATH, LOGS_DIR
from jane.sanitizers import strip_client_tool_markers as _strip_client_tool_markers
from llm_brain.v1.persistent_gemini import get_gemini_persistent_manager
from jane.session_summary import format_session_summary, load_session_summary, update_session_summary_async
from jane_web.broadcast import StreamBroadcaster
from jane_web.client_tool_markers import (
    ToolMarkerExtractor,
    visible_text_and_client_tool_calls as _visible_text_and_client_tool_calls,
)
from jane_web.file_context import resolve_file_context_value
from jane_web.music_playlists import (
    extract_fallback_music_play_marker as _extract_fallback_music_play_marker,
    music_playlist_delegate_context as _music_playlist_delegate_context,
    music_playlist_delegate_error_context as _music_playlist_delegate_error_context,
    music_playlist_no_match_delegate_context as _music_playlist_no_match_delegate_context,
    music_playlist_no_match_task_context as _music_playlist_no_match_task_context,
    music_playlist_task_context as _music_playlist_task_context,
    music_playlist_task_error_context as _music_playlist_task_error_context,
    replace_music_play_marker as _replace_music_play_marker,
)
from jane_web.persistent_prompt import (
    latest_user_prompt_from_transcript as _latest_user_prompt_from_transcript,
    persistent_turn_prompt as _persistent_turn_prompt,
)
from jane_web.prefetch_cache import PrefetchMemoryCache
from jane_web.proxy_ack import pick_ack as _pick_ack
from jane_web.proxy_brain import (
    brain_name as _resolve_brain_name,
    session_log_id as _session_log_id,
    use_gemini_api as _use_gemini_api,
    use_persistent_claude as _use_persistent_claude,
    use_persistent_codex as _use_persistent_codex,
    use_persistent_gemini as _use_persistent_gemini,
    use_standing_codex as _use_standing_codex,
    web_chat_model as _get_web_chat_model,
)
from jane_web.proxy_logging import LOG_MAX_BYTES, ProxyRequestLogger
from jane_web.proxy_persistence import (
    privacy_local_only_for_class as _privacy_local_only_for_class,
    stage3_writeback_decision as _stage3_writeback_decision,
)
from jane_web.proxy_sessions import (
    global_idle_blocks_prune as _global_idle_blocks_prune,
    oldest_session_key as _oldest_session_key,
    read_global_idle_ts as _read_global_idle_ts_from_path,
    session_composite_key as _session_composite_key,
    split_session_composite_key as _split_session_composite_key,
    stale_session_expirations as _stale_session_expirations,
)
from jane_web.proxy_text import (
    message_for_persistence as _message_for_persistence,
    prepare_phone_tool_message as _prepare_phone_tool_message,
    progress_snapshot as _progress_snapshot,
)
from jane_web.router_overrides import apply_router_keyword_overrides as _apply_router_keyword_overrides
from jane_web.server_email_tools import execute_email_tool_serverside as _execute_email_tool_serverside
from jane_web.server_data_contexts import (
    calendar_delegate_context as _calendar_delegate_context,
    calendar_delegate_credentials_error_context as _calendar_delegate_credentials_error_context,
    calendar_delegate_error_context as _calendar_delegate_error_context,
    calendar_range_from_router_response as _calendar_range_from_router_response,
    calendar_task_context as _calendar_task_context,
    calendar_task_credentials_error_context as _calendar_task_credentials_error_context,
    calendar_task_error_context as _calendar_task_error_context,
    email_delegate_context as _email_delegate_context,
    email_delegate_credentials_error_context as _email_delegate_credentials_error_context,
    email_delegate_error_context as _email_delegate_error_context,
    email_read_query_from_router_response as _email_read_query_from_router_response,
    email_task_context as _email_task_context,
    email_task_credentials_error_context as _email_task_credentials_error_context,
    email_task_error_context as _email_task_error_context,
)
from jane_web.shopping_list_proxy import (
    parse_shopping_list_proxy_action as _parse_shopping_list_proxy_action,
    shopping_list_legacy_response as _shopping_list_legacy_response,
    shopping_list_v2_task_context as _shopping_list_v2_task_context,
)
from jane_web.sms_read_context import (
    SmsReadQuery as _SmsReadQuery,
    fetch_sms_readback_messages as _fetch_sms_readback_messages,
    sms_inbox_context as _sms_inbox_context,
    sms_read_error_context as _sms_read_error_context,
    sms_read_query_from_router_response as _sms_read_query_from_router_response,
    sms_task_context as _sms_task_context,
    sms_task_error_context as _sms_task_error_context,
)
from jane_web.tts_contract import (
    combine_tts_detail as _combine_tts_detail,
    enforce_tts_output_contract as _enforce_tts_output_contract,
    normalize_tts_text as _normalize_tts_text,
    split_tts_sentences as _split_tts_sentences,
    take_short_tts_spoken as _take_short_tts_spoken,
    truncate_tts_spoken_text as _truncate_tts_spoken_text,
)

logger = logging.getLogger("jane.proxy")

JANE_RESPONSE_WAIT_SECONDS = int(os.environ.get("JANE_RESPONSE_WAIT_SECONDS", "7200"))

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
SESSION_IDLE_TTL_SECONDS = max(int(os.environ.get("JANE_SESSION_IDLE_TTL_SECONDS", "1800")), 60)
_CC_ACTIVITY_PATH = Path(os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))) / "claude_code_activity.json"


def _read_global_idle_ts() -> float:
    """Last time Chieh typed at a Claude Code prompt. 0 if unknown.

    Reads claude_code_activity.json (NOT idle_state.json — that one is also
    written by jane_web on every API call, which would defer archival forever
    while Jane is in active use).
    """
    return _read_global_idle_ts_from_path(_CC_ACTIVITY_PATH, now_ts=time.time())

# ── Prefetch cache ─────────────────────────────────────────────────────────────
_prefetch_memory_cache = PrefetchMemoryCache()
_prefetch_cache = _prefetch_memory_cache.entries  # {session_id: {"result": str, "timestamp": float}}
_PREFETCH_CACHE_MAX = _prefetch_memory_cache.max_entries  # hard cap on entries to prevent unbounded growth
PREFETCH_TTL = _prefetch_memory_cache.ttl_seconds  # seconds


def run_prefetch_memory(session_id: str, user_id: str | None = None) -> None:
    """Query ChromaDB with a broad context query and cache the result for 60s.

    Called from the /api/jane/prefetch-memory endpoint. Runs the query in a
    background thread so the HTTP response returns immediately.
    """
    if _prefetch_memory_cache.is_fresh(session_id):
        logger.debug("[%s] Prefetch: still fresh, skipping", _session_log_id(session_id))
        return

    def _worker() -> None:
        start = time.perf_counter()
        try:
            query = "recent context and topics"
            from context_builder.v1.context_builder import _safe_get_memory_summary
            result = _safe_get_memory_summary(
                query,
                conversation_summary="",
                session_id=session_id,
                user_id=user_id,
            )
        except Exception:
            result = ""
        _prefetch_memory_cache.store(session_id, result)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("[%s] Prefetch memory cached in %dms (%d chars)", _session_log_id(session_id), elapsed_ms, len(result))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def get_prefetch_result(session_id: str) -> str:
    """Return a cached prefetch memory result if it is still within TTL, else ''."""
    return _prefetch_memory_cache.get(session_id)


def _get_brain_name() -> str:
    return _resolve_brain_name(env_file_path=ENV_FILE_PATH, environ=os.environ)


def _get_timeout_seconds(brain_name: str) -> int:
    return resolve_timeout_seconds(brain_name)


def _get_execution_profile(brain_name: str | None = None) -> ExecutionProfile:
    return build_execution_profile(brain_name or _get_brain_name())


def _prune_stale_sessions(now: float | None = None) -> None:
    now_ts = time.time() if now is None else now
    # Global-idle gate: only archive when Chieh is also idle in Claude Code.
    # idle_state.json is updated by ~/.claude/hooks/idle_state_hook.sh on every
    # CC prompt, so an active CC session keeps Jane archival deferred.
    global_last = _read_global_idle_ts()
    if _global_idle_blocks_prune(now_ts, global_last, SESSION_IDLE_TTL_SECONDS):
        return
    expirations = _stale_session_expirations(
        _sessions,
        now_ts=now_ts,
        ttl_seconds=SESSION_IDLE_TTL_SECONDS,
    )
    for expiration in expirations:
        logger.info(
            "[%s] Expiring idle Jane web session after %ds",
            expiration.composite_key[:12],
            expiration.idle_seconds,
        )
        if not expiration.session_id:
            # Malformed key — drop without calling end_session to avoid crash.
            _sessions.pop(expiration.composite_key, None)
            continue
        end_session(expiration.user_id, expiration.session_id)


# Providers that run through the Codex CLI (normalized name is "openai").
_CODEX_BRAINS = {"openai", "codex"}

# When the live Codex brain is exhausted, Jane fails over to this provider.
_CODEX_FAILOVER_PROVIDER = "claude"


def _is_provider_exhausted_error(exc: Exception) -> bool:
    """True when an error looks like Codex usage/quota exhaustion (vs. a normal
    failure we should just surface). Kept broad on purpose: a false positive only
    costs one extra provider attempt, a false negative leaves Jane dead."""
    text = str(exc).lower()
    signals = (
        "usage limit", "hit your usage", "ran out", "out of usage",
        "quota", "insufficient_quota", "rate limit", "rate_limit",
        "429", "resource_exhausted", "too many requests", "billing",
    )
    return any(s in text for s in signals)


def _persist_brain_provider(provider: str) -> None:
    """Switch Jane's active brain to ``provider`` in-process and in the .env so it
    survives restarts. ``brain_name()`` reads JANE_BRAIN from the .env on every
    turn, so the file is authoritative — os.environ is set too as a safety net."""
    os.environ["JANE_BRAIN"] = provider
    try:
        path = Path(ENV_FILE_PATH)
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        out: list[str] = []
        found = False
        for line in lines:
            if line.strip().replace(" ", "").startswith("JANE_BRAIN="):
                out.append(f"JANE_BRAIN={provider}")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(f"JANE_BRAIN={provider}")
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        logger.warning("Could not persist JANE_BRAIN=%s to .env: %s", provider, exc)


async def _shutdown_codex_sessions(user_id: str, session_id: str) -> None:
    """Tear down any live Codex session for this user so the exhausted CLI is
    disconnected before we spin up the failover brain."""
    try:
        from llm_brain.v1.standing_codex import get_codex_app_server_manager
        await get_codex_app_server_manager().end(user_id, session_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("standing_codex end during failover: %s", exc)
    try:
        from llm_brain.v1.persistent_codex import get_codex_persistent_manager
        await get_codex_persistent_manager().end(user_id, session_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("persistent_codex end during failover: %s", exc)


async def _failover_codex_to_claude(user_id: str, session_id: str, exc: Exception) -> None:
    """Disconnect Codex and make Claude Jane's brain (in-process + persisted)."""
    logger.warning(
        "[%s] Codex brain exhausted (%s) — disconnecting Codex and switching Jane to %s",
        session_id[:12], str(exc)[:150], _CODEX_FAILOVER_PROVIDER,
    )
    await _shutdown_codex_sessions(user_id, session_id)
    _persist_brain_provider(_CODEX_FAILOVER_PROVIDER)
    try:
        from agent_skills.work_log_tools import log_activity
        log_activity(
            f"Live brain auto-failover: Codex out of usage → switched Jane's brain to "
            f"{_CODEX_FAILOVER_PROVIDER}. Trigger: {str(exc)[:200]}",
            category="system",
        )
    except Exception:  # noqa: BLE001 — logging must never break the turn
        pass


async def _execute_brain_sync(user_id: str, session_id: str, brain_name: str, adapter, request_ctx) -> str:
    try:
        return await _dispatch_brain_sync(user_id, session_id, brain_name, adapter, request_ctx)
    except Exception as exc:  # noqa: BLE001
        if brain_name not in _CODEX_BRAINS or not _is_provider_exhausted_error(exc):
            raise
        await _failover_codex_to_claude(user_id, session_id, exc)
        return await _dispatch_brain_sync(
            user_id, session_id, _CODEX_FAILOVER_PROVIDER, adapter, request_ctx
        )


async def _execute_brain_stream(user_id: str, session_id: str, brain_name: str, adapter, request_ctx, emit) -> str:
    try:
        return await _dispatch_brain_stream(user_id, session_id, brain_name, adapter, request_ctx, emit)
    except Exception as exc:  # noqa: BLE001
        if brain_name not in _CODEX_BRAINS or not _is_provider_exhausted_error(exc):
            raise
        emit("status", "Codex is out of usage — switching Jane's brain to Claude…")
        await _failover_codex_to_claude(user_id, session_id, exc)
        return await _dispatch_brain_stream(
            user_id, session_id, _CODEX_FAILOVER_PROVIDER, adapter, request_ctx, emit
        )


async def _dispatch_brain_sync(user_id: str, session_id: str, brain_name: str, adapter, request_ctx) -> str:
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
        worker = await manager.get(user_id, session_id)
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
        session = await manager.get(user_id, session_id)
        prompt_text, _cm = _persistent_turn_prompt(
            system_prompt=request_ctx.system_prompt,
            transcript=request_ctx.transcript,
            is_fresh=session.is_fresh(),
            code_map_loader=_maybe_prepend_code_map,
        )
        if _cm:
            logger.info("[%s] Code map injected (persistent claude sync)", session_id[:12])
        return await manager.run_turn(
            user_id,
            session_id,
            prompt_text,
            timeout_seconds=profile.timeout_seconds,
            model=_get_web_chat_model(brain_name),
            yolo=profile.mode == "yolo",
        )
    if _use_standing_codex(brain_name):
        from llm_brain.v1.standing_codex import get_codex_app_server_manager
        manager = get_codex_app_server_manager()
        profile = _get_execution_profile(brain_name)
        session = await manager.get(user_id, session_id)
        prompt_text, _cm = _persistent_turn_prompt(
            system_prompt=request_ctx.system_prompt,
            transcript=request_ctx.transcript,
            is_fresh=session.is_fresh(),
            code_map_loader=_maybe_prepend_code_map,
        )
        if _cm:
            logger.info("[%s] Code map injected (standing codex sync)", session_id[:12])
        return await manager.run_turn(
            user_id,
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
        session = await manager.get(user_id, session_id)
        prompt_text, _cm = _persistent_turn_prompt(
            system_prompt=request_ctx.system_prompt,
            transcript=request_ctx.transcript,
            is_fresh=session.is_fresh(),
            code_map_loader=_maybe_prepend_code_map,
        )
        if _cm:
            logger.info("[%s] Code map injected (persistent codex sync)", session_id[:12])
        return await manager.run_turn(
            user_id,
            session_id,
            prompt_text,
            timeout_seconds=profile.timeout_seconds,
            model=_get_web_chat_model(brain_name),
            yolo=profile.mode == "yolo",
        )
    return await asyncio.to_thread(adapter.execute, request_ctx.system_prompt, request_ctx.transcript)


async def _dispatch_brain_stream(user_id: str, session_id: str, brain_name: str, adapter, request_ctx, emit) -> str:
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
        worker = await manager.get(user_id, session_id)
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
        session = await manager.get(user_id, session_id)
        prompt_text, _cm = _persistent_turn_prompt(
            system_prompt=request_ctx.system_prompt,
            transcript=request_ctx.transcript,
            is_fresh=session.is_fresh(),
            code_map_loader=_maybe_prepend_code_map,
        )
        if _cm:
            emit("status", "Loading code map for code-related query...")
            logger.info("[%s] Code map injected (persistent claude stream)", session_id[:12])
        return await manager.run_turn(
            user_id,
            session_id,
            prompt_text,
            on_delta=lambda delta: emit("delta", delta),
            on_status=lambda status: emit("status", status),
            timeout_seconds=profile.timeout_seconds,
            model=_get_web_chat_model(brain_name),
            yolo=profile.mode == "yolo",
        )
    if _use_standing_codex(brain_name):
        from llm_brain.v1.standing_codex import get_codex_app_server_manager
        manager = get_codex_app_server_manager()
        profile = _get_execution_profile(brain_name)
        session = await manager.get(user_id, session_id)
        prompt_text, _cm = _persistent_turn_prompt(
            system_prompt=request_ctx.system_prompt,
            transcript=request_ctx.transcript,
            is_fresh=session.is_fresh(),
            code_map_loader=_maybe_prepend_code_map,
        )
        if _cm:
            emit("status", "Loading code map for code-related query...")
            logger.info("[%s] Code map injected (standing codex stream)", session_id[:12])
        return await manager.run_turn(
            user_id,
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
    if _use_persistent_codex(brain_name):
        from llm_brain.v1.persistent_codex import get_codex_persistent_manager
        manager = get_codex_persistent_manager()
        profile = _get_execution_profile(brain_name)
        session = await manager.get(user_id, session_id)
        prompt_text, _cm = _persistent_turn_prompt(
            system_prompt=request_ctx.system_prompt,
            transcript=request_ctx.transcript,
            is_fresh=session.is_fresh(),
            code_map_loader=_maybe_prepend_code_map,
        )
        if _cm:
            emit("status", "Loading code map for code-related query...")
            logger.info("[%s] Code map injected (persistent codex stream)", session_id[:12])
        return await manager.run_turn(
            user_id,
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


def _get_session(user_id: str, session_id: str) -> JaneSessionState:
    _prune_stale_sessions()
    composite_key = _session_composite_key(user_id, session_id)
    state = _sessions.get(composite_key)
    if state is None:
        # Evict oldest session if at capacity. Route through end_session() so
        # the conv manager closes cleanly (final archival, DB handles, timers).
        # Raw pop() would silently drop the session and skip archival —
        # especially likely now that the global-idle gate keeps sessions
        # in the table longer.
        if len(_sessions) >= _MAX_SESSIONS:
            oldest_key = _oldest_session_key(_sessions)
            logger.info("[%s] Evicting oldest session to stay under %d cap", oldest_key[:12], _MAX_SESSIONS)
            evict_user, evict_sid = _split_session_composite_key(oldest_key)
            if evict_sid:
                try:
                    end_session(evict_user, evict_sid)
                except Exception as exc:
                    logger.warning("[%s] end_session during eviction failed: %s — falling back to raw pop", oldest_key[:12], exc)
                    _sessions.pop(oldest_key, None)
            else:
                _sessions.pop(oldest_key, None)

        state = JaneSessionState(conv_manager=ConversationManager(session_id, user_id=user_id))
        _sessions[composite_key] = state
        logger.info("[%s:%s] Created in-memory Jane session state (total=%d)", user_id[:8], _session_log_id(session_id), len(_sessions))
    elif state.conv_manager is None:
        state.conv_manager = ConversationManager(session_id, user_id=user_id)
        logger.info("[%s:%s] Recreated ConversationManager for existing session state", user_id[:8], _session_log_id(session_id))
    state.last_accessed_at = time.time()
    return state


def _resolve_file_context(state: JaneSessionState, message: str, file_context: str | None) -> str | None:
    resolved, source = resolve_file_context_value(
        message=message,
        file_context=file_context,
        recent_file_context=state.recent_file_context,
    )
    if source == "request":
        state.recent_file_context = resolved or ""
        logger.info("Resolved file context from request payload chars=%d", len(resolved or ""))
    elif source == "recent":
        logger.info("Resolved file context from recent follow-up context chars=%d", len(state.recent_file_context or ""))
    return resolved


def prewarm_session(session_id: str, user_id: str) -> None:
    state = _get_session(user_id, session_id)
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
            from context_builder.v1.context_builder import _safe_get_memory_summary
            memory_summary = _safe_get_memory_summary(
                query,
                conversation_summary=summary_text,
                session_id=session_id,
                user_id=user_id,
            )
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


def end_session(user_id: str, session_id: str) -> None:
    composite_key = _session_composite_key(user_id, session_id)
    state = _sessions.pop(composite_key, None)
    if state and state.conv_manager:
        conv_manager = state.conv_manager
        state.conv_manager = None

        def _close_conversation_manager() -> None:
            try:
                logger.info("[%s:%s] Background-closing Jane session state", user_id[:8], _session_log_id(session_id))
                conv_manager.close()
                logger.info("[%s:%s] Background session close complete", user_id[:8], _session_log_id(session_id))
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
    if _use_standing_codex(brain_name):
        try:
            from llm_brain.v1.standing_codex import get_codex_app_server_manager
            manager = get_codex_app_server_manager()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.end(user_id, session_id))
            except RuntimeError:
                def _end_codex_app_server_session():
                    try:
                        asyncio.run(asyncio.wait_for(manager.end(user_id, session_id), timeout=10))
                    except asyncio.TimeoutError:
                        logger.warning("[%s] Standing Codex shutdown timed out", _session_log_id(session_id))
                    except Exception as exc:
                        logger.error("[%s] Error in standing Codex session cleanup: %s", _session_log_id(session_id), exc)
                thread = threading.Thread(target=_end_codex_app_server_session, daemon=True)
                thread.start()
            logger.info("[%s] Ended standing Codex session", _session_log_id(session_id))
        except Exception:
            logger.exception("[%s] Failed to end standing Codex session", _session_log_id(session_id))
    if _use_persistent_codex(brain_name):
        try:
            from llm_brain.v1.persistent_codex import get_codex_persistent_manager
            manager = get_codex_persistent_manager()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.end(user_id, session_id))
            except RuntimeError:
                def _end_codex_session():
                    try:
                        asyncio.run(asyncio.wait_for(manager.end(user_id, session_id), timeout=10))
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
                loop.create_task(manager.end(user_id, session_id))
            except RuntimeError:
                # No running event loop — create one in a background thread to avoid
                # conflicts with event loops in other threads
                def _end_session():
                    try:
                        asyncio.run(asyncio.wait_for(manager.end(user_id, session_id), timeout=10))
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


_LOG_MAX_BYTES = LOG_MAX_BYTES
_proxy_request_logger = ProxyRequestLogger(REQUEST_TIMING_LOG, PROMPT_DUMP_LOG)
_truncate_log_if_needed = _proxy_request_logger.truncate_log_if_needed
_log_stage = _proxy_request_logger.log_stage
_log_start = _proxy_request_logger.log_start
_dump_prompt = _proxy_request_logger.dump_prompt


def _persist_turns_async(
    session_id: str,
    conv_manager: ConversationManager | None,
    user_turn: dict,
    assistant_turn: dict,
    user_message: str,
    assistant_message: str,
    *,
    stage: str = "stage3",
    cls: str | None = None,
    skip_fifo: bool = False,
) -> None:
    """Persist a completed turn. The scope of work depends on `stage`:

    - `stage="stage3"` (Opus answered): full pipeline. Short-term writeback
      + thematic memory update (Haiku CLI) + session summary update
      (qwen subprocess).
    - `stage="stage2"` (v2 handler short-circuit): short-term writeback
      ONLY. Thematic + session summary are Stage-3-tier work — they exist
      to index substantive Opus reasoning into Chroma for later retrieval.
      Stage 2 turns are templated canned responses ("It's 6:04 PM",
      canned greeting, "Got it, 10 minutes") — summarizing them wastes a
      subprocess fork + up to 90 s of qwen time per turn, and the
      resulting "topics" have no durable value.

    If the class metadata marks this turn as `privacy="local_only"`, the
    thematic/session-summary work is skipped unconditionally — those
    writebacks invoke cloud LLMs (Haiku) that must not see private data.
    The skip is explicit (not a Stage-2 coincidence) so future changes to
    the stage routing don't accidentally expose private content to cloud
    writeback.

    Investigation 2026-04-18: persistence-worker subprocess pressure on
    a 1.4 GB jane-web process correlated with event-loop stalls of 45-50 s.
    Gating stage3-tier work on actual stage3 routing eliminates this for
    the common case (voice Q&A handled by v2 handlers).
    """
    # Explicit privacy gate (independent of stage). Looked up once up-front
    # so the worker thread doesn't have to re-import.
    def _privacy_for_class(class_name: str) -> str:
        from agent_skills.private_handler_utils import privacy_for
        return privacy_for(class_name)

    privacy_local_only = _privacy_local_only_for_class(cls, _privacy_for_class)
    stage3_decision = _stage3_writeback_decision(
        stage,
        privacy_local_only=privacy_local_only,
    )

    def _worker() -> None:
        logger.info(
            "[%s] Persistence worker started stage=%s cls=%s user_chars=%d assistant_chars=%d",
            _session_log_id(session_id),
            stage,
            cls or "-",
            len(user_message or ""),
            len(assistant_message or ""),
        )
        try:
            stage_start = time.perf_counter()
            if conv_manager:
                conv_manager.add_messages([user_turn, assistant_turn], cls=cls)
                invalidate_memory_summary_cache(session_id)
                _log_stage(session_id, "short_term_writeback_async", stage_start)
            else:
                logger.warning("[%s] No ConversationManager available for writeback", _session_log_id(session_id))
        except Exception as exc:
            logger.exception("[%s] Short-term writeback failed", session_id[:12])
            _log_stage(session_id, "short_term_writeback_async_error", stage_start, error=type(exc).__name__)

        # FIFO write — runs for ALL stages (stage2 + stage3) so the
        # recent_turns SQLite FIFO stays current regardless of which
        # pipeline path handled the turn. Previously only v2/v3 pipeline
        # paths wrote to the FIFO; the standing brain (stage3_escalate →
        # jane_proxy) path was missing this, leaving Opus conversations
        # with zero FIFO entries.
        # Callers that already wrote to the FIFO (v2/v3 pipeline paths)
        # pass skip_fifo=True to avoid duplicate entries.
        if not skip_fifo:
            try:
                fifo_start = time.perf_counter()
                from jane_web.jane_v2.pipeline import _persist_turn_to_fifo
                _persist_turn_to_fifo(
                    session_id, user_message, assistant_message,
                    stage=stage,
                    intent=cls or "",
                )
                _log_stage(session_id, "fifo_write", fifo_start)
            except Exception as exc:
                logger.warning("[%s] FIFO write failed (non-fatal): %s", session_id[:12], exc)

        if not stage3_decision.run_stage3_writeback and stage3_decision.reason == "privacy_local_only":
            # Explicit privacy skip — class is marked local_only. Thematic
            # memory (Haiku CLI) and session summary (qwen subprocess) would
            # embed verbatim content and cannot run. Independent of stage
            # so a future reroute of a private class does not accidentally
            # send data to cloud writeback.
            _log_stage(session_id, stage3_decision.skip_log_stage, time.perf_counter())
            logger.info(
                "[%s] Persistence worker finished (privacy=local_only cls=%s — skipped thematic + summary)",
                _session_log_id(session_id), cls or "-",
            )
            return

        if not stage3_decision.run_stage3_writeback:
            # Stage 2 short-circuit — skip thematic + session summary. These
            # are for Opus-tier substantive content; Stage 2 turns are
            # handler-generated templated responses with no durable topic.
            _log_stage(session_id, stage3_decision.skip_log_stage, time.perf_counter())
            logger.info("[%s] Persistence worker finished (stage2 — skipped thematic + summary)", _session_log_id(session_id))
            return

        # Atomic short-term memory update (Haiku-powered, 1-3s typical).
        # The FIFO write happens earlier in this function for immediate
        # conversational continuity. This section writes the persistent
        # Chroma short-term note used for cross-session recent recall.
        try:
            stage_start = time.perf_counter()
            if conv_manager:
                conv_manager.update_short_term_memory(user_message, assistant_message)
                _log_stage(session_id, "short_term_memory_update_async", stage_start)
        except Exception as exc:
            logger.exception("[%s] Short-term memory update failed", session_id[:12])
            _log_stage(session_id, "short_term_memory_update_async_error", stage_start, error=type(exc).__name__)

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
    request_start = time.perf_counter()
    # Broadcast start
    _sync_broadcaster = StreamBroadcaster(broadcast_user_id, session_id, platform or "", message)
    _sync_broadcaster.start()
    state = _get_session(user_id, session_id)
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
            _sync_broadcaster, broadcast_user_id, request_start, user_id,
        )
    finally:
        if _gate_acquired:
            state.request_gate.release()


async def _send_message_inner(
    state, session_id: str, message: str, file_context: str,
    platform: str, tts_enabled: bool, _sync_broadcaster, broadcast_user_id: str,
    request_start: float, user_id: str,
) -> dict:
    """Inner send_message logic, always runs under request_gate."""
    # Phone tools: extract any [TOOL_RESULT:{json}] markers the Android client
    # prepended. Same treatment as the stream path — strip from user-visible
    # bubble, prepend a [PHONE TOOL RESULTS] block onto the brain-visible
    # message so Jane knows what the last phone-tool invocation did.
    _phone_tool_message = _prepare_phone_tool_message(message)
    _cleaned_message = _phone_tool_message.cleaned_message
    _tool_results = _phone_tool_message.tool_results
    if _tool_results:
        logger.info("[%s] (sync) received %d tool result(s) from client",
                    session_id[:12], len(_tool_results))
    _user_visible_message = _phone_tool_message.user_visible_message
    message = _phone_tool_message.brain_visible_message
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
        and not _use_gemini_api(brain_name)
        and not _use_standing_codex(brain_name)
        and not _use_persistent_codex(brain_name)
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
            user_id=user_id,
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
    response = await _execute_brain_sync(user_id, session_id, brain_name, adapter, request_ctx)
    if tts_enabled:
        response = _enforce_tts_output_contract(response, session_id, "sync")
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
        response, _sync_tool_calls = _visible_text_and_client_tool_calls(response)
        _total_sync_calls = len(_sync_tool_calls)
        if _total_sync_calls > 0:
            logger.warning(
                "[%s] (sync) response contained %d client_tool_call marker(s) "
                "that cannot be dispatched in non-streaming mode — stripped from "
                "response text",
                session_id[:12], _total_sync_calls,
            )

    try:
        from llm_brain.v1.standing_brain import get_standing_brain_manager as _get_sbm
        _notice = _get_sbm().pop_pending_notification()
        if _notice:
            response = f"{_notice}\n\n{response}"
            if tts_enabled:
                response = _enforce_tts_output_contract(response, session_id, "sync-notice")
    except Exception:
        pass

    return {"text": response, "files": []}


async def stream_message(
    user_id: str,
    session_id: str,
    message: str,
    file_context: str = None,
    platform: str = None,
    tts_enabled: bool = False,
    skip_router: bool = False,
) -> AsyncIterator[str]:
    """Stream a chat turn.

    `skip_router=True` tells this function to BYPASS its internal Stage 1
    embedding classifier + Stage 2 dispatcher and go straight to the
    final brain (Opus). jane_v2's Stage 3 escalation sets this — v2 has
    already done its own classification with stronger safeguards, and a
    second uncoordinated reclassification inside stream_message caused
    bugs like v2 correctly demoting END_CONVERSATION then v1 re-picking
    it and short-circuiting with a canned "Ok." reply.
    """
    broadcast_user_id = user_id
    request_start = time.perf_counter()
    state = _get_session(user_id, session_id)
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
    _phone_tool_message = _prepare_phone_tool_message(message)
    _cleaned_message = _phone_tool_message.cleaned_message
    _tool_results = _phone_tool_message.tool_results
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
    _brain_visible_message = _phone_tool_message.brain_visible_message  # what the brain will see
    _user_visible_message = _phone_tool_message.user_visible_message  # what the user actually typed
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
    # TTS-latency debug instrumentation. These track the gap between the last
    # delta the client sees and the done event that triggers TTS on Android.
    _tts_first_delta_logged = False
    _tts_last_delta_time: float | None = None

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
        nonlocal _ack_seen, _accumulated_deltas, _tts_first_delta_logged, _tts_last_delta_time
        # TTS-latency debug: stamp first delta and keep rolling "last delta" time.
        if event_type == "delta" and payload:
            _tts_last_delta_time = time.perf_counter()
            if not _tts_first_delta_logged:
                _tts_first_delta_logged = True
                _log_stage(session_id, "tts_first_delta", request_start, chars=len(payload))
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
            # TTS-latency debug: stamp when the done-event processing starts
            # and how long since the last delta the client saw. The gap between
            # tts_last_delta_seen (below) and tts_done_raw_emit is where
            # post-text server work lives (tool flush, music fallback, etc.).
            _log_stage(session_id, "tts_done_emit_start", request_start,
                       gap_since_last_delta_ms=(
                           int((time.perf_counter() - _tts_last_delta_time) * 1000)
                           if _tts_last_delta_time is not None else -1))
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
            _music_marker = _extract_fallback_music_play_marker(payload)
            if _music_marker:
                logger.info("[%s] Opus music fallback: creating playlist for query '%s'",
                            session_id[:12], _music_marker.query[:60])
                try:
                    from jane_web.main import create_music_playlist_from_query
                    _fb_playlist = create_music_playlist_from_query(_music_marker.query)
                    if _fb_playlist:
                        payload = _replace_music_play_marker(payload or "", _music_marker, _fb_playlist["id"])
                        logger.info("[%s] Opus music fallback: replaced with playlist id=%s (%d tracks)",
                                    session_id[:12], _fb_playlist['id'], len(_fb_playlist.get('tracks', [])))
                    else:
                        logger.info("[%s] Opus music fallback: no matches for '%s'",
                                    session_id[:12], _music_marker.query[:60])
                except Exception as _fb_err:
                    logger.warning("[%s] Opus music fallback failed: %s", session_id[:12], _fb_err)

        # If gemma router already emitted an ack, suppress Claude's [ACK] block.
        # If gemma didn't handle it (delegate/unknown), let Claude provide its own ack.

        # Strip [[CLIENT_TOOL:...]] markers from the done payload so Android
        # TTS never speaks raw tool syntax.  Delta events are already stripped
        # by _tool_extractor above, but the done event carries the full raw
        # response text — Android uses done.data for TTS when present.
        if event_type == "done" and payload and "[[CLIENT_TOOL:" in payload:
            payload, _ = _visible_text_and_client_tool_calls(payload)
        # Always strip orphan trailing `]]` from the done payload — Opus
        # occasionally emits an extra `]]` past the real marker close.
        # (See 2026-04-20 08:48:02: "Message sent. ]]" landed in the ledger.)
        if event_type == "done" and payload:
            payload = ToolMarkerExtractor._strip_orphan_close(payload)

        if event_type == "done":
            _log_stage(session_id, "tts_done_raw_emit", request_start,
                       payload_chars=len(payload or ""))

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
    _stage2_delegate_ack = None  # quick ack emitted by Stage 2 when delegating to Claude
    _gemma_conversation_end = False  # v2 pipeline: END_CONVERSATION signal to client
    _gemma_client_tools = []  # v2 pipeline: client tool calls from Stage 2 fast path
    _shopping_list_active = False  # set by shopping_list classification
    # Always initialize _classification so run_pipeline_async() can access it as a
    # free variable even when the v2 pipeline is used and the old pipeline is skipped.
    _classification = None
    try:
        if skip_router:
            # Caller (jane_v2 Stage 3 escalation) already classified and
            # wants us to go straight to Opus — don't rerun classifier.
            raise _SkipRouterSignal()
        if _skip_initial_ack:
            # Fall-through sentinel: raise a silent skip marker caught below.
            raise _SkipRouterSignal()
        if os.environ.get("JANE_USE_V2_PIPELINE") == "1":
            # ── v2 pipeline: Stage 1 classify → build context → Stage 2 execute ────
            from intent_classifier.v2.classifier import stage1_classify as _s1_fn
            from intent_classifier.v1.gemma_stage2 import stage2_execute as _s2_fn
            ROUTER_MODEL = "embedding-v2"
            # ── Stage 0: exact-match lookup (zero LLM cost) ──────────────────
            from jane_web._stage0_singleton import stage0 as _s0
            _s0_hit = _s0.classify(message or "")
            if _s0_hit:
                logger.info("[%s] Stage0 exact match: %r -> %s", session_id[:12], (message or "")[:60], _s0_hit)
                _stage1 = {"classification": _s0_hit, "confidence": 1.0, "margin": 1.0, "stage0": True}
            else:
                _stage1 = await _s1_fn(message, session_id)
            _s1_cls = _stage1.get("classification", "DELEGATE_OPUS")
            # END_CONVERSATION is destructive: it short-circuits the brain,
            # replies "Ok.", and tells clients to end active listening. The
            # jane_v2 wrapper already requires an 0.80 floor, but this proxy
            # path calls the raw embedding classifier directly, so duplicate
            # the wrapper's safety gates here.
            if _s1_cls == "END_CONVERSATION":
                try:
                    from jane_web.jane_v2.stage1_classifier import _end_conversation_phrase_ok
                    _end_phrase_ok = _end_conversation_phrase_ok(message)
                except Exception:
                    _end_phrase_ok = True
                _end_conf = float(_stage1.get("confidence") or 0.0)
                if not _end_phrase_ok:
                    logger.info(
                        "[%s] v2 END_CONVERSATION phrase guard rejected %r — delegating",
                        session_id[:12], (message or "")[:100],
                    )
                    _s1_cls = "DELEGATE_OPUS"
                    _stage1["classification"] = _s1_cls
                elif _end_conf < 0.80:
                    logger.info(
                        "[%s] v2 END_CONVERSATION confidence %.2f below safety floor — delegating",
                        session_id[:12], _end_conf,
                    )
                    _s1_cls = "DELEGATE_OPUS"
                    _stage1["classification"] = _s1_cls
            _stage1["classification"] = _s1_cls
            # Sync _classification so run_pipeline_async()'s CLASSIFICATION_TO_INTENT
            # lookup works for v2 pipeline turns that delegate to Opus.
            _classification = _s1_cls.lower()
            # ── Build task context (fetch data for data-intensive intents) ─────────
            _v2_task_ctx = ""
            if _s1_cls == "READ_MESSAGES":
                _stage2_delegate_ack = "Checking your messages..."
                try:
                    from vault_web.database import get_db as _v2_get_db
                    _v2_filter = _stage1.get("filter", "")
                    _v2_query = _SmsReadQuery(days=5, limit=30, sender_filter=_v2_filter or None)
                    with _v2_get_db() as _v2c:
                        _v2_msgs = _fetch_sms_readback_messages(_v2c, _v2_query)
                    _v2_task_ctx = _sms_task_context(_v2_msgs)
                    logger.info("[%s] v2 READ_MESSAGES: fetched %d msgs%s",
                                session_id[:12], len(_v2_msgs),
                                f" (filter: {_v2_filter})" if _v2_filter else "")
                except Exception as _v2_sms_err:
                    logger.error("[%s] v2 SMS fetch failed: %s", session_id[:12], _v2_sms_err)
                    _v2_task_ctx = _sms_task_error_context(_v2_sms_err)
            elif _s1_cls == "READ_EMAIL":
                _stage2_delegate_ack = "Let me check your email..."
                try:
                    from agent_skills.email_tools import read_inbox as _v2_read_inbox
                    _v2_emails = _v2_read_inbox(limit=10, query="is:unread")
                    _v2_task_ctx = _email_task_context(_v2_emails)
                    logger.info("[%s] v2 READ_EMAIL: fetched %d emails", session_id[:12], len(_v2_emails) if _v2_emails else 0)
                except RuntimeError as _v2_email_err:
                    _v2_task_ctx = _email_task_credentials_error_context(_v2_email_err)
                except Exception as _v2_email_err:
                    logger.error("[%s] v2 email fetch failed: %s", session_id[:12], _v2_email_err)
                    _v2_task_ctx = _email_task_error_context(_v2_email_err)
            elif _s1_cls == "READ_CALENDAR":
                _stage2_delegate_ack = "Let me check your calendar..."
                _v2_range = (_stage1.get("range") or "today").strip()
                try:
                    from agent_skills.calendar_tools import list_events_in_range as _v2_list_cal
                    _v2_events = _v2_list_cal(_v2_range, max_results=25)
                    _v2_task_ctx = _calendar_task_context(_v2_events, _v2_range)
                    logger.info("[%s] v2 READ_CALENDAR: fetched %d events (range=%s)",
                                session_id[:12], len(_v2_events) if _v2_events else 0, _v2_range)
                except RuntimeError as _v2_cal_err:
                    _v2_task_ctx = _calendar_task_credentials_error_context(_v2_cal_err)
                except Exception as _v2_cal_err:
                    logger.error("[%s] v2 calendar fetch failed: %s", session_id[:12], _v2_cal_err)
                    _v2_task_ctx = _calendar_task_error_context(_v2_cal_err)
            elif _s1_cls == "MUSIC_PLAY":
                _v2_query = _stage1.get("query", "")
                _stage2_delegate_ack = f"Playing {_v2_query}..." if _v2_query else "Playing music..."
                try:
                    from jane_web.main import create_music_playlist_from_query as _v2_pl_fn
                    _v2_pl = _v2_pl_fn(_v2_query)
                    if _v2_pl and _v2_pl.get("tracks"):
                        _v2_task_ctx = _music_playlist_task_context(_v2_pl)
                    else:
                        _v2_task_ctx = _music_playlist_no_match_task_context()
                except Exception as _v2_music_err:
                    logger.warning("[%s] v2 music playlist failed: %s", session_id[:12], _v2_music_err)
                    _v2_task_ctx = _music_playlist_task_error_context(_v2_music_err)
            elif _s1_cls == "SHOPPING_LIST":
                try:
                    from agent_skills.shopping_list import (
                        add_item as _v2_add_item,
                        remove_item as _v2_rm_item,
                        clear_list as _v2_clear_list,
                    )
                    _v2_action = _parse_shopping_list_proxy_action(_stage1.get("action"))
                    if _v2_action and _v2_action.kind == "add":
                        _v2_updated = _v2_add_item(_v2_action.item, _v2_action.store)
                        _v2_task_ctx = _shopping_list_v2_task_context(_v2_action, _v2_updated)
                    elif _v2_action and _v2_action.kind == "remove":
                        _v2_updated = _v2_rm_item(_v2_action.item, _v2_action.store, confidence=1.0)
                        _v2_task_ctx = _shopping_list_v2_task_context(_v2_action, _v2_updated)
                    elif _v2_action and _v2_action.kind == "clear":
                        _v2_clear_list(_v2_action.store, confidence=1.0)
                        _v2_task_ctx = _shopping_list_v2_task_context(_v2_action)
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
                _stage2_delegate_ack = _stage2.get("response") or _stage2_delegate_ack
                # If no specific ack, generate a topic-aware one via qwen.
                # Previously picked one of 6 generic strings ("Hmm.", "One sec.",
                # ...), which user flagged as often feeling disconnected from
                # the actual request. _generate_delegate_ack uses the user's
                # message to produce something like "Let me check your email,
                # one sec." Falls back to a static string on LLM failure.
                if not _stage2_delegate_ack and not _suppress_delegate_ack:
                    try:
                        from jane_web.jane_v2.pipeline import _generate_delegate_ack as _v2_gen_ack
                        _stage2_delegate_ack = await _v2_gen_ack(
                            message, session_id, cls=_s1_cls or "others",
                        )
                    except Exception as _ack_err:
                        logger.warning("[%s] topic-aware ack generation failed (%s) — static fallback",
                                       session_id[:12], _ack_err)
                        _stage2_delegate_ack = "One sec, let me look into that."
                # Inject delegate context into message so Opus sees it
                _v2_dctx = _stage2.get("delegate_context", "") or _v2_task_ctx
                if _v2_dctx:
                    message = message + "\n\n" + _v2_dctx
                if _stage2_delegate_ack and not _suppress_delegate_ack:
                    _raw_emit("model", ROUTER_MODEL)
                    _raw_emit("ack", _stage2_delegate_ack)
                    _ack_seen = True
                    logger.info("[%s] v2 delegate ack: %s", session_id[:12], (_stage2_delegate_ack or "")[:60])
                elif _stage2_delegate_ack and _suppress_delegate_ack:
                    logger.info("[%s] v2 delegate (ack suppressed, text mode): %s",
                                session_id[:12], (_stage2_delegate_ack or "")[:60])
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
        _keyword_override = _apply_router_keyword_overrides(_classification, _router_response, message)
        for _old_classification, _new_classification in _keyword_override.changes:
            logger.info(
                "[%s] Keyword override: %s → %s",
                session_id[:12],
                _old_classification,
                _new_classification,
            )
        _classification = _keyword_override.classification
        _router_response = _keyword_override.response
        if _classification == "music_play" and _router_response:
            # Music: delegate to Opus for nuanced handling (e.g., "play something
            # relaxing", "skip the piano tutorials"). Server pre-creates the playlist
            # so Opus can reference it, but Opus decides the response.
            logger.info("[%s] Gemma router: music_play query='%s' → delegating to Opus",
                        session_id[:12], _router_response)
            _stage2_delegate_ack = f"Playing {_router_response}..."
            _gemma_short_circuit = False
            try:
                from jane_web.main import create_music_playlist_from_query
                playlist = create_music_playlist_from_query(_router_response)
                if playlist is not None and len(playlist.get("tracks", [])) > 0:
                    message = message + _music_playlist_delegate_context(playlist)
                else:
                    message = message + _music_playlist_no_match_delegate_context()
            except Exception as _music_err:
                logger.warning("[%s] Music playlist creation failed: %s", session_id[:12], _music_err)
                message = message + _music_playlist_delegate_error_context(_music_err)
        elif _classification == "read_messages":
            # Read messages server-side from synced_messages DB (synced by Android).
            # Same pattern as read_email: inject data into the brain context.
            logger.info("[%s] Gemma router: read_messages → fetching from synced DB",
                        session_id[:12])
            _stage2_delegate_ack = "Checking your messages..."
            _gemma_short_circuit = False
            _sms_data_ctx = ""
            try:
                from vault_web.database import get_db as _get_sms_db
                # Parse optional sender filter from router response
                _sms_query = _sms_read_query_from_router_response(_router_response)
                with _get_sms_db() as _sms_conn:
                    _sms_list = _fetch_sms_readback_messages(_sms_conn, _sms_query)

                _sms_data_ctx = _sms_inbox_context(_sms_list)
                if _sms_list:
                    _sms_count = len(_sms_list)
                else:
                    _sms_count = 0
                logger.info("[%s] Fetched %d SMS messages from synced DB%s",
                            session_id[:12], _sms_count,
                            f" (filter: {_sms_query.sender_filter})" if _sms_query.sender_filter else "")
            except Exception as _sms_err:
                _sms_data_ctx = _sms_read_error_context(_sms_err)
                logger.error("[%s] SMS DB fetch failed: %s", session_id[:12], _sms_err)
            if _sms_data_ctx:
                message = message + _sms_data_ctx
        elif _classification == "sync_messages":
            # Force SMS sync: inject instruction for the brain to emit
            # [[CLIENT_TOOL:sync.force_sms:{}]] so the Android app re-syncs.
            logger.info("[%s] Gemma router: sync_messages → delegating to brain with sync tool instruction",
                        session_id[:12])
            _stage2_delegate_ack = "Syncing your messages..."
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
            _stage2_delegate_ack = "Let me check your email..."
            _gemma_short_circuit = False
            _email_data_ctx = ""
            try:
                from agent_skills.email_tools import read_inbox as _read_inbox
                # Parse limit and query from router response
                _email_query = _email_read_query_from_router_response(_router_response)
                _emails = _read_inbox(limit=_email_query.limit, query=_email_query.query)
                _email_data_ctx = _email_delegate_context(_emails)
                logger.info("[%s] Fetched %d emails server-side", session_id[:12], len(_emails))
            except RuntimeError as _email_err:
                # No Gmail credentials — tell the brain so it can explain
                _email_data_ctx = _email_delegate_credentials_error_context(_email_err)
                logger.warning("[%s] Email fetch failed (no credentials): %s",
                               session_id[:12], _email_err)
            except Exception as _email_err:
                _email_data_ctx = _email_delegate_error_context(_email_err)
                logger.error("[%s] Email fetch failed: %s", session_id[:12], _email_err)
            # Inject email data into the brain message
            if _email_data_ctx:
                message = message + _email_data_ctx
        elif _classification == "read_calendar":
            # Calendar is server-side (same OAuth grant as Gmail). Same pattern
            # as read_email: fetch events here and inject as context.
            logger.info("[%s] Gemma router: read_calendar → fetching server-side",
                        session_id[:12])
            _stage2_delegate_ack = "Let me check your calendar..."
            _gemma_short_circuit = False
            _cal_data_ctx = ""
            # Parse range hint from router response (default today) and from user msg
            _cal_range = _calendar_range_from_router_response(_router_response, message)
            try:
                from agent_skills.calendar_tools import list_events_in_range as _list_cal_range
                _cal_events = _list_cal_range(_cal_range, max_results=25)
                _cal_data_ctx = _calendar_delegate_context(_cal_events, _cal_range)
                logger.info("[%s] Fetched %d calendar events server-side (range=%s)",
                            session_id[:12], len(_cal_events), _cal_range)
            except RuntimeError as _cal_err:
                _cal_data_ctx = _calendar_delegate_credentials_error_context(_cal_err)
                logger.warning("[%s] Calendar fetch failed (no credentials): %s",
                               session_id[:12], _cal_err)
            except Exception as _cal_err:
                _cal_data_ctx = _calendar_delegate_error_context(_cal_err)
                logger.error("[%s] Calendar fetch failed: %s", session_id[:12], _cal_err)
            if _cal_data_ctx:
                message = message + _cal_data_ctx
        elif _classification == "shopping_list":
            # Shopping list intent — handle add/remove directly, delegate queries to brain.
            logger.info("[%s] Gemma router: shopping_list action='%s'", session_id[:12], _router_response)
            from agent_skills.shopping_list import add_item, remove_item, clear_list
            _action = _parse_shopping_list_proxy_action(_router_response)
            if _action and _action.kind == "add":
                _updated = add_item(_action.item, _action.store)
                _router_response = _shopping_list_legacy_response(_action, _updated)
                _gemma_short_circuit = True
            elif _action and _action.kind == "remove":
                _updated = remove_item(_action.item, _action.store, confidence=1.0)
                _router_response = _shopping_list_legacy_response(_action, _updated)
                _gemma_short_circuit = True
            elif _action and _action.kind == "clear":
                clear_list(_action.store, confidence=1.0)
                _router_response = _shopping_list_legacy_response(_action)
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
                _stage2_delegate_ack = _router_response
                logger.info("[%s] Gemma router: self_handle → delegating to Opus", session_id[:12])
        else:
            logger.info("[%s] Gemma router: %s → Claude", session_id[:12], _classification)
            _stage2_delegate_ack = _router_response  # None if Stage 2 didn't produce one
            if _stage2_delegate_ack and not _suppress_delegate_ack:
                # Voice mode: emit the ack so the user hears something while Opus thinks.
                _raw_emit("model", ROUTER_MODEL)
                _raw_emit("ack", _stage2_delegate_ack)
                _ack_seen = True  # suppress Claude's [ACK] block since Gemma already acked
                logger.info("[%s] Gemma router: delegate ack emitted: %s", session_id[:12], _stage2_delegate_ack[:60])
            elif _stage2_delegate_ack and _suppress_delegate_ack:
                # Text mode: classification happened (for routing) but ack is suppressed.
                # Don't set _ack_seen — let Claude produce its own [ACK] naturally.
                logger.info("[%s] Gemma router: delegate (ack suppressed, text mode): %s", session_id[:12], _stage2_delegate_ack[:60])
            else:
                logger.info("[%s] Gemma router: no ack — letting Claude handle it", session_id[:12])
    except _SkipRouterSignal:
        pass  # intentional skip (open SMS draft); no warning
    except Exception as _router_err:
        logger.warning("[%s] Gemma router failed: %s — letting Claude handle ack", session_id[:12], _router_err)

    if _gemma_short_circuit:
        # Gemma handled it — emit model label, response, and done event.
        _raw_emit("model", ROUTER_MODEL)
        routed_response = _router_response
        if tts_enabled:
            routed_response = _enforce_tts_output_contract(_router_response, session_id, "gemma")
        if _gemma_conversation_end:
            _raw_emit("conversation_end", "true")
        for _v2_ct in _gemma_client_tools:
            _raw_emit("client_tool_call", json.dumps(
                {"name": _v2_ct["name"], "args": _v2_ct.get("args", {})},
                ensure_ascii=True,
            ))
        _raw_emit("delta", routed_response)
        _raw_emit("done", routed_response)
        broadcaster.finish(routed_response)
        user_turn = {"role": "user", "content": persisted_user_message}
        # Tag Gemma-handled turns so the standing brain knows it didn't see them.
        # Without this tag, [Recent exchanges] includes turns Claude never processed,
        # causing its internal conversation memory to diverge from the injected history.
        assistant_turn = {"role": "assistant", "content": routed_response, "handler": "gemma"}
        state.history.extend([user_turn, assistant_turn])
        state.history = state.history[-24:]
        _persist_turns_async(
            session_id, state.conv_manager,
            user_turn, assistant_turn,
            persisted_user_message, routed_response,
            stage="stage2",
            cls=_classification,
        )
        total_ms = int((time.perf_counter() - request_start) * 1000)
        logger.info("[%s] Gemma short-circuit complete in %dms, response=%d chars",
                    session_id[:12], total_ms, len(routed_response))
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
                and not _use_gemini_api(brain_name)
                and not _use_standing_codex(brain_name)
                and not _use_persistent_codex(brain_name)
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
                            user_id=user_id,
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
                # Re-inject Standing Brain Mode override every turn so it
                # survives context compaction (the turn-0 system prompt can
                # get lost after many turns).
                safety_parts.append(
                    "[STANDING BRAIN MODE] You are the web/Android standing brain. "
                    "SKIP these CLAUDE.md sections: "
                    "Run Job Queue (unless user explicitly asks), Code Edit Lock, Review Process. "
                    "Respond directly to the user's message. No background automation."
                )
                safety_ctx = "\n\n".join(safety_parts)
                user_msg, _cm_loaded = _maybe_prepend_code_map(message)
                if _cm_loaded:
                    emit("status", "Loading code map for code-related query...")
                    logger.info("[%s] Code map injected (standing brain stream)", session_id[:12])
                transcript = f"{safety_ctx}\n\nUser: {user_msg}" if safety_ctx else user_msg
                # If Gemma already emitted a quick ack, tell Claude so it can follow up naturally
                if _stage2_delegate_ack:
                    transcript += f'\n\n[ALREADY SPOKEN] A brief acknowledgment was already spoken to the user: "{_stage2_delegate_ack}" — do NOT repeat it or generate your own [ACK] block. Continue naturally from where that ack left off.'
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
                    user_id=user_id,
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
                    user_id=user_id,
                )

            # If Gemma already emitted a quick ack, inject context so Claude follows up naturally
            from context_builder.v1.context_builder import JaneRequestContext as _JRC
            if _stage2_delegate_ack and request_ctx:
                _ack_note = f'\n\n[ALREADY SPOKEN] A brief acknowledgment was already spoken to the user: "{_stage2_delegate_ack}" — do NOT repeat it or generate your own [ACK] block. Continue naturally from where that ack left off.'
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
                and not _use_standing_codex(brain_name)
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
                elif _use_standing_codex(brain_name):
                    model_name = _get_web_chat_model(brain_name)
                    emit("model", model_name)
                    emit("status", f"Handing the request to Jane's standing Codex brain ({model_name}).")
                elif _use_persistent_codex(brain_name):
                    model_name = _get_web_chat_model(brain_name)
                    emit("model", model_name)
                    emit("status", f"Handing the request to Jane's Codex brain ({model_name}).")
                else:
                    emit("model", adapter.label)
                    emit("status", f"Handing the request to Jane's {adapter.label} brain.")
                response = await _execute_brain_stream(user_id, session_id, brain_name, adapter, request_ctx, emit)
                if tts_enabled:
                    response = _enforce_tts_output_contract(response, session_id, "stream")
            elapsed_ms = int((time.perf_counter() - stage_start) * 1000)
            logger.info("[%s] Brain responded (stream) in %dms, %d chars", session_id[:12], elapsed_ms, len(response or ""))
            _log_stage(session_id, "brain_execute", stage_start, response_chars=len(response or ""))
            if not (response or "").strip():
                logger.warning("[%s] Brain returned empty response after %dms — emitting error instead of empty done",
                               session_id[:12], elapsed_ms)
                emit("error", "⚠️ Jane's brain returned an empty response. This usually means the model is overloaded — please try again.")
            else:
                try:
                    from llm_brain.v1.standing_brain import get_standing_brain_manager as _get_sbm
                    _notice = _get_sbm().pop_pending_notification()
                    if _notice:
                        response = f"{_notice}\n\n{response}"
                        if tts_enabled:
                            response = _enforce_tts_output_contract(response, session_id, "sync-notice")
                except Exception:
                    pass
                if tts_enabled:
                    response = _enforce_tts_output_contract(response, session_id, "stream-notice")
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
            if event_type == "done":
                # TTS-latency debug: stamp the moment done is yielded to the
                # HTTP response body. Compare to tts_done_raw_emit — if this
                # gap is large, it points at queue/coroutine scheduling lag.
                _log_stage(session_id, "tts_done_yielded", request_start)
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
                    await asyncio.wait_for(task, timeout=JANE_RESPONSE_WAIT_SECONDS)
                except asyncio.TimeoutError:
                    logger.warning(
                        "[%s] Adapter task still running after %ds post-disconnect, cancelling",
                        _session_log_id(session_id),
                        JANE_RESPONSE_WAIT_SECONDS,
                    )
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
