"""Payload normalization helpers for contact and SMS routes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def contact_insert_values(contact: Mapping[str, Any], synced_at: str) -> tuple[Any, ...] | None:
    display_name = (contact.get("display_name") or "").strip()
    if not display_name:
        return None
    phone_number = (contact.get("phone_number") or "").strip() or None
    email = (contact.get("email") or "").strip() or None
    is_primary = 1 if contact.get("is_primary") else 0
    contact_id = str(contact.get("contact_id", "")).strip() or None
    return (display_name, phone_number, email, is_primary, contact_id, synced_at)


def contact_alias_values(body: Mapping[str, Any]) -> tuple[str, str, Any] | None:
    alias = (body.get("alias") or "").strip()
    phone = (body.get("phone_number") or "").strip()
    if not alias or not phone:
        return None
    return (alias, phone, body.get("display_name"))


def message_insert_values(
    message: Mapping[str, Any],
    synced_at: str,
    *,
    classify_message: Callable[[str, bool], str],
) -> tuple[Any, ...] | None:
    sender = (message.get("sender") or "").strip()
    body = (message.get("body") or "").strip()
    timestamp_ms = message.get("timestamp_ms")
    if not sender or not timestamp_ms:
        return None
    is_read = 1 if message.get("is_read", True) else 0
    is_contact = 1 if message.get("is_contact", False) else 0
    msg_type = classify_message(body, bool(is_contact))
    return (sender, body, timestamp_ms, is_read, is_contact, msg_type, synced_at)
