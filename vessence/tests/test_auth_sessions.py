from types import SimpleNamespace

from jane_web.auth_sessions import (
    _create_trusted_row_session,
    _share_allows_path,
    _trusted_bootstrap_row,
    bootstrap_session_for_request,
    chat_stream_session_for_request,
    request_has_share_or_auth,
    required_session_id_for_request,
)


def _request(*, headers=None, cookies=None, query=None, host="203.0.113.5"):
    return SimpleNamespace(
        headers=headers or {},
        cookies=cookies or {},
        query_params=query or {},
        client=SimpleNamespace(host=host) if host is not None else None,
    )


def _resolve(request, **overrides):
    cache = overrides.pop("cache", {})
    created = []

    defaults = {
        "trusted_device_session_cache": cache,
        "get_session_id_fn": lambda req: req.cookies.get("jane_session"),
        "get_trusted_device_cookie_id_fn": lambda req: req.cookies.get("jane_trusted_device"),
        "device_fingerprint_fn": lambda req: "fingerprint",
        "validate_session_fn": lambda session_id, fingerprint: session_id == "valid-session",
        "get_trusted_device_by_id_fn": lambda device_id: None,
        "create_session_fn": lambda fingerprint, trusted, user_id: (
            created.append((fingerprint, trusted, user_id)) or "new-session"
        ),
        "default_user_id_fn": lambda: "default-user",
        "is_single_user_no_auth_mode_fn": lambda: False,
        "is_local_request_fn": lambda req: False,
    }
    defaults.update(overrides)
    return required_session_id_for_request(request, **defaults), cache, created


def test_chat_stream_session_uses_body_session_for_local_control_request() -> None:
    calls = []

    assert chat_stream_session_for_request(
        _request(host="127.0.0.1"),
        body_session_id="body-session",
        get_or_bootstrap_session_fn=lambda request: calls.append(request) or ("auth", "trusted"),
        is_local_control_ip_fn=lambda host: host == "127.0.0.1",
    ) == ("body-session", None)
    assert calls == []


def test_chat_stream_session_uses_prompt_queue_fallback_for_local_control_request() -> None:
    assert chat_stream_session_for_request(
        _request(host="::1"),
        body_session_id=None,
        get_or_bootstrap_session_fn=lambda request: ("auth", "trusted"),
        is_local_control_ip_fn=lambda host: host == "::1",
    ) == ("prompt_queue_session", None)


def test_chat_stream_session_delegates_non_local_requests_to_bootstrap() -> None:
    request = _request(host="198.51.100.5")
    calls = []

    assert chat_stream_session_for_request(
        request,
        body_session_id="body-session",
        get_or_bootstrap_session_fn=lambda req: calls.append(req) or ("auth-session", "trusted-id"),
        is_local_control_ip_fn=lambda host: False,
    ) == ("auth-session", "trusted-id")
    assert calls == [request]


def test_required_session_allows_single_user_local_mode_first() -> None:
    session_id, _, _ = _resolve(
        _request(host="127.0.0.1", query={"session_id": "query-session"}),
        is_single_user_no_auth_mode_fn=lambda: True,
        is_local_request_fn=lambda req: True,
    )

    assert session_id == "single_user_local"


def test_required_session_allows_localhost_bypass_when_not_cloudflare() -> None:
    session_id, _, _ = _resolve(
        _request(host="127.0.0.1", query={"session_id": "query-session"})
    )
    fallback, _, _ = _resolve(_request(host="::1"))
    proxied, _, _ = _resolve(
        _request(headers={"cf-connecting-ip": "198.51.100.1"}, host="127.0.0.1")
    )

    assert session_id == "query-session"
    assert fallback == "internal"
    assert proxied is None


def test_required_session_uses_valid_session_cookie() -> None:
    session_id, _, _ = _resolve(_request(cookies={"jane_session": "valid-session"}))

    assert session_id == "valid-session"


def test_required_session_reuses_cached_trusted_device_session() -> None:
    session_id, _, _ = _resolve(
        _request(cookies={"jane_trusted_device": "trusted-device"}),
        cache={"trusted-device": "cached-session"},
        validate_session_fn=lambda session_id, fingerprint: session_id == "cached-session",
    )

    assert session_id == "cached-session"


def test_required_session_creates_and_caches_session_for_trusted_device_cookie() -> None:
    session_id, cache, created = _resolve(
        _request(cookies={"jane_trusted_device": "trusted-device"}),
        get_trusted_device_by_id_fn=lambda device_id: {"id": device_id, "label": ""},
    )

    assert session_id == "new-session"
    assert cache == {"trusted-device": "new-session"}
    assert created == [("fingerprint", True, "default-user")]


