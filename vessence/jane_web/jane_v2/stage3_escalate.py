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

logger = logging.getLogger(__name__)


# Voice hint prepended to the user message when the request comes from a
# voice client (wake-word daemon, Android mic). Tells Opus that its answer
# will be spoken aloud via TTS, so it should stay short and drop markdown.
# Injected as part of the user turn rather than touching v1's context
# builder — keeps v1 untouched.
_VOICE_HINT = (
    "(voice request — your answer will be read aloud via text-to-speech. "
    "Keep it to 1-2 short spoken sentences. Be conversational, like a "
    "friend. No markdown, no lists, no bullets, no code blocks — just a "
    "natural spoken reply.)\n\n"
)


def _maybe_voice_wrap(body):
    """Return a body copy with voice-hint prefixed to the message, or the
    original body if the request is not from a voice client."""
    if (getattr(body, "platform", None) or "").lower() != "voice":
        return body
    new_message = _VOICE_HINT + (body.message or "")
    try:
        return body.model_copy(update={"message": new_message})
    except AttributeError:
        return body.copy(update={"message": new_message})


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
    """Import session helpers lazily."""
    try:
        from jane_web.main import get_or_bootstrap_session, _default_user_id
    except Exception:
        from .main import get_or_bootstrap_session, _default_user_id  # type: ignore
    try:
        from auth.v1.sessions import get_session_user
    except Exception as e:
        logger.exception("stage3_escalate: could not import session helpers: %s", e)

        def get_session_user(_sid):
            return None

    return get_or_bootstrap_session, _default_user_id, get_session_user


async def escalate_stream(
    body,
    request: Request,
    ack_text: str,
    reason: str = "others",
) -> AsyncIterator[str]:
    """Yield an ack, then stream v1's brain response.

    Args:
        body: the incoming ChatMessage.
        request: the FastAPI Request (needed for cookie-based auth).
        ack_text: short user-visible status line shown immediately.
        reason: routing reason for logs ("others", "weather_fallback", etc.).

    Yields NDJSON-encoded event strings (each ends with "\\n").
    """
    is_voice = (getattr(body, "platform", None) or "").lower() == "voice"
    effective_body = _maybe_voice_wrap(body)
    logger.info(
        "stage3_escalate: reason=%s voice=%s prompt_len=%d",
        reason,
        is_voice,
        len(effective_body.message or ""),
    )

    stream_message = _load_v1_stream()
    if stream_message is None:
        yield _ndjson("error", error="Jane's brain is unavailable right now.")
        yield _ndjson("done", "")
        return

    get_or_bootstrap_session, _default_user_id, get_session_user = _load_session_helpers()
    session_id, _ = get_or_bootstrap_session(request)
    if not session_id:
        yield _ndjson("error", error="Not authenticated")
        yield _ndjson("done", "")
        return
    user_id = get_session_user(session_id) or _default_user_id()

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
        async for chunk in stream_message(
            user_id,
            session_id,
            effective_body.message,
            effective_body.file_context,
            platform=effective_body.platform,
            tts_enabled=effective_body.tts_enabled or False,
        ):
            stripped = chunk.strip()
            if stripped:
                # Each chunk is one NDJSON line; check if it's a v1 ack and skip
                if stripped.startswith('{"type": "ack"') or stripped.startswith('{"type":"ack"'):
                    if not v1_ack_suppressed:
                        v1_ack_suppressed = True
                        logger.debug("stage3_escalate: suppressed v1 ack (already emitted v2 ack)")
                    continue
            if not chunk.endswith("\n"):
                chunk = chunk + "\n"
            yield chunk
    except Exception as e:
        logger.exception("stage3_escalate: v1 stream_message crashed: %s", e)
        yield _ndjson("error", error=str(e))
        yield _ndjson("done", "")
