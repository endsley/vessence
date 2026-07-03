"""Stage 3 — escalate to Jane's full brain (Opus / Claude / Gemini).

When Stage 1 routes to "others", or when a Stage 2 handler can't
answer confidently, we fall back to v1's stream_message which owns
the full context-building, memory retrieval, and brain subprocess
management. Stage 3 is deliberately a thin wrapper around v1 so we
don't duplicate the complex brain plumbing — a rewrite of that is
out of scope for the v2 3-stage pipeline.

What Stage 3 adds on top of a raw v1 call:
  - A pre-ack event emitted immediately, so the user sees something
    within ~50 ms even though the real answer may take seconds.
  - Class context in logs for debugging.
  - Uniform error handling — if v1 crashes, emit a final error event
    instead of letting the stream hang.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import Request

from jane_web.client_tool_markers import ToolMarkerExtractor
from jane_web.jane_v2.stage3_body_injections import (
    copy_body_with_message as _copy_body_with_message,
    inject_class_protocol as _inject_class_protocol,
    inject_extracted_params as _inject_extracted_params,
    maybe_voice_wrap as _maybe_voice_wrap,
)
from jane_web.jane_v2.stage3_protocols import (
    load_class_protocol as _load_class_protocol,
    reason_to_class as _reason_to_class,
)

logger = logging.getLogger(__name__)

def _inject_structured_state(body):
    """Prepend a rendered CURRENT CONVERSATION STATE block to the user's
    message when FIFO holds an active pending action or last intent.

    Stage 3 (Opus) is the only consumer that benefits — structured state
    lets it answer context-dependent follow-ups ("what about tomorrow",
    "actually make it shorter") without re-deriving state from prose.
    """
    session_id = getattr(body, "session_id", None)
    if not session_id:
        return body
    try:
        from . import recent_context
        block = recent_context.render_stage3_context(session_id, max_turns=5)
    except Exception:
        return body
    if not block or "[CURRENT CONVERSATION STATE]" not in block:
        return body
    # Prepend the full rendered block (state header + FIFO prose). The
    # prior assumption that v1's standing brain already has the history
    # is false when the previous turn was handled by Stage 2 — those
    # turns never touched v1, so v1's context is blank. Always passing
    # the last few FIFO turns is the simplest way to keep Opus oriented
    # across Stage 2 → Stage 3 transitions.
    new_message = block.strip() + "\n\n" + (body.message or "")
    return _copy_body_with_message(body, new_message)


def _ndjson(event_type: str, data=None, **extra) -> str:
    payload = {"type": event_type}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=True) + "\n"


def _load_v1_stream():
    """Import v1's stream_message lazily to avoid circular imports."""
    try:
        from jane_proxy import stream_message
        return stream_message
    except ImportError:
        try:
            from jane_web.jane_proxy import stream_message  # type: ignore
            return stream_message
        except Exception as e:
            logger.exception("stage3_escalate: could not import v1 stream_message: %s", e)
            return None


def _load_session_helpers():
    """Import session helpers lazily.

    The `jane_web.main` absolute import is expected to succeed in all
    normal runtime configurations (uvicorn / CLI entrypoint). The
    previous fallback used a relative import that was always broken
    (`.main` doesn't exist inside `jane_v2/`) and swallowed the real
    error.  If the absolute import fails, we now stub out with no-ops
    and log loudly — Stage 3 can still run without session helpers, it
    just won't personalize the user context.
    """
    try:
        from jane_web.main import get_or_bootstrap_session, _default_user_id
    except Exception as e:
        logger.exception("stage3_escalate: jane_web.main import failed: %s", e)

        def get_or_bootstrap_session(*_a, **_kw):
            return None

        def _default_user_id():
            return None

    try:
        from vault_web.auth import get_session_user
    except Exception as e:
        logger.exception("stage3_escalate: vault_web.auth import failed: %s", e)

        def get_session_user(_sid):
            return None

    return get_or_bootstrap_session, _default_user_id, get_session_user


