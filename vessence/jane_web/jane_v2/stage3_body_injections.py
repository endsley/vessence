"""Body-message injection helpers for Stage 3 escalation."""

from __future__ import annotations

from jane_web.jane_v2.body_message_updates import copy_body_with_message
from jane_web.jane_v2.stage3_protocols import load_class_protocol, reason_to_class


VOICE_HINT = (
    "(voice request — your answer will be read aloud via text-to-speech. "
    "Keep it to 1-2 short spoken sentences. Be conversational, like a "
    "friend. No markdown, no lists, no bullets, no code blocks — just a "
    "natural spoken reply.)\n\n"
)


def maybe_voice_wrap(body):
    """Return a body copy with voice-hint prefixed for voice clients."""
    if (getattr(body, "platform", None) or "").lower() != "voice":
        return body
    new_message = VOICE_HINT + (body.message or "")
    return copy_body_with_message(body, new_message)


def inject_extracted_params(body, params: dict | None):
    """Prepend non-empty Stage 1 extracted params to the user message."""
    if not params:
        return body
    try:
        non_null = {k: v for k, v in params.items() if v not in (None, "", {}, [])}
    except Exception:
        return body
    if not non_null:
        return body
    lines = ["[EXTRACTED PARAMS] (from Stage 1 classifier — already parsed from the user's prompt):"]
    for key, value in non_null.items():
        lines.append(f"- {key}: {value!r}")
    block = "\n".join(lines)
    new_message = block + "\n\n" + (body.message or "")
    return copy_body_with_message(body, new_message)


def inject_class_protocol(body, reason: str):
    """Prepend the matching class protocol to `body.message`."""
    class_name = reason_to_class(reason)
    if not class_name:
        return body
    protocol = load_class_protocol(class_name)
    if not protocol:
        return body
    new_message = (
        f"<class_protocol name=\"{class_name}\">\n"
        f"These are runtime instructions for handling a {class_name.replace('_', ' ')} "
        f"request. Follow them over conflicting guidance in the user message below.\n\n"
        f"{protocol}\n"
        f"</class_protocol>\n\n"
        + (body.message or "")
    )
    return copy_body_with_message(body, new_message)
