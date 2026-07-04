from jane_web.auth_cookies import (
    AUTH_COOKIE_MAX_AGE_SECONDS,
    AuthCookieSpec,
    apply_auth_cookie_spec,
    auth_cookie_specs,
)


class _Response:
    def __init__(self):
        self.calls = []

    def set_cookie(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def test_auth_cookie_specs_refresh_changed_session_and_trusted_device():
    specs = auth_cookie_specs(
        existing_session_id="old-session",
        session_id="new-session",
        existing_trusted_device_id="old-device",
        trusted_device_id="new-device",
    )

    assert specs == [
        AuthCookieSpec("jane_session", "new-session", max_age=AUTH_COOKIE_MAX_AGE_SECONDS),
        AuthCookieSpec("jane_trusted_device", "new-device", max_age=AUTH_COOKIE_MAX_AGE_SECONDS),
    ]


def test_auth_cookie_specs_skips_unchanged_or_missing_values():
    assert auth_cookie_specs(
        existing_session_id="session",
        session_id="session",
        existing_trusted_device_id="device",
        trusted_device_id="device",
    ) == []
    assert auth_cookie_specs(
        existing_session_id=None,
        session_id=None,
        existing_trusted_device_id=None,
        trusted_device_id=None,
    ) == []


def test_auth_cookie_specs_allows_route_cookie_names():
    specs = auth_cookie_specs(
        existing_session_id=None,
        session_id="session",
        existing_trusted_device_id=None,
        trusted_device_id="device",
        session_cookie_name="s",
        trusted_device_cookie_name="t",
        max_age=30,
    )

    assert specs == [
        AuthCookieSpec("s", "session", max_age=30),
        AuthCookieSpec("t", "device", max_age=30),
    ]


def test_apply_auth_cookie_spec_sets_response_cookie_attributes():
    response = _Response()
    spec = AuthCookieSpec("cookie-name", "cookie-value", max_age=45, httponly=False, samesite="strict")

    apply_auth_cookie_spec(response, spec, secure=True)

    assert response.calls == [
        (
            ("cookie-name", "cookie-value"),
            {"httponly": False, "secure": True, "samesite": "strict", "max_age": 45},
        )
    ]
