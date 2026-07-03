from jane_web.cli_login_helpers import (
    append_status_stderr_tail,
    clean_cli_output,
    cli_output_lines,
    cli_binary_for_provider,
    cli_login_debug_payload,
    cli_login_candidates,
    cli_login_process_state,
    extract_claude_auth_url,
    extract_device_code,
    extract_first_auth_url,
    extract_oauth_state,
    mask_email,
    parse_provider_auth_status_output,
    provider_auth_status_base,
    provider_auth_status_command,
    provider_auth_status_error,
    read_cli_transcript_lines,
    unsupported_provider_auth_status,
)


class FakeProcess:
    def __init__(self, poll_result, returncode):
        self._poll_result = poll_result
        self.returncode = returncode

    def poll(self):
        return self._poll_result


def test_cli_login_candidates_and_binary_for_supported_providers():
    assert cli_login_candidates("claude") == [["claude", "auth", "login"]]
    assert cli_login_candidates("gemini") == [["gemini", "auth", "login"]]
    assert cli_login_candidates("openai") == [["codex", "login", "--device-auth"]]
    assert cli_binary_for_provider("claude") == "claude"
    assert cli_binary_for_provider("openai") == "codex"


def test_cli_login_candidates_for_unknown_provider():
    assert cli_login_candidates("unknown") == []
    assert cli_binary_for_provider("unknown") is None


def test_mask_email_preserves_existing_edge_case_outputs():
    assert mask_email("") == ""
    assert mask_email("abc") == "abc..."
    assert mask_email("ab") == "ab..."
    assert mask_email("a@example.com") == "a***@example.com"
    assert mask_email("ab@example.com") == "ab***@example.com"
    assert mask_email("@example.com") == "***@example.com"


def test_read_cli_transcript_lines_handles_missing_and_strips_blank_lines(tmp_path):
    assert read_cli_transcript_lines(None) == []
    assert read_cli_transcript_lines(str(tmp_path / "missing.log")) == []

    path = tmp_path / "auth.log"
    path.write_text("\n first \n\nsecond\n", encoding="utf-8")

    assert read_cli_transcript_lines(str(path)) == ["first", "second"]


def test_cli_login_process_state_handles_missing_running_and_exited_processes():
    assert cli_login_process_state(None) == ("missing", None)
    assert cli_login_process_state(FakeProcess(None, None)) == ("running", None)
    assert cli_login_process_state(FakeProcess(0, 0)) == ("exited", 0)


def test_cli_login_debug_payload_preserves_snapshot_shape_and_transcript_tail():
    payload = cli_login_debug_payload(
        provider="claude",
        process=FakeProcess(1, 1),
        authenticated=True,
        transcript_lines=["one", "two", "three", "four"],
        auth_status={"logged_in": False},
    )

    assert payload == {
        "provider": "claude",
        "process_state": "exited",
        "process_returncode": 1,
        "cli_login_authenticated_flag": True,
        "transcript_tail": ["two", "three", "four"],
        "auth_status": {"logged_in": False},
    }



def test_parse_provider_auth_status_output_reads_json_details():
    details = {"logged_in": False}

    assert parse_provider_auth_status_output(
        details,
        '{"loggedIn": true, "authMethod": "oauth", "email": "user@example.com", "subscriptionType": "pro"}',
    )
    assert details == {
        "logged_in": True,
        "auth_method": "oauth",
        "email_hint": "us***@example.com",
        "subscription_type": "pro",
    }


def test_parse_provider_auth_status_output_falls_back_to_text_tail():
    details = {"logged_in": False}

    assert parse_provider_auth_status_output(details, "line 1\nLogged in as user@example.com")
    assert details["logged_in"] is True
    assert details["status_stdout_tail"] == "Logged in as user@example.com"

    details = {"logged_in": True}
    parse_provider_auth_status_output(details, "Not logged in")
    assert details["logged_in"] is False


def test_provider_auth_status_helpers_preserve_status_detail_shapes():
    assert provider_auth_status_command("claude") == ["claude", "auth", "status"]
    assert provider_auth_status_command("gemini") is None
    assert unsupported_provider_auth_status("gemini") == {
        "provider": "gemini",
        "supported": False,
        "logged_in": False,
    }
    assert provider_auth_status_error("claude", RuntimeError("boom")) == {
        "provider": "claude",
        "supported": True,
        "logged_in": False,
        "status_error": "boom",
    }
    assert provider_auth_status_base("claude", 7) == {
        "provider": "claude",
        "supported": True,
        "status_returncode": 7,
        "logged_in": False,
    }


def test_append_status_stderr_tail_uses_last_nonempty_stderr_line():
    details = {}

    assert append_status_stderr_tail(details, "first\nsecond") is details
    assert details == {"status_stderr_tail": "second"}
    assert append_status_stderr_tail(details, "   ") == {"status_stderr_tail": "second"}


def test_extract_oauth_state_reads_state_param():
    assert extract_oauth_state("https://example.com/callback?code=abc&state=xyz") == "xyz"
    assert extract_oauth_state("https://example.com/callback?code=abc") is None
    assert extract_oauth_state("") is None


def test_cli_output_cleanup_and_line_normalization():
    raw = b"\x1b[31mRed\x1b[0m\n\n second \n\x1b]title\x07Done"

    text = clean_cli_output(raw)

    assert "Red" in text
    assert "\x1b" not in text
    assert cli_output_lines(text) == ["Red", "second", "Done"]


def test_extract_claude_auth_url_accepts_only_claude_or_anthropic_urls():
    assert extract_claude_auth_url(["Open https://example.com/nope"]) is None
    assert extract_claude_auth_url(["Open https://claude.com/cai/oauth)"]) == "https://claude.com/cai/oauth"
    assert extract_claude_auth_url(["Open https://platform.anthropic.com/oauth\\"]) == "https://platform.anthropic.com/oauth"


def test_extract_first_auth_url_and_device_code():
    assert extract_first_auth_url("Open https://example.com/device)") == "https://example.com/device"
    assert extract_first_auth_url("no url here") is None
    assert extract_device_code("Use code MMVV-CSOZV to continue") == "MMVV-CSOZV"
    assert extract_device_code("Use code abcd-efgh") is None
