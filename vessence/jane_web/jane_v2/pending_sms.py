"""SMS pending-action helpers for the v2 pipeline."""

from __future__ import annotations

import json
import logging
import re


logger = logging.getLogger(__name__)

_SMS_DRAFT_MARKER_RE = re.compile(
    r"\[\[CLIENT_TOOL:contacts\.(sms_draft|sms_draft_update|sms_send|sms_cancel):"
    r"(\{[^\n]*?\})\]\]"
)


def pending_consumed_marker(
    pending: dict,
    *,
    status: str = "resolved",
    resolution: str = "answered",
) -> dict:
    """Build a FIFO marker that suppresses an older pending action."""
    marker = {
        "type": pending.get("type", ""),
        "handler_class": pending.get("handler_class", ""),
        "status": status,
        "resolution": resolution,
    }
    awaiting = pending.get("awaiting") or (pending.get("data") or {}).get("awaiting")
    if awaiting:
        marker["awaiting"] = awaiting
    return {key: value for key, value in marker.items() if value}


def resolve_pending_sms_confirmation(pending: dict) -> dict:
    """Build a Stage 2-shaped result dict that sends the pending SMS."""
    data = pending.get("data") or {}
    phone = data.get("phone_number") or ""
    body = data.get("body") or data.get("message_body") or ""
    display = data.get("display_name") or data.get("recipient") or "them"
    tool_args = json.dumps({"phone_number": phone, "body": body})
    marker = f"[[CLIENT_TOOL:contacts.sms_send_direct:{tool_args}]]"
    return {
        "text": f"Sending to {display}. {marker}",
        "structured": {
            "intent": "send message",
            "entities": {
                "recipient": display,
                "message_body": body,
                "phone_number": phone,
            },
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "resolved",
                "resolution": "confirmed",
            },
            "safety": {"side_effectful": True, "requires_confirmation": False},
        },
    }


def cancel_pending_sms_confirmation(pending: dict) -> dict:
    """Build a Stage 2-shaped result dict that drops the pending SMS."""
    data = pending.get("data") or {}
    display = data.get("display_name") or data.get("recipient") or "them"
    return {
        "text": f"Okay, not sending that to {display}.",
        "structured": {
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "resolved",
                "resolution": "cancelled",
            },
        },
    }


def extract_sms_draft_state(text: str) -> dict | None:
    """Return the latest open SMS draft state from Stage 3 client markers."""
    if not text or "[[CLIENT_TOOL:contacts.sms_" not in text:
        return None
    state: dict | None = None
    for match in _SMS_DRAFT_MARKER_RE.finditer(text):
        tool = match.group(1)
        try:
            args = json.loads(match.group(2))
        except Exception:
            continue
        if tool == "sms_draft":
            state = {
                "draft_id": args.get("draft_id") or "",
                "query": args.get("query") or "",
                "body": args.get("body") or "",
            }
        elif tool == "sms_draft_update":
            if state is not None:
                state["body"] = args.get("body", state.get("body", ""))
                if args.get("draft_id"):
                    state["draft_id"] = args["draft_id"]
            else:
                state = {
                    "draft_id": args.get("draft_id") or "",
                    "query": "",
                    "body": args.get("body") or "",
                }
        elif tool in ("sms_send", "sms_cancel"):
            state = None
    if state and state.get("draft_id") and state.get("body"):
        return state
    return None


def resolve_pending_sms_draft_send(pending: dict) -> dict:
    """User confirmed an open sms_draft. Emit sms_send with the draft_id."""
    data = pending.get("data") or {}
    draft_id = data.get("draft_id") or ""
    query = data.get("query") or data.get("display_name") or data.get("recipient") or "them"
    body = data.get("body") or ""
    tool_args = json.dumps({"draft_id": draft_id})
    marker = f"[[CLIENT_TOOL:contacts.sms_send:{tool_args}]]"
    return {
        "text": f"Sending to {query}. {marker}",
        "structured": {
            "intent": "send message",
            "entities": {
                "recipient": query,
                "message_body": body,
                "draft_id": draft_id,
            },
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "status": "resolved",
                "resolution": "sent",
            },
            "safety": {"side_effectful": True, "requires_confirmation": False},
        },
    }


def cancel_pending_sms_draft(pending: dict) -> dict:
    """User cancelled an open sms_draft. Emit sms_cancel with the draft_id."""
    data = pending.get("data") or {}
    draft_id = data.get("draft_id") or ""
    query = data.get("query") or data.get("display_name") or data.get("recipient") or "them"
    tool_args = json.dumps({"draft_id": draft_id})
    marker = f"[[CLIENT_TOOL:contacts.sms_cancel:{tool_args}]]"
    return {
        "text": f"Okay, cancelled the message to {query}. {marker}",
        "structured": {
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "status": "resolved",
                "resolution": "cancelled",
            },
        },
    }


async def resolve_pending_sms_draft_edit(pending: dict, edit_text: str) -> dict:
    """Compose an sms_draft_update result for an edited open draft."""
    data = pending.get("data") or {}
    draft_id = data.get("draft_id") or ""
    query = data.get("query") or data.get("display_name") or data.get("recipient") or "them"
    old_body = data.get("body") or ""
    new_body = old_body

    compose_prompt = (
        "You are revising an SMS draft based on the user's edit instruction.\n"
        "CRITICAL: output ONLY the new message body - no preamble, no quotes, "
        "no 'Sure, here is' prefix. Just the revised SMS body text itself.\n\n"
        f"CURRENT DRAFT BODY: {old_body}\n"
        f"USER EDIT INSTRUCTION: {edit_text}\n\n"
        "NEW BODY:"
    )
    try:
        import httpx
        from jane_web.jane_v2.models import (
            LOCAL_LLM as _model,
            LOCAL_LLM_NUM_CTX as _num_ctx,
            LOCAL_LLM_TIMEOUT as _timeout,
            OLLAMA_URL as _url,
        )
        async with httpx.AsyncClient(timeout=_timeout) as client:
            response = await client.post(_url, json={
                "model": _model,
                "prompt": compose_prompt,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 80,
                    "num_ctx": _num_ctx,
                },
                "keep_alive": -1,
            })
            response.raise_for_status()
            composed = (response.json().get("response") or "").strip()
            composed = composed.strip('"').strip("'").strip()
            if composed.lower().startswith("new body:"):
                composed = composed[len("new body:"):].strip()
            if composed:
                new_body = composed
    except Exception as exc:
        logger.warning("draft-edit compose failed (%s) - using fallback concat", exc)
        new_body = f"{old_body}. {edit_text}".strip()

    tool_args = json.dumps({"draft_id": draft_id, "body": new_body})
    marker = f"[[CLIENT_TOOL:contacts.sms_draft_update:{tool_args}]]"
    return {
        "text": f"Updated. To {query}: {new_body}. {marker}",
        "structured": {
            "intent": "send message",
            "entities": {
                "recipient": query,
                "message_body": new_body,
                "draft_id": draft_id,
            },
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "status": "awaiting_user",
                "awaiting": "confirm_draft",
                "handler_class": "send message",
                "data": {
                    "draft_id": draft_id,
                    "query": query,
                    "body": new_body,
                },
            },
        },
    }