def _has_share_or_auth(request, path="/vault/file.txt", **overrides):
    defaults = {
        "get_session_id_fn": lambda req: req.cookies.get("jane_session"),
        "get_trusted_device_cookie_id_fn": lambda req: req.cookies.get("jane_trusted_device"),
        "device_fingerprint_fn": lambda req: "fingerprint",
        "validate_session_fn": lambda session_id, fingerprint: session_id == "valid-session",
        "get_trusted_device_by_id_fn": lambda device_id: None,
        "validate_share_fn": lambda share_code: None,
        "is_single_user_no_auth_mode_fn": lambda: False,
        "is_local_request_fn": lambda req: False,
    }
    defaults.update(overrides)
    return request_has_share_or_auth(request, path, **defaults)


def test_share_or_auth_allows_single_user_local_mode() -> None:
    assert _has_share_or_auth(
        _request(host="127.0.0.1"),
        is_single_user_no_auth_mode_fn=lambda: True,
        is_local_request_fn=lambda req: True,
    )


def test_share_or_auth_allows_valid_session_or_trusted_device_cookie() -> None:
    assert _has_share_or_auth(_request(cookies={"jane_session": "valid-session"}))
    assert _has_share_or_auth(
        _request(cookies={"jane_trusted_device": "trusted-device"}),
        get_trusted_device_by_id_fn=lambda device_id: {"id": device_id},
    )


def test_share_or_auth_allows_matching_share_cookie_path() -> None:
    assert _has_share_or_auth(
        _request(cookies={"share_code": "share-1"}),
        path="/vault/shared/file.txt",
        validate_share_fn=lambda code: {"path": "/vault/shared"},
    )
    assert _has_share_or_auth(
        _request(cookies={"share_code": "share-root"}),
        path="/vault/anything.txt",
        validate_share_fn=lambda code: {"path": "/"},
    )


def test_share_or_auth_rejects_missing_or_nonmatching_credentials() -> None:
    assert not _has_share_or_auth(_request())
    assert not _has_share_or_auth(
        _request(cookies={"share_code": "share-1"}),
        path="/vault/private/file.txt",
        validate_share_fn=lambda code: {"path": "/vault/shared"},
    )


def test_share_allows_path_preserves_legacy_prefix_semantics() -> None:
    assert _share_allows_path({"path": "/"}, "/vault/anything.txt")
    assert _share_allows_path({"path": "/vault/shared"}, "/vault/shared/file.txt")
    assert _share_allows_path({"path": "/vault/shared"}, "/vault/sharedness/file.txt")
    assert not _share_allows_path({"path": "/vault/shared"}, "/vault/private/file.txt")
    assert not _share_allows_path(None, "/vault/shared/file.txt")


def _bootstrap(request, **overrides):
    created = []
    prewarmed = []
    defaults = {
        "get_session_id_fn": lambda req: req.cookies.get("jane_session"),
        "get_trusted_device_cookie_id_fn": lambda req: req.cookies.get("jane_trusted_device"),
        "device_fingerprint_fn": lambda req: "fingerprint",
        "validate_session_fn": lambda session_id, fingerprint: session_id == "valid-session",
        "create_session_fn": lambda fingerprint, trusted, user_id: (
            created.append((fingerprint, trusted, user_id)) or f"created-{len(created)}"
        ),
        "get_session_user_fn": lambda session_id: "session-user" if session_id == "valid-session" else None,
        "default_user_id_fn": lambda: "default-user",
        "get_trusted_device_by_id_fn": lambda device_id: None,
        "get_trusted_device_by_fingerprint_fn": lambda fingerprint: None,
        "is_single_user_no_auth_mode_fn": lambda: False,
        "is_local_request_fn": lambda req: False,
        "is_local_browser_access_fn": lambda req: False,
        "client_ip_fn": lambda req: "198.51.100.1",
        "session_log_id_fn": lambda session_id: session_id[:12] if session_id else "none",
        "prewarm_session_fn": lambda session_id, user_id: prewarmed.append((session_id, user_id)),
        "logger": None,
    }
    defaults.update(overrides)
    return bootstrap_session_for_request(request, **defaults), created, prewarmed


