"""Conversation key helpers for Jane web chat routes."""

from __future__ import annotations


def conversation_device_id(
    header_device_id: str | None,
    trusted_cookie: str | None,
    fingerprint: str | None,
) -> str:
    device_id = (header_device_id or "").strip() or (trusted_cookie or "")[:32]
    if not device_id:
        device_id = (fingerprint or "")[:16] or "nodevice"
    return device_id


def build_conversation_key_payload(
    *,
    raw_client_sid: str | None,
    auth_session_id: str | None,
    user_id: str,
    sanitized_user_id: str,
    managed: bool,
    device_id: str,
) -> dict:
    client_session_id = (raw_client_sid or "").strip() or auth_session_id or "default"
    if managed:
        conversation_key = f"{sanitized_user_id}__{device_id}__{client_session_id}"
    else:
        # Legacy Chieh sessions keep their raw client session to avoid churn.
        conversation_key = (raw_client_sid or "").strip() or auth_session_id or "default"

    return {
        "user_id": user_id,
        "sanitized_user_id": sanitized_user_id,
        "device_id": device_id,
        "client_session_id": client_session_id,
        "conversation_key": conversation_key,
        "managed": managed,
    }
