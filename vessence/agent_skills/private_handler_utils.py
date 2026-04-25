"""Safety utilities for Stage 2 handlers marked `privacy="local_only"`.

Classes flagged `no_stage3 = True` cannot punt to Stage 3 on failure — their
handler IS the final answer-giver. This module provides the terminal
deflection the pipeline uses when such a handler crashes, returns an invalid
shape, or explicitly requests escalation. The deflection must never carry
class-specific data (since the handler couldn't answer, we don't know what
the user was asking about at the level of specificity the reply implies).
"""

from __future__ import annotations

SAFE_CLINIC_DEFLECTION = "I'm not sure about that one — can you rephrase?"


def safe_deflection(cls: str | None = None) -> dict:
    """Return a safe, class-agnostic deflection suitable for local-only handlers."""
    return {"text": SAFE_CLINIC_DEFLECTION}


def _lookup_meta(cls: str | None) -> dict | None:
    """Resolve `cls` against the v2 class registry, tolerant of "_" vs " ".

    The registry is keyed by the class `name` field, which uses spaces
    ("clinic schedules info"). Some classifier code paths historically emit
    the folder-name form with underscores ("clinic_schedules_info"). Try
    the verbatim key first, then the normalized space form so either works.
    """
    if not cls:
        return None
    try:
        from jane_web.jane_v2 import classes as class_registry
        reg = class_registry.get_registry()
    except Exception:
        return None
    meta = reg.get(cls)
    if meta is not None:
        return meta
    normalized = cls.replace("_", " ").strip().lower()
    return reg.get(normalized)


def is_no_stage3(cls: str | None) -> bool:
    """True if the given class is marked `no_stage3 = True` in its metadata."""
    meta = _lookup_meta(cls)
    return bool(meta and meta.get("no_stage3"))


def privacy_for(cls: str | None) -> str | None:
    """Return the class's `privacy` flag ("local_only" or None)."""
    meta = _lookup_meta(cls)
    if meta:
        return meta.get("privacy")
    return None


# ── Multi-turn continuation helpers ────────────────────────────────────────
import datetime as _dt


def _expires_at(minutes: int = 2) -> str:
    return (_dt.datetime.utcnow() + _dt.timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def pending_continuation(
    handler_class: str,
    awaiting: str,
    question: str,
    data: dict | None = None,
    minutes: int = 2,
) -> dict:
    """Build a STAGE2_FOLLOWUP pending_action for any multi-turn handler.

    Use this from "repeating-read" handlers (todo, weather) and
    "confirm-or-revise" handlers (sms, email) so the next turn knows
    which handler should resume and with what shape.

    `awaiting` is a handler-specific tag identifying the response shape
    expected (e.g. "another_category_or_stop", "send_confirmation",
    "revised_body"). The handler reads this tag in its resume branch.

    `question` is the literal text Jane just asked. Stored verbatim so
    the classifier's pivot check can see what was being asked.

    `data` carries any handler-specific state across the turn (e.g.
    {"draft": {...}, "remaining": [...]}).
    """
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": handler_class,
        "status": "awaiting_user",
        "awaiting": awaiting,
        "data": {**(data or {}), "awaiting": awaiting},
        "question": question,
        "expires_at": _expires_at(minutes),
    }


def end_conversation(text: str = "Ok.", structured: dict | None = None) -> dict:
    """Return a handler result that ends the conversation cleanly.

    Emits conversation_end=True so the Android client drops STT and
    returns to wake-word mode (and plays the end-conversation cue).
    """
    return {
        "text": text,
        "conversation_end": True,
        "structured": structured or {},
    }
