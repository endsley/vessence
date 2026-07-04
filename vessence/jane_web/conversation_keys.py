"""Conversation key helpers for Jane web chat routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def load_scoped_session_resolver() -> Callable[[str | None, str | None], str]:
    from agent_skills.user_manager import scoped_session_id

    return scoped_session_id


def load_user_manager_helpers() -> tuple[Callable[[str], bool], Callable[[str], str]]:
    from agent_skills.user_manager import is_managed_user, normalize_user_id

    return is_managed_user, normalize_user_id


def conversation_device_id(
    header_device_id: str | None,
    trusted_cookie: str | None,
    fingerprint: str | None,
) -> str:
    device_id = (header_device_id or "").strip() or (trusted_cookie or "")[:32]
    if not device_id:
        device_id = (fingerprint or "")[:16] or "nodevice"
    return device_id


def conversation_client_session_id(
    raw_client_sid: str | None,
    auth_session_id: str | None,
) -> str:
    return (raw_client_sid or "").strip() or auth_session_id or "default"


def build_conversation_key_payload(
    *,
    raw_client_sid: str | None,
    auth_session_id: str | None,
    user_id: str,
    sanitized_user_id: str,
    managed: bool,
    device_id: str,
) -> dict:
    client_session_id = conversation_client_session_id(raw_client_sid, auth_session_id)
    if managed:
        conversation_key = f"{sanitized_user_id}__{device_id}__{client_session_id}"
    else:
        # Legacy Chieh sessions keep their raw client session to avoid churn.
        conversation_key = client_session_id

    return {
        "user_id": user_id,
        "sanitized_user_id": sanitized_user_id,
        "device_id": device_id,
        "client_session_id": client_session_id,
        "conversation_key": conversation_key,
        "managed": managed,
    }


def scoped_conversation_session_id(
    user_id: str | None,
    session_id: str | None,
    *,
    scoped_resolver_loader: Callable[[], Callable[[str | None, str | None], str]] = (
        load_scoped_session_resolver
    ),
) -> str:
    try:
        return scoped_resolver_loader()(user_id, session_id)
    except Exception:
        return (session_id or "").strip() or "default"


def safe_auth_session_id(request: Any, get_session_id_fn: Callable[[Any], str | None]) -> str | None:
    try:
        return get_session_id_fn(request)
    except Exception:
        return None


def resolved_conversation_user_id(
    auth_session_id: str | None,
    *,
    get_session_user_fn: Callable[[str | None], str | None],
    default_user_id_fn: Callable[[], str],
) -> str:
    return (get_session_user_fn(auth_session_id) if auth_session_id else None) or default_user_id_fn()


def managed_user_context(
    user_id: str,
    user_manager_loader: Callable[
        [],
        tuple[Callable[[str], bool], Callable[[str], str]],
    ] = load_user_manager_helpers,
) -> tuple[str, bool]:
    try:
        is_managed_user, normalize_user_id = user_manager_loader()
        return normalize_user_id(user_id), is_managed_user(user_id)
    except Exception:
        return user_id, False


def safe_trusted_device_cookie(
    request: Any,
    get_trusted_device_cookie_id_fn: Callable[[Any], str | None],
) -> str | None:
    try:
        return get_trusted_device_cookie_id_fn(request)
    except Exception:
        return None


def fallback_device_fingerprint(
    request: Any,
    *,
    header_device_id: str,
    trusted_cookie: str | None,
    device_fingerprint_fn: Callable[[Any], str],
) -> str:
    if header_device_id or trusted_cookie:
        return ""
    try:
        return device_fingerprint_fn(request)
    except Exception:
        return ""


def resolve_conversation_key_payload(
    request: Any,
    body: Any,
    *,
    get_session_id_fn: Callable[[Any], str | None],
    get_session_user_fn: Callable[[str | None], str | None],
    default_user_id_fn: Callable[[], str],
    get_trusted_device_cookie_id_fn: Callable[[Any], str | None],
    device_fingerprint_fn: Callable[[Any], str],
    user_manager_loader: Callable[
        [],
        tuple[Callable[[str], bool], Callable[[str], str]],
    ] = load_user_manager_helpers,
) -> dict:
    raw_client_sid = (getattr(body, "session_id", None) or "").strip()
    auth_session_id = safe_auth_session_id(request, get_session_id_fn)
    user_id = resolved_conversation_user_id(
        auth_session_id,
        get_session_user_fn=get_session_user_fn,
        default_user_id_fn=default_user_id_fn,
    )
    sanitized_user_id, managed = managed_user_context(user_id, user_manager_loader)

    header_device_id = (request.headers.get("x-jane-device-id") or "").strip()
    trusted_cookie = safe_trusted_device_cookie(request, get_trusted_device_cookie_id_fn)
    fingerprint = fallback_device_fingerprint(
        request,
        header_device_id=header_device_id,
        trusted_cookie=trusted_cookie,
        device_fingerprint_fn=device_fingerprint_fn,
    )
    device_id = conversation_device_id(header_device_id, trusted_cookie, fingerprint)
    return build_conversation_key_payload(
        raw_client_sid=raw_client_sid,
        auth_session_id=auth_session_id,
        user_id=user_id,
        sanitized_user_id=sanitized_user_id,
        managed=managed,
        device_id=device_id,
    )
