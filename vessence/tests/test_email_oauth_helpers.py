import pytest

from agent_skills import email_oauth
from agent_skills.email_oauth_helpers import (
    REFRESH_LEEWAY_SECONDS,
    TOKEN_FILE_PREFIX,
    account_token_file,
    apply_refresh_response,
    build_token_payload,
    normalized_user_id,
    should_refresh_token,
    should_write_legacy_token,
    token_slug,
)


def test_email_oauth_reexports_private_normalizers():
    assert email_oauth._normalized_user_id is normalized_user_id
    assert email_oauth._token_slug is token_slug


def test_normalized_user_id_and_token_slug_preserve_storage_rules():
    assert normalized_user_id(" Chieh.T.Wu@GMAIL.com ") == "chieh.t.wu@gmail.com"
    assert token_slug("Chieh.T+tag@Example.COM") == "chieh_t_tag_at_example_com"
    assert token_slug("  ") == ""


def test_account_token_file_uses_slugged_user_and_prefix():
    assert account_token_file("/tmp/creds", "Chieh.T.Wu@gmail.com") == (
        f"/tmp/creds/{TOKEN_FILE_PREFIX}chieh_t_wu_at_gmail_com.json"
    )
    assert account_token_file("/tmp/creds", "u@example.com", token_file_prefix="x_") == (
        "/tmp/creds/x_u_at_example_com.json"
    )
    with pytest.raises(ValueError, match="account-specific"):
        account_token_file("/tmp/creds", "   ")


def test_build_token_payload_normalizes_user_and_applies_defaults():
    payload = build_token_payload(
        " User@Example.com ",
        {"access_token": "a", "expires_at": 123, "scope": "gmail"},
        stored_at=456.0,
    )

    assert payload == {
        "user_id": "user@example.com",
        "access_token": "a",
        "refresh_token": "",
        "token_type": "Bearer",
        "expires_at": 123,
        "scope": "gmail",
        "stored_at": 456.0,
    }
    with pytest.raises(ValueError, match="Gmail user_id is required"):
        build_token_payload(" ", {}, stored_at=1.0)


def test_should_write_legacy_token_preserves_default_account_rule():
    assert should_write_legacy_token("", "chieh@example.com")
    assert should_write_legacy_token("chieh@example.com", "chieh@example.com")
    assert not should_write_legacy_token("chieh@example.com", "julia@example.com")


def test_should_refresh_token_uses_five_minute_leeway():
    assert REFRESH_LEEWAY_SECONDS == 300
    assert not should_refresh_token(2000, now=1600)
    assert should_refresh_token(2000, now=1700)
    assert should_refresh_token(0, now=100)


def test_apply_refresh_response_updates_token_data_in_place():
    token_data = {
        "access_token": "old",
        "refresh_token": "refresh-old",
        "expires_at": 10,
    }

    result = apply_refresh_response(
        token_data,
        {"access_token": "new", "expires_in": 1800},
        now=100.0,
    )

    assert result is token_data
    assert token_data == {
        "access_token": "new",
        "refresh_token": "refresh-old",
        "expires_at": 1900.0,
    }

    apply_refresh_response(
        token_data,
        {"access_token": "newer", "refresh_token": "refresh-new"},
        now=200.0,
    )
    assert token_data["access_token"] == "newer"
    assert token_data["refresh_token"] == "refresh-new"
    assert token_data["expires_at"] == 3800.0
