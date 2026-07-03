"""Shared SMS client-tool marker helpers for the v2 pipeline."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from jane_web.client_tool_markers import build_client_tool_marker


SMS_SEND_DIRECT_TOOL = "contacts.sms_send_direct"
SMS_DRAFT_TOOL = "contacts.sms_draft"
SMS_DRAFT_UPDATE_TOOL = "contacts.sms_draft_update"
SMS_SEND_TOOL = "contacts.sms_send"
SMS_CANCEL_TOOL = "contacts.sms_cancel"

SMS_DRAFT_ACTIONS = ("sms_draft", "sms_draft_update", "sms_send", "sms_cancel")
SMS_DRAFT_MARKER_RE = re.compile(
    r"\[\[CLIENT_TOOL:contacts\.(" + "|".join(SMS_DRAFT_ACTIONS) + r"):"
    r"(\{[^\n]*?\})\]\]"
)


def client_tool_marker(tool: str, args: Mapping[str, Any]) -> str:
    return build_client_tool_marker(tool, dict(args))


def sms_send_direct_marker(phone_number: str, body: str) -> str:
    return client_tool_marker(SMS_SEND_DIRECT_TOOL, {"phone_number": phone_number, "body": body})


def sms_draft_send_marker(draft_id: str) -> str:
    return client_tool_marker(SMS_SEND_TOOL, {"draft_id": draft_id})


def sms_draft_cancel_marker(draft_id: str) -> str:
    return client_tool_marker(SMS_CANCEL_TOOL, {"draft_id": draft_id})


def sms_draft_update_marker(draft_id: str, body: str) -> str:
    return client_tool_marker(SMS_DRAFT_UPDATE_TOOL, {"draft_id": draft_id, "body": body})


def stage3_sms_request_context(*, streaming: bool = False) -> str:
    if streaming:
        return (
            "\n\n[SMS SEND REQUEST — Stage 2 could not resolve recipient]\n"
            "The user wants to send a TEXT MESSAGE (SMS). Use sms_send_direct:\n"
            "[[CLIENT_TOOL:contacts.sms_send_direct:{\"phone_number\":\"<number>\",\"body\":\"<message>\"}]]\n"
            "Steps: 1) Figure out who the recipient is from memory/contacts. "
            "2) Compose the message body (rewrite perspective: 'tell X I love her' → 'I love you'). "
            "3) Confirm with the user, then send via sms_send_direct. "
            "NEVER use contacts.call. NEVER use sms_draft for simple sends.\n"
            "[END SMS SEND REQUEST]"
        )
    return (
        "\n\n[SMS SEND REQUEST — Stage 2 could not resolve recipient]\n"
        "Use sms_send_direct: [[CLIENT_TOOL:contacts.sms_send_direct:"
        "{\"phone_number\":\"<number>\",\"body\":\"<message>\"}]]\n"
        "Resolve the recipient, confirm with user, send via sms_send_direct.\n"
        "[END SMS SEND REQUEST]"
    )
