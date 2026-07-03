"""Small request inspection helpers for Jane web."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


def session_log_id(session_id: str | None) -> str:
    return session_id[:12] if session_id else "none"


def client_ip(request: Any) -> str:
    """Get the real client IP, respecting Cloudflare and reverse proxy headers."""

    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Real-IP")
        or (request.client.host if request.client else None)
        or "unknown"
    )


def is_local_browser_access(request: Any) -> bool:
    """Check if request is truly local and not proxied through Cloudflare."""

    if request.headers.get("cf-connecting-ip"):
        return False
    client_host = request.client.host if request.client else ""
    return client_host in ("127.0.0.1", "::1")


def cookie_secure_flag(request: Any) -> bool:
    """Return True only if the request came over HTTPS or via an HTTPS proxy."""

    if request.url.scheme == "https":
        return True
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return forwarded_proto == "https"


def is_single_user_no_auth_mode(environ: Mapping[str, str] = os.environ) -> bool:
    return not environ.get("GOOGLE_CLIENT_ID", "").strip()


def is_local_request(request: Any) -> bool:
    """True if the request is from localhost and not from a proxy."""

    if request.headers.get("cf-connecting-ip"):
        return False
    if request.headers.get("x-forwarded-for"):
        return False
    client_host = request.client.host if request.client else ""
    return client_host in ("127.0.0.1", "::1", "localhost")


def is_android_webview_request(request: Any) -> bool:
    user_agent = request.headers.get("user-agent", "")
    return "VessencesAndroid/" in user_agent
