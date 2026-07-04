from jane_web.conversation_keys import (
    build_conversation_key_payload,
    conversation_client_session_id,
    conversation_device_id,
    fallback_device_fingerprint,
    managed_user_context,
    resolve_conversation_key_payload,
    resolved_conversation_user_id,
    safe_auth_session_id,
    safe_trusted_device_cookie,
    scoped_conversation_session_id,
)


def test_conversation_device_id_prefers_header_then_trusted_cookie_then_fingerprint():
    trusted = "trusted-cookie-value" * 3
    fingerprint = "fingerprint-abcdef"
    assert conversation_device_id(" header ", "trusted", "fingerprint") == "header"
    assert conversation_device_id("", trusted, "fingerprint") == trusted[:32]
    assert conversation_device_id("", "", fingerprint) == fingerprint[:16]
    assert conversation_device_id("", "", "") == "nodevice"


def test_conversation_client_session_id_prefers_raw_then_auth_then_default():
    assert conversation_client_session_id(" client ", "auth") == "client"
    assert conversation_client_session_id("", "auth") == "auth"
    assert conversation_client_session_id(None, None) == "default"


def test_build_conversation_key_payload_for_managed_user():
    payload = build_conversation_key_payload(
        raw_client_sid="client",
        auth_session_id="auth",
        user_id="user@example.com",
        sanitized_user_id="user_example_com",
        managed=True,
        device_id="device",
    )

    assert payload == {
        "user_id": "user@example.com",
        "sanitized_user_id": "user_example_com",
        "device_id": "device",
        "client_session_id": "client",
        "conversation_key": "user_example_com__device__client",
        "managed": True,
    }


def test_build_conversation_key_payload_for_unmanaged_preserves_legacy_key():
    payload = build_conversation_key_payload(
        raw_client_sid=" client ",
        auth_session_id="auth",
        user_id="chieh",
        sanitized_user_id="chieh",
        managed=False,
        device_id="device",
    )

    assert payload["client_session_id"] == "client"
    assert payload["conversation_key"] == "client"

    fallback = build_conversation_key_payload(
        raw_client_sid="",
        auth_session_id="auth",
        user_id="chieh",
        sanitized_user_id="chieh",
        managed=False,
        device_id="device",
    )
    assert fallback["client_session_id"] == "auth"
    assert fallback["conversation_key"] == "auth"


def test_scoped_conversation_session_id_uses_loaded_resolver():
    def loader():
        return lambda user_id, session_id: f"{user_id}:{session_id}"

    assert scoped_conversation_session_id(
        "user@example.com",
        "jane_android",
        scoped_resolver_loader=loader,
    ) == "user@example.com:jane_android"


def test_scoped_conversation_session_id_falls_back_to_sanitized_session_or_default():
    def broken_loader():
        raise RuntimeError("user manager unavailable")

    assert scoped_conversation_session_id(
        "user@example.com",
        " jane_android ",
        scoped_resolver_loader=broken_loader,
    ) == "jane_android"
    assert scoped_conversation_session_id(
        "user@example.com",
        "",
        scoped_resolver_loader=broken_loader,
    ) == "default"


def test_conversation_key_safe_resolution_helpers_preserve_fallbacks() -> None:
    request = object()

    assert safe_auth_session_id(request, lambda _request: "auth") == "auth"
    assert safe_auth_session_id(request, lambda _request: (_ for _ in ()).throw(RuntimeError)) is None
    assert resolved_conversation_user_id(
        "auth",
        get_session_user_fn=lambda session_id: "user@example.com",
        default_user_id_fn=lambda: "chieh",
    ) == "user@example.com"
    assert resolved_conversation_user_id(
        None,
        get_session_user_fn=lambda session_id: "ignored",
        default_user_id_fn=lambda: "chieh",
    ) == "chieh"
    assert managed_user_context(
        "user@example.com",
        lambda: (lambda user_id: True, lambda user_id: "user_example_com"),
    ) == ("user_example_com", True)
    assert managed_user_context("chieh", lambda: (_ for _ in ()).throw(RuntimeError)) == (
        "chieh",
        False,
    )
    assert safe_trusted_device_cookie(request, lambda _request: "trusted") == "trusted"
    assert safe_trusted_device_cookie(request, lambda _request: (_ for _ in ()).throw(RuntimeError)) is None
    assert fallback_device_fingerprint(
        request,
        header_device_id="device",
        trusted_cookie=None,
        device_fingerprint_fn=lambda _request: "fingerprint",
    ) == ""
    assert fallback_device_fingerprint(
        request,
        header_device_id="",
        trusted_cookie=None,
        device_fingerprint_fn=lambda _request: "fingerprint",
    ) == "fingerprint"


def test_resolve_conversation_key_payload_for_managed_user_uses_header_device() -> None:
    class Body:
        session_id = " client "

    class Request:
        headers = {"x-jane-device-id": " device "}

    def user_manager_loader():
        return (
            lambda user_id: user_id == "user@example.com",
            lambda user_id: user_id.replace("@", "_").replace(".", "_"),
        )

    payload = resolve_conversation_key_payload(
        Request(),
        Body(),
        get_session_id_fn=lambda request: "auth-session",
        get_session_user_fn=lambda session_id: "user@example.com",
        default_user_id_fn=lambda: "chieh",
        get_trusted_device_cookie_id_fn=lambda request: "trusted-cookie",
        device_fingerprint_fn=lambda request: "fingerprint",
        user_manager_loader=user_manager_loader,
    )

    assert payload == {
        "user_id": "user@example.com",
        "sanitized_user_id": "user_example_com",
        "device_id": "device",
        "client_session_id": "client",
        "conversation_key": "user_example_com__device__client",
        "managed": True,
    }


def test_resolve_conversation_key_payload_falls_back_when_user_manager_unavailable() -> None:
    class Body:
        session_id = ""

    class Request:
        headers = {}

    trusted = "trusted-cookie-value" * 3

    def broken_session_id(request):
        raise RuntimeError("no session")

    def broken_user_manager_loader():
        raise RuntimeError("user manager unavailable")

    payload = resolve_conversation_key_payload(
        Request(),
        Body(),
        get_session_id_fn=broken_session_id,
        get_session_user_fn=lambda session_id: "ignored",
        default_user_id_fn=lambda: "chieh",
        get_trusted_device_cookie_id_fn=lambda request: trusted,
        device_fingerprint_fn=lambda request: "fingerprint",
        user_manager_loader=broken_user_manager_loader,
    )

    assert payload == {
        "user_id": "chieh",
        "sanitized_user_id": "chieh",
        "device_id": trusted[:32],
        "client_session_id": "default",
        "conversation_key": "default",
        "managed": False,
    }
