"""Deterministic pending-action response routing."""

from __future__ import annotations

from typing import Any

from jane_web.jane_v2.pending_action_phrases import (
    STAGE3_CANCEL_STRONG,
    is_cancel,
    is_confirm,
    is_edit_intent,
    is_high_precision_interrupt,
    is_topic_pivot,
    normalize_reply,
)


def _log(logger: Any, level: str, message: str, *args: Any) -> None:
    if logger is not None:
        getattr(logger, level)(message, *args)


def _resolution(action: str, pending: dict, pending_turn_id: str | None, **extra: Any) -> dict:
    return {
        "action": action,
        **extra,
        "pending": pending,
        "pending_turn_id": pending_turn_id,
    }


def _pending_data(pending: dict) -> dict:
    data = pending.get("data", {})
    return data if isinstance(data, dict) else {}


def _pending_awaiting(pending: dict) -> Any:
    return pending.get("awaiting") or _pending_data(pending).get("awaiting")


def _followup_pivot_kind(ptype: str, user_text: str) -> str | None:
    if ptype not in ("STAGE3_FOLLOWUP", "STAGE2_FOLLOWUP"):
        return None
    if is_high_precision_interrupt(user_text):
        return "high_precision_interrupt"
    if is_topic_pivot(user_text):
        return "topic_pivot"
    return None


def _cancel_kind(ptype: str, user_text: str) -> str | None:
    if not is_cancel(user_text):
        return None
    if ptype in ("STAGE3_FOLLOWUP", "SEND_MESSAGE_DRAFT_OPEN"):
        if normalize_reply(user_text) not in STAGE3_CANCEL_STRONG:
            return "soft_ignored"
        return "strong_cancel"
    return "global_cancel"


def _send_message_confirmation_resolution(
    pending: dict,
    user_text: str,
    pending_turn_id: str | None,
    *,
    logger: Any = None,
) -> dict | None:
    if is_confirm(user_text):
        _log(logger, "info", "resolver: confirm matched for pending %s", pending.get("type", ""))
        return _resolution("confirm", pending, pending_turn_id)
    return None


def _send_message_draft_resolution(
    pending: dict,
    user_text: str,
    pending_turn_id: str | None,
    *,
    logger: Any = None,
) -> dict | None:
    ptype = pending.get("type", "")
    if is_confirm(user_text):
        _log(logger, "info", "resolver: draft_send matched for pending %s", ptype)
        return _resolution("sms_draft_send", pending, pending_turn_id)
    if is_edit_intent(user_text):
        _log(logger, "info", "resolver: draft_edit matched for pending %s", ptype)
        return _resolution("sms_draft_edit", pending, pending_turn_id)
    return None


def _stage3_followup_resolution(
    pending: dict,
    pending_turn_id: str | None,
    *,
    logger: Any = None,
) -> dict:
    _log(logger, "info", "resolver: stage3_followup (awaiting=%s)", pending.get("awaiting"))
    return _resolution(
        "stage3_followup",
        pending,
        pending_turn_id,
        pending_data=_pending_data(pending),
    )


def _stage2_followup_resolution(
    pending: dict,
    pending_turn_id: str | None,
    *,
    logger: Any = None,
) -> dict | None:
    handler_class = pending.get("handler_class", "")
    if not handler_class:
        _log(logger, "warning", "resolver: STAGE2_FOLLOWUP missing handler_class")
        return None
    _log(
        logger,
        "info",
        "resolver: followup → %s (awaiting=%s)",
        handler_class,
        _pending_awaiting(pending),
    )
    return _resolution(
        "followup",
        pending,
        pending_turn_id,
        handler_class=handler_class,
        pending_data=_pending_data(pending),
    )


def resolve_pending_action_response(
    pending: dict,
    user_text: str,
    pending_turn_id: str | None = None,
    *,
    logger: Any = None,
) -> dict | None:
    ptype = pending.get("type", "")

    pivot_kind = _followup_pivot_kind(ptype, user_text)
    if pivot_kind == "high_precision_interrupt":
        _log(
            logger,
            "info",
            "resolver: high-precision interrupt detected for %s — clearing "
            "pending, falling through to Stage 1 (text=%r)",
            ptype,
            (user_text or "")[:80],
        )
        return _resolution("pivot", pending, pending_turn_id)
    if pivot_kind == "topic_pivot":
        _log(
            logger,
            "info",
            "resolver: topic-pivot detected for %s — clearing pending, "
            "falling through to Stage 1 (text=%r)",
            ptype,
            (user_text or "")[:80],
        )
        return _resolution("pivot", pending, pending_turn_id)

    cancel_kind = _cancel_kind(ptype, user_text)
    if cancel_kind == "soft_ignored":
        _log(
            logger,
            "info",
            "resolver: soft-cancel %r ignored for %s "
            "— letting it fall through",
            normalize_reply(user_text),
            ptype,
        )
    elif cancel_kind == "strong_cancel":
        _log(logger, "info", "resolver: strong cancel matched for %s", ptype)
        return _resolution("cancel", pending, pending_turn_id)
    elif cancel_kind == "global_cancel":
        _log(logger, "info", "resolver: global cancel matched for pending %s", ptype)
        return _resolution("cancel", pending, pending_turn_id)

    if ptype == "SEND_MESSAGE_CONFIRMATION":
        return _send_message_confirmation_resolution(
            pending,
            user_text,
            pending_turn_id,
            logger=logger,
        )

    if ptype == "SEND_MESSAGE_DRAFT_OPEN":
        return _send_message_draft_resolution(
            pending,
            user_text,
            pending_turn_id,
            logger=logger,
        )

    if ptype == "STAGE3_FOLLOWUP":
        return _stage3_followup_resolution(pending, pending_turn_id, logger=logger)

    if ptype == "STAGE2_FOLLOWUP":
        return _stage2_followup_resolution(pending, pending_turn_id, logger=logger)

    return None
