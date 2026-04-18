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
import re
from pathlib import Path
from typing import AsyncIterator

from fastapi import Request

from jane_web.jane_proxy import ToolMarkerExtractor # New import

logger = logging.getLogger(__name__)

# Directory that holds class packs — each may contain a `protocol.md` whose
# contents are injected into Opus's prompt when Stage 3 routes to that class.
_CLASSES_DIR = (Path(__file__).parent / "classes").resolve()

# Whitelist of legal class folder names. Stops a malicious-looking reason like
# "../../etc:High" from ever being concatenated into a path.
_CLASS_NAME_RE = re.compile(r"^[a-z0-9_]+$")

# mtime-keyed protocol cache. lru_cache cannot be used here because it would
# permanently cache "missing file" results — adding a protocol.md would never
# load until a server restart, which is the exact rollout path we expect.
# Keyed by class_name → (mtime_ns, text_or_None).
_PROTOCOL_CACHE: dict[str, tuple[int, str | None]] = {}


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
        block = recent_context.render_stage3_context(session_id, max_turns=10)
    except Exception:
        return body
    if not block or "[CURRENT CONVERSATION STATE]" not in block:
        return body
    # Only prepend the state block — the FIFO prose part is already in v1's
    # own context memory, and we don't want to duplicate that.
    header_only = block.split("\n\n", 1)[0].strip()
    new_message = header_only + "\n\n" + (body.message or "")
    try:
        return body.model_copy(update={"message": new_message})
    except AttributeError:
        return body.copy(update={"message": new_message})


