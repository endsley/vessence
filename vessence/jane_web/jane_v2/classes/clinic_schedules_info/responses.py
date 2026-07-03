"""Response builders for clinic schedule Stage 2."""

from __future__ import annotations

from agent_skills.private_handler_utils import pending_continuation as _pending_continuation


INTENT = "clinic schedules info"


def build_clinic_pending(awaiting: str, **data) -> dict:
    return _pending_continuation(
        handler_class=INTENT,
        awaiting=awaiting,
        question=f"(awaiting:{awaiting})",
        data=data,
    )


def build_clinic_response(reply: str) -> dict:
    return {
        "text": reply,
        "structured": {
            "intent": INTENT,
            "pending_action": build_clinic_pending("clinic_followup"),
        },
    }
