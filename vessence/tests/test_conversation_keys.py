from jane_web.conversation_keys import build_conversation_key_payload, conversation_device_id


def test_conversation_device_id_prefers_header_then_trusted_cookie_then_fingerprint():
    trusted = "trusted-cookie-value" * 3
    fingerprint = "fingerprint-abcdef"
    assert conversation_device_id(" header ", "trusted", "fingerprint") == "header"
    assert conversation_device_id("", trusted, "fingerprint") == trusted[:32]
    assert conversation_device_id("", "", fingerprint) == fingerprint[:16]
    assert conversation_device_id("", "", "") == "nodevice"


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
