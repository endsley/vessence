"""Auth-cookie planning helpers for Jane web responses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SESSION_COOKIE = "jane_session"
TRUSTED_DEVICE_COOKIE = "jane_trusted_device"
AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


@dataclass(frozen=True)
class AuthCookieSpec:
    name: str
    value: str
    max_age: int = AUTH_COOKIE_MAX_AGE_SECONDS
    httponly: bool = True
    samesite: str = "lax"


def auth_cookie_specs(
    *,
    existing_session_id: str | None,
    session_id: str | None,
    existing_trusted_device_id: str | None,
    trusted_device_id: str | None,
    session_cookie_name: str = SESSION_COOKIE,
    trusted_device_cookie_name: str = TRUSTED_DEVICE_COOKIE,
    max_age: int = AUTH_COOKIE_MAX_AGE_SECONDS,
) -> list[AuthCookieSpec]:
    """Return auth cookies that need to be refreshed for a response."""
    specs: list[AuthCookieSpec] = []
    if session_id and existing_session_id != session_id:
        specs.append(AuthCookieSpec(session_cookie_name, session_id, max_age=max_age))
    if trusted_device_id and existing_trusted_device_id != trusted_device_id:
        specs.append(AuthCookieSpec(trusted_device_cookie_name, trusted_device_id, max_age=max_age))
    return specs


def apply_auth_cookie_spec(response: Any, spec: AuthCookieSpec, *, secure: bool) -> None:
    response.set_cookie(
        spec.name,
        spec.value,
        httponly=spec.httponly,
        secure=secure,
        samesite=spec.samesite,
        max_age=spec.max_age,
    )
