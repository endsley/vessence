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


def resolve_pending_action_response(
    pending: dict,
    user_text: str,
    pending_turn_id: str | None = None,
    *,
    logger: Any = None,
) -> dict | None:
    ptype = pending.get("type", "")

    if (
        ptype in ("STAGE3_FOLLOWUP", "STAGE2_FOLLOWUP")
        and is_high_precision_interrupt(user_text)
    ):
        _log(
            logger,
            "info",
            "resolver: high-precision interrupt detected for %s — clearing "
            "pending, falling through to Stage 1 (text=%r)",
            ptype,
            (user_text or "")[:80],
        )
        return {
            "action": "pivot",
            "pending": pending,
            "pending_turn_id": pending_turn_id,
        }

    if ptype in ("STAGE3_FOLLOWUP", "STAGE2_FOLLOWUP") and is_topic_pivot(user_text):
        _log(
            logger,
            "info",
            "resolver: topic-pivot detected for %s — clearing pending, "
            "falling through to Stage 1 (text=%r)",
            ptype,
            (user_text or "")[:80],
        )
        return {
            "action": "pivot",
            "pending": pending,
            "pending_turn_id": pending_turn_id,
        }

    if is_cancel(user_text):
        if ptype in ("STAGE3_FOLLOWUP", "SEND_MESSAGE_DRAFT_OPEN"):
            if normalize_reply(user_text) not in STAGE3_CANCEL_STRONG:
                _log(
                    logger,
                    "info",
                    "resolver: soft-cancel %r ignored for %s "
                    "— letting it fall through",
                    normalize_reply(user_text),
                    ptype,
                )
            else:
                _log(logger, "info", "resolver: strong cancel matched for %s", ptype)
                return {
                    "action": "cancel",
                    "pending": pending,
                    "pending_turn_id": pending_turn_id,
                }
        else:
            _log(logger, "info", "resolver: global cancel matched for pending %s", ptype)
            return {
                "action": "cancel",
                "pending": pending,
                "pending_turn_id": pending_turn_id,
            }

    if ptype == "SEND_MESSAGE_CONFIRMATION":
        if is_confirm(user_text):
            _log(logger, "info", "resolver: confirm matched for pending %s", ptype)
            return {
                "action": "confirm",
                "pending": pending,
                "pending_turn_id": pending_turn_id,
            }
        return None

    if ptype == "SEND_MESSAGE_DRAFT_OPEN":
        if is_confirm(user_text):
            _log(logger, "info", "resolver: draft_send matched for pending %s", ptype)
            return {
                "action": "sms_draft_send",
                "pending": pending,
                "pending_turn_id": pending_turn_id,
            }
        if is_edit_intent(user_text):
            _log(logger, "info", "resolver: draft_edit matched for pending %s", ptype)
            return {
                "action": "sms_draft_edit",
                "pending": pending,
                "pending_turn_id": pending_turn_id,
            }
        return None

    if ptype == "STAGE3_FOLLOWUP":
        _log(logger, "info", "resolver: stage3_followup (awaiting=%s)", pending.get("awaiting"))
        return {
            "action": "stage3_followup",
            "pending": pending,
            "pending_data": pending.get("data", {}),
            "pending_turn_id": pending_turn_id,
        }

    if ptype == "STAGE2_FOLLOWUP":
        handler_class = pending.get("handler_class", "")
        if not handler_class:
            _log(logger, "warning", "resolver: STAGE2_FOLLOWUP missing handler_class")
            return None
        _log(
            logger,
            "info",
            "resolver: followup → %s (awaiting=%s)",
            handler_class,
            pending.get("awaiting") or pending.get("data", {}).get("awaiting"),
        )
        return {
            "action": "followup",
            "handler_class": handler_class,
            "pending": pending,
            "pending_data": pending.get("data", {}),
            "pending_turn_id": pending_turn_id,
        }

    return None
