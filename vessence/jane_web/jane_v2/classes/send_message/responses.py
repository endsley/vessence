"""Response builders for the send-message Stage 2 handler."""
from __future__ import annotations

from agent_skills.private_handler_utils import pending_continuation
from jane_web.jane_v2.sms_tool_markers import (
    sms_draft_cancel_marker as _sms_draft_cancel_marker,
    sms_draft_send_marker as _sms_draft_send_marker,
    sms_send_direct_marker as _sms_send_direct_marker,
)


INTENT = "send message"


def build_send_marker(phone: str, body: str) -> str:
    return _sms_send_direct_marker(phone, body)


def build_sent_response(
    phone: str,
    display: str,
    body: str,
    *,
    prefix: str = "Done, message sent.",
) -> dict:
    marker = build_send_marker(phone, body)
    return {
        "text": f"{prefix} {marker}",
        "conversation_end": True,
        "structured": {
            "intent": INTENT,
            "entities": {
                "recipient": display,
                "phone_number": phone,
                "message_body": body,
            },
            "safety": {"side_effectful": True, "requires_confirmation": False},
        },
    }


def draft_pending_data(phone: str, display: str, body: str | None = None) -> dict:
    draft = {"phone": phone, "display": display}
    if body is not None:
        draft["body"] = body
    return {"draft": draft}


def build_pending_message_response(ask: str, awaiting: str, data: dict) -> dict:
    return {
        "text": ask,
        "structured": {
            "intent": INTENT,
            "pending_action": pending_continuation(
                handler_class=INTENT,
                awaiting=awaiting,
                question=ask,
                data=data,
            ),
        },
    }


def build_revision_request_response(phone: str, display: str) -> dict:
    ask = "Please give me the updated message."
    return build_pending_message_response(ask, "revised_body", draft_pending_data(phone, display))


def build_confirmation_response(phone: str, display: str, body: str) -> dict:
    ask = f"Message to {display}: {body}. Should I send it?"
    return build_pending_message_response(
        ask,
        "send_confirmation",
        draft_pending_data(phone, display, body),
    )


def build_open_draft_send_response(draft_id: str, query: str, body: str) -> dict:
    marker = _sms_draft_send_marker(draft_id)
    return {
        "text": f"Sending to {query}. {marker}",
        "structured": {
            "intent": INTENT,
            "entities": {"recipient": query, "message_body": body, "draft_id": draft_id},
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "status": "resolved",
                "resolution": "sent",
            },
            "safety": {"side_effectful": True, "requires_confirmation": False},
        },
    }


def build_open_draft_cancel_response(draft_id: str, query: str) -> dict:
    marker = _sms_draft_cancel_marker(draft_id)
    return {
        "text": f"Okay, cancelled the message to {query}. {marker}",
        "structured": {
            "intent": INTENT,
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "status": "resolved",
                "resolution": "cancelled",
            },
        },
    }