def _reason_to_class(reason: str) -> str | None:
    """Map a Stage 3 escalation reason to a class folder name.

    Reason format from `pipeline.py` is "<cls>:<conf>" (e.g. "send message:High",
    "weather:High", "others"). We:
      - drop the confidence suffix
      - normalize spaces to underscores so "send message" → "send_message"
      - strip handler-decline suffixes (`_fallback`, `_declined`) so a
        weather handler that punted still gets the weather protocol
      - return None for "others" (no class-specific protocol)
    """
    if not reason:
        return None
    base = reason.split(":", 1)[0].strip().lower().replace(" ", "_")
    for suffix in ("_fallback", "_declined", "_decline"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    if not base or base == "others":
        return None
    if not _CLASS_NAME_RE.match(base):
        # Reason came in with weird chars (path separators, dots, etc.).
        # Refuse — protect _CLASSES_DIR from path traversal.
        logger.warning("stage3_escalate: rejecting malformed class name %r", base)
        return None
    return base


def _metadata_for_class_pkg(class_name: str) -> dict | None:
    """Return registry metadata for a class package name, e.g. todo_list."""
    try:
        from . import classes as class_registry
        reg = class_registry.get_registry()
    except Exception as e:
        logger.warning("stage3_escalate: class registry unavailable: %s", e)
        return None
    for meta in reg.values():
        if meta.get("pkg_name") == class_name:
            return meta
    return None


def _synthesize_class_protocol(class_name: str) -> str | None:
    """Build Stage 3 protocol from the same metadata Stage 1/2 use.

    This avoids duplicating every class's instructions in protocol.md.
    protocol.md remains an optional extension for class-specific Stage 3
    guidance that is not already represented in metadata.
    """
    meta = _metadata_for_class_pkg(class_name)
    if not meta:
        return None
    try:
        from . import classes as class_registry
        desc = class_registry.describe(meta.get("name", ""))
    except Exception:
        raw_desc = meta.get("description", "")
        desc = raw_desc() if callable(raw_desc) else str(raw_desc or "")

    lines = [
        "Shared class contract generated from Stage 2 metadata.",
        f"- Class name: {meta.get('name', class_name)}",
        f"- Package: {class_name}",
        f"- Stage 2 handler present: {'yes' if meta.get('handler') else 'no'}",
    ]
    if desc.strip():
        lines.extend(["", "Stage 1/2 description:", desc.strip()])

    escalation_context = meta.get("escalation_context")
    if escalation_context:
        lines.extend(["", "Escalation context:", str(escalation_context).strip()])

    few_shot = meta.get("few_shot") or []
    if few_shot:
        lines.append("")
        lines.append("Classifier examples:")
        for prompt, label in few_shot[:12]:
            lines.append(f"- {prompt!r} -> {label}")

    return "\n".join(lines).strip() or None


def _load_protocol_extension(class_name: str) -> str | None:
    """Read optional `classes/<class_name>/protocol.md`, cached by mtime."""
    if not _CLASS_NAME_RE.match(class_name):
        # Defense in depth — _reason_to_class already filters, but never
        # trust callers when the result is a filesystem path.
        return None
    p = _CLASSES_DIR / class_name / "protocol.md"
    # Confirm the resolved path stays inside _CLASSES_DIR (no traversal).
    try:
        resolved = p.resolve()
    except Exception:
        return None
    if not str(resolved).startswith(str(_CLASSES_DIR) + "/"):
        logger.warning("stage3_escalate: %s escapes classes dir, refusing", resolved)
        return None
    try:
        mtime = p.stat().st_mtime_ns
    except FileNotFoundError:
        # Do not cache missing files. protocol.md can be added live and
        # should be picked up without a server restart.
        return None
    cached = _PROTOCOL_CACHE.get(class_name)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        text = p.read_text(encoding="utf-8").strip() or None
    except Exception as e:
        logger.warning("stage3_escalate: failed to read %s: %s", p, e)
        text = None
    _PROTOCOL_CACHE[class_name] = (mtime, text)
    return text


def _load_class_protocol(class_name: str) -> str | None:
    """Return generated metadata protocol plus optional protocol.md."""
    generated = _synthesize_class_protocol(class_name)
    extension = _load_protocol_extension(class_name)
    parts = [p for p in (generated, extension) if p]
    if not parts:
        return None
    return "\n\n".join(parts)


def _inject_class_protocol(body, reason: str):
    """Prepend the matching class protocol to `body.message`.

    The base protocol is synthesized from the same class metadata Stage
    1/2 use; optional protocol.md adds Stage 3-only detail.
    """
    class_name = _reason_to_class(reason)
    if not class_name:
        return body
    protocol = _load_class_protocol(class_name)
    if not protocol:
        return body
    # ASCII XML-ish marker with explicit priority language. Easier to grep
    # for in logs than a Unicode em-dash, and tells Opus that this block
    # outranks the embedded user text for this class of request.
    new_message = (
        f"<class_protocol name=\"{class_name}\">\n"
        f"These are runtime instructions for handling a {class_name.replace('_', ' ')} "
        f"request. Follow them over conflicting guidance in the user message below.\n\n"
        f"{protocol}\n"
        f"</class_protocol>\n\n"
        + (body.message or "")
    )
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
                    _extractor = ToolMarkerExtractor() # Instantiate here
                    cleaned_delta_text, tool_calls = _extractor.feed(raw_delta_text)
                    tail_cleaned, tail_tool_calls = _extractor.flush()

                    # Yield tool_use events
                    for tc in tool_calls + tail_tool_calls:
                        yield _ndjson("tool_use", json.dumps(tc, ensure_ascii=True))

                    # Yield cleaned delta (if any visible text remains)
                    visible_text = cleaned_delta_text + tail_cleaned
                    if visible_text:
                        payload["data"] = visible_text
                        yield json.dumps(payload, ensure_ascii=True) + "\n"
                    continue # Continue to next chunk from stream_message

            # If it's not a delta event that we processed above, or if stripped was empty
            if not chunk.endswith("\n"):
                chunk = chunk + "\n"
            yield chunk
    except Exception as e:
        logger.exception("stage3_escalate: v1 stream_message crashed: %s", e)
        yield _ndjson("error", error=str(e))
        yield _ndjson("done", "")