async def escalate_stream(
    body,
    request: Request,
    ack_text: str,
    reason: str = "others",
    session_id_override: str | None = None,
    params: dict | None = None,
) -> AsyncIterator[str]:
    """Yield an ack, then stream v1's brain response.

    Args:
        body: the incoming ChatMessage.
        request: the FastAPI Request (needed for cookie-based auth).
        ack_text: short user-visible status line shown immediately.
        reason: routing reason for logs ("others", "weather_fallback", etc.).
        session_id_override: if set, use this session_id for v1 stream_message
            instead of the cookie-derived one. The v2 pipeline passes its
            canonical session_id here so v1's conversation_manager writes
            FIFO rows under the SAME key the pipeline uses for pending-
            action lookups — otherwise multi-turn follow-ups silently
            lose state.

    Yields NDJSON-encoded event strings (each ends with "\\n").
    """
    is_voice = (getattr(body, "platform", None) or "").lower() == "voice"
    effective_body = _inject_structured_state(body)
    effective_body = _inject_extracted_params(effective_body, params)
    effective_body = _maybe_voice_wrap(effective_body)
    # Class protocol goes outermost so it appears first within the user-turn
    # payload (ahead of voice hints and state blocks). v1's stream_message
    # may still wrap this with system instructions, memory, and tool prompts
    # before sending to Opus, so this is "first in body.message", not
    # necessarily first in Opus's full prompt.
    effective_body = _inject_class_protocol(effective_body, reason)
    injected_class = _reason_to_class(reason)
    if injected_class is None:
        protocol_status = "n/a"
    elif _load_class_protocol(injected_class):
        protocol_status = f"loaded:{injected_class}"
    else:
        protocol_status = f"missing:{injected_class}"
    logger.info(
        "stage3_escalate: reason=%s voice=%s prompt_len=%d sid_override=%s class_protocol=%s",
        reason,
        is_voice,
        len(effective_body.message or ""),
        bool(session_id_override),
        protocol_status,
    )

    stream_message = _load_v1_stream()
    if stream_message is None:
        yield _ndjson("error", error="Jane's brain is unavailable right now.")
        yield _ndjson("done", "")
        return

    get_or_bootstrap_session, _default_user_id, get_session_user = _load_session_helpers()
    # Auth still goes through cookies, but we use the canonical session_id
    # (body or cookie, whichever the pipeline decided) as the key threaded
    # into v1. This keeps FIFO writes consistent across v1 + v2.
    cookie_session_id, _ = get_or_bootstrap_session(request)
    if not cookie_session_id:
        yield _ndjson("error", error="Not authenticated")
        yield _ndjson("done", "")
        return
    session_id = (session_id_override or "").strip() or cookie_session_id
    user_id = get_session_user(cookie_session_id) or _default_user_id()

    try:
        # Always emit the ack for Stage 3 escalations — it conveys both
        # "message received" and a rough time estimate so the user knows
        # whether to wait or come back later. Stage 2 fast-paths skip
        # acks entirely (handled in pipeline.py).
        if ack_text:
            yield _ndjson("ack", ack_text)

        # Filter out v1's own canned `ack` events — we already emitted ours
        # above. Without this filter the user hears two acks: ours ("Sure,
        # give me a sec to ...") followed by v1's ("On it...").
        # We also drop v1's "model" + initial gemma classification noise
        # when they immediately precede an Opus ack.
        v1_ack_suppressed = False
        _extractor = ToolMarkerExtractor()
        async for chunk in stream_message(
            user_id,
            session_id,
            effective_body.message,
            effective_body.file_context,
            platform=effective_body.platform,
            tts_enabled=effective_body.tts_enabled or False,
            skip_router=True,
        ):
            stripped = chunk.strip()
            if stripped:
                # Each chunk is one NDJSON line; check if it's a v1 ack and skip
                if stripped.startswith('{"type": "ack"') or stripped.startswith('{"type":"ack"'):
                    if not v1_ack_suppressed:
                        v1_ack_suppressed = True
                        logger.debug("stage3_escalate: suppressed v1 ack (already emitted v2 ack)")
                    continue

                # Process chunk for tool_use events
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    if not chunk.endswith("\n"):
                        chunk = chunk + "\n"
                    yield chunk # Yield original if not JSON
                    continue

                if payload.get("type") == "delta" and isinstance(payload.get("data"), str):
                    raw_delta_text = payload["data"]
                    cleaned_delta_text, tool_calls = _extractor.feed(raw_delta_text)

                    # Yield tool_use events
                    for tc in tool_calls:
                        yield _ndjson("tool_use", json.dumps(tc, ensure_ascii=True))

                    # Yield cleaned delta (if any visible text remains)
                    if cleaned_delta_text:
                        payload["data"] = cleaned_delta_text
                        yield json.dumps(payload, ensure_ascii=True) + "\n"
                    continue # Continue to next chunk from stream_message

            # If it's not a delta event that we processed above, or if stripped was empty
            if not chunk.endswith("\n"):
                chunk = chunk + "\n"
            yield chunk

        # Flush any buffered partial marker at end of stream
        tail_cleaned, tail_tool_calls = _extractor.flush()
        for tc in tail_tool_calls:
            yield _ndjson("tool_use", json.dumps(tc, ensure_ascii=True))
        if tail_cleaned:
            yield _ndjson("delta", tail_cleaned)
    except Exception as e:
        logger.exception("stage3_escalate: v1 stream_message crashed: %s", e)
        yield _ndjson("error", error=str(e))
        yield _ndjson("done", "")
