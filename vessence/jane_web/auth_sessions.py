"""Session-resolution helpers for Jane web auth dependencies."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any


def chat_stream_session_for_request(
    request: Any,
    *,
    body_session_id: str | None,
    get_or_bootstrap_session_fn: Callable[[Any], tuple[str | None, str | None]],
    is_local_control_ip_fn: Callable[[str], bool],
) -> tuple[str | None, str | None]:
    client_host = request.client.host if getattr(request, "client", None) else ""
    if is_local_control_ip_fn(client_host):
        return body_session_id or "prompt_queue_session", None
    return get_or_bootstrap_session_fn(request)


def required_session_id_for_request(
    request: Any,
    *,
    trusted_device_session_cache: MutableMapping[str, str],
    get_session_id_fn: Callable[[Any], str | None],
    get_trusted_device_cookie_id_fn: Callable[[Any], str | None],
    device_fingerprint_fn: Callable[[Any], str],
    validate_session_fn: Callable[[str | None, str], bool],
    get_trusted_device_by_id_fn: Callable[[str | None], dict[str, Any] | None],
    create_session_fn: Callable[..., str],
    default_user_id_fn: Callable[[], str],
    is_single_user_no_auth_mode_fn: Callable[[], bool],
    is_local_request_fn: Callable[[Any], bool],
) -> str | None:
    if is_single_user_no_auth_mode_fn() and is_local_request_fn(request):
        return "single_user_local"

    if not request.headers.get("cf-connecting-ip"):
        client_host = request.client.host if request.client else ""
        if client_host in ("127.0.0.1", "::1"):
            return request.query_params.get("session_id") or "internal"

    session_id = get_session_id_fn(request)
    fingerprint = device_fingerprint_fn(request)
    if session_id and validate_session_fn(session_id, fingerprint):
        return session_id

    trusted_cookie = get_trusted_device_cookie_id_fn(request)
    if trusted_cookie:
        cached = trusted_device_session_cache.get(trusted_cookie)
        if cached and validate_session_fn(cached, fingerprint):
            return cached
        trusted_row = get_trusted_device_by_id_fn(trusted_cookie)
        if trusted_row:
            new_session = create_session_fn(
                fingerprint,
                trusted=True,
                user_id=trusted_row["label"] or default_user_id_fn(),
            )
            trusted_device_session_cache[trusted_cookie] = new_session
            return new_session
    return None


def request_has_share_or_auth(
    request: Any,
    path: str,
    *,
    get_session_id_fn: Callable[[Any], str | None],
    get_trusted_device_cookie_id_fn: Callable[[Any], str | None],
    device_fingerprint_fn: Callable[[Any], str],
    validate_session_fn: Callable[[str | None, str], bool],
    get_trusted_device_by_id_fn: Callable[[str | None], dict[str, Any] | None],
    validate_share_fn: Callable[[str | None], dict[str, Any] | None],
    is_single_user_no_auth_mode_fn: Callable[[], bool],
    is_local_request_fn: Callable[[Any], bool],
) -> bool:
    if is_single_user_no_auth_mode_fn() and is_local_request_fn(request):
        return True

    session_id = get_session_id_fn(request)
    fingerprint = device_fingerprint_fn(request)
    if session_id and validate_session_fn(session_id, fingerprint):
        return True

    trusted_cookie = get_trusted_device_cookie_id_fn(request)
    if trusted_cookie and get_trusted_device_by_id_fn(trusted_cookie):
        return True

    share_code = request.cookies.get("share_code")
    if share_code:
        share = validate_share_fn(share_code)
        if _share_allows_path(share, path):
            return True
    return False


def _share_allows_path(share: dict[str, Any] | None, path: str) -> bool:
    if not share:
        return False
    share_path = share["path"]
    return path.startswith(share_path) or share_path == "/"


def _bootstrap_user_id(row: dict[str, Any] | None, default_user_id_fn: Callable[[], str]) -> str:
    return (row or {}).get("label") or default_user_id_fn()


def _create_and_prewarm_session(
    *,
    fingerprint: str,
    trusted: bool,
    user_id: str,
    create_session_fn: Callable[..., str],
    prewarm_session_fn: Callable[[str, str], Any],
) -> str:
    session_id = create_session_fn(fingerprint, trusted=trusted, user_id=user_id)
    prewarm_session_fn(session_id, user_id)
    return session_id


def _create_trusted_row_session(
    trusted_row: dict[str, Any],
    *,
    fingerprint: str,
    create_session_fn: Callable[..., str],
    default_user_id_fn: Callable[[], str],
    prewarm_session_fn: Callable[[str, str], Any],
) -> tuple[str, str]:
    user_id = _bootstrap_user_id(trusted_row, default_user_id_fn)
    session_id = _create_and_prewarm_session(
        fingerprint=fingerprint,
        trusted=True,
        user_id=user_id,
        create_session_fn=create_session_fn,
        prewarm_session_fn=prewarm_session_fn,
    )
    return session_id, trusted_row["id"]


def _trusted_bootstrap_row(
    *,
    trusted_cookie_id: str | None,
    fingerprint: str,
    get_trusted_device_by_id_fn: Callable[[str | None], dict[str, Any] | None],
    get_trusted_device_by_fingerprint_fn: Callable[[str], dict[str, Any] | None],
) -> tuple[dict[str, Any] | None, str | None]:
    if trusted_cookie_id:
        trusted_row = get_trusted_device_by_id_fn(trusted_cookie_id)
        if trusted_row:
            return trusted_row, "trusted-cookie"

    trusted_row = get_trusted_device_by_fingerprint_fn(fingerprint)
    if trusted_row:
        return trusted_row, "fingerprint-match"
    return None, None


def bootstrap_session_for_request(
    request: Any,
    *,
    get_session_id_fn: Callable[[Any], str | None],
    get_trusted_device_cookie_id_fn: Callable[[Any], str | None],
    device_fingerprint_fn: Callable[[Any], str],
    validate_session_fn: Callable[[str | None, str], bool],
    create_session_fn: Callable[..., str],
    get_session_user_fn: Callable[[str | None], str | None],
    default_user_id_fn: Callable[[], str],
    get_trusted_device_by_id_fn: Callable[[str | None], dict[str, Any] | None],
    get_trusted_device_by_fingerprint_fn: Callable[[str], dict[str, Any] | None],
    is_single_user_no_auth_mode_fn: Callable[[], bool],
    is_local_request_fn: Callable[[Any], bool],
    is_local_browser_access_fn: Callable[[Any], bool],
    client_ip_fn: Callable[[Any], str],
    session_log_id_fn: Callable[[str | None], str],
    prewarm_session_fn: Callable[[str, str], Any],
    logger: Any | None = None,
) -> tuple[str | None, str | None]:
    if is_single_user_no_auth_mode_fn() and is_local_request_fn(request):
        fingerprint = device_fingerprint_fn(request)
        existing = get_session_id_fn(request)
        if existing and validate_session_fn(existing, fingerprint):
            return existing, get_trusted_device_cookie_id_fn(request)
        session_id = create_session_fn(fingerprint, trusted=True, user_id=default_user_id_fn())
        return session_id, None

    session_id = get_session_id_fn(request)
    fingerprint = device_fingerprint_fn(request)
    if session_id and validate_session_fn(session_id, fingerprint):
        trusted_cookie = get_trusted_device_cookie_id_fn(request)
        if logger is not None:
            logger.info(
                "Session bootstrap reused existing session=%s trusted_cookie=%s ip=%s",
                session_log_id_fn(session_id),
                bool(trusted_cookie),
                client_ip_fn(request),
            )
        prewarm_session_fn(session_id, get_session_user_fn(session_id) or default_user_id_fn())
        return session_id, trusted_cookie

    trusted_cookie_id = get_trusted_device_cookie_id_fn(request)
    trusted_row, trusted_source = _trusted_bootstrap_row(
        trusted_cookie_id=trusted_cookie_id,
        fingerprint=fingerprint,
        get_trusted_device_by_id_fn=get_trusted_device_by_id_fn,
        get_trusted_device_by_fingerprint_fn=get_trusted_device_by_fingerprint_fn,
    )
    if trusted_row:
        session_id, trusted_device_id = _create_trusted_row_session(
            trusted_row,
            fingerprint=fingerprint,
            create_session_fn=create_session_fn,
            default_user_id_fn=default_user_id_fn,
            prewarm_session_fn=prewarm_session_fn,
        )
        if logger is not None:
            logger.info(
                "Session bootstrap created session=%s via %s trusted_device=%s ip=%s",
                session_log_id_fn(session_id),
                trusted_source,
                trusted_device_id,
                client_ip_fn(request),
            )
        return session_id, trusted_device_id

    if is_local_browser_access_fn(request):
        user_id = default_user_id_fn()
        session_id = _create_and_prewarm_session(
            fingerprint=fingerprint,
            trusted=False,
            user_id=user_id,
            create_session_fn=create_session_fn,
            prewarm_session_fn=prewarm_session_fn,
        )
        if logger is not None:
            logger.info(
                "Session bootstrap created local session=%s host=%s ip=%s",
                session_log_id_fn(session_id),
                request.headers.get("host", ""),
                client_ip_fn(request),
            )
        return session_id, None

    if logger is not None:
        logger.info(
            "Session bootstrap found no authenticated session ip=%s trusted_cookie=%s",
            client_ip_fn(request),
            bool(trusted_cookie_id),
        )
    return None, None