def test_bootstrap_session_single_user_local_reuses_valid_existing_without_prewarm() -> None:
    result, created, prewarmed = _bootstrap(
        _request(cookies={"jane_session": "valid-session", "jane_trusted_device": "trusted"}),
        is_single_user_no_auth_mode_fn=lambda: True,
        is_local_request_fn=lambda req: True,
    )

    assert result == ("valid-session", "trusted")
    assert created == []
    assert prewarmed == []


def test_bootstrap_session_reuses_valid_session_and_prewarms_session_user() -> None:
    result, created, prewarmed = _bootstrap(
        _request(cookies={"jane_session": "valid-session", "jane_trusted_device": "trusted"})
    )

    assert result == ("valid-session", "trusted")
    assert created == []
    assert prewarmed == [("valid-session", "session-user")]


def test_bootstrap_session_creates_from_trusted_cookie_row() -> None:
    result, created, prewarmed = _bootstrap(
        _request(cookies={"jane_trusted_device": "trusted"}),
        get_trusted_device_by_id_fn=lambda device_id: {"id": device_id, "label": "trusted-user"},
    )

    assert result == ("created-1", "trusted")
    assert created == [("fingerprint", True, "trusted-user")]
    assert prewarmed == [("created-1", "trusted-user")]


def test_create_trusted_row_session_uses_label_or_default_user() -> None:
    created = []
    prewarmed = []

    result = _create_trusted_row_session(
        {"id": "trusted-1", "label": ""},
        fingerprint="fingerprint",
        create_session_fn=lambda fingerprint, trusted, user_id: (
            created.append((fingerprint, trusted, user_id)) or "session-1"
        ),
        default_user_id_fn=lambda: "default-user",
        prewarm_session_fn=lambda session_id, user_id: prewarmed.append((session_id, user_id)),
    )

    assert result == ("session-1", "trusted-1")
    assert created == [("fingerprint", True, "default-user")]
    assert prewarmed == [("session-1", "default-user")]


def test_trusted_bootstrap_row_prefers_cookie_row_before_fingerprint() -> None:
    calls = []

    row, source = _trusted_bootstrap_row(
        trusted_cookie_id="trusted-cookie",
        fingerprint="fingerprint",
        get_trusted_device_by_id_fn=lambda device_id: calls.append(("id", device_id)) or {"id": device_id},
        get_trusted_device_by_fingerprint_fn=lambda fingerprint: calls.append(("fp", fingerprint)) or {
            "id": "fp-device"
        },
    )

    assert row == {"id": "trusted-cookie"}
    assert source == "trusted-cookie"
    assert calls == [("id", "trusted-cookie")]


def test_trusted_bootstrap_row_falls_back_to_fingerprint_match() -> None:
    row, source = _trusted_bootstrap_row(
        trusted_cookie_id="missing-cookie",
        fingerprint="fingerprint",
        get_trusted_device_by_id_fn=lambda device_id: None,
        get_trusted_device_by_fingerprint_fn=lambda fingerprint: {"id": f"{fingerprint}-device"},
    )

    assert row == {"id": "fingerprint-device"}
    assert source == "fingerprint-match"


def test_trusted_bootstrap_row_returns_empty_pair_without_match() -> None:
    assert _trusted_bootstrap_row(
        trusted_cookie_id=None,
        fingerprint="fingerprint",
        get_trusted_device_by_id_fn=lambda device_id: {"id": device_id},
        get_trusted_device_by_fingerprint_fn=lambda fingerprint: None,
    ) == (None, None)


def test_bootstrap_session_creates_from_fingerprint_trusted_device() -> None:
    result, created, prewarmed = _bootstrap(
        _request(),
        get_trusted_device_by_fingerprint_fn=lambda fingerprint: {"id": "fp-device", "label": ""},
    )

    assert result == ("created-1", "fp-device")
    assert created == [("fingerprint", True, "default-user")]
    assert prewarmed == [("created-1", "default-user")]


def test_bootstrap_session_creates_untrusted_session_for_local_browser() -> None:
    result, created, prewarmed = _bootstrap(
        _request(headers={"host": "localhost"}, host="127.0.0.1"),
        is_local_browser_access_fn=lambda req: True,
    )

    assert result == ("created-1", None)
    assert created == [("fingerprint", False, "default-user")]
    assert prewarmed == [("created-1", "default-user")]


def test_bootstrap_session_returns_empty_pair_when_no_auth_path_matches() -> None:
    result, created, prewarmed = _bootstrap(_request())

    assert result == (None, None)
    assert created == []
    assert prewarmed == []
