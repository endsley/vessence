import json
import io
import stat
from urllib.parse import parse_qs

import pytest

from jane_web.cli_login_helpers import (
    append_status_stderr_tail,
    apply_claude_refresh_tokens,
    base64url_no_padding,
    cached_provider_auth_status,
    claude_auth_code_from_callback,
    claude_credentials_payload,
    claude_oauth_authorization_url,
    claude_oauth_refresh_request_spec,
    claude_oauth_token_request_spec,
    claude_refresh_token_from_credentials,
    cli_credentials_path,
    clean_cli_output,
    cli_output_lines,
    cli_binary_for_provider,
    cli_login_debug_payload,
    cli_login_candidates,
    cli_login_output_update,
    cli_login_process_state,
    extract_claude_auth_url,
    extract_device_code,
    extract_first_auth_url,
    extract_oauth_state,
    gemini_credentials_payload,
    gemini_oauth_authorization_url,
    gemini_oauth_token_request_spec,
    mask_email,
    oauth_login_credentials_for_code,
    oauth_token_exchange_error,
    oauth_token_response,
    parse_provider_auth_status_output,
    pkce_code_challenge,
    process_ids_with_children,
    process_tree_socket_port,
    proc_stat_parent_pid,
    proc_net_listen_socket_candidates,
    proc_net_listen_socket_ports,
    provider_auth_status_base,
    provider_auth_status_command,
    provider_auth_status_details,
    provider_auth_status_error,
    refresh_provider_auth_status_details,
    read_cli_transcript_lines,
    ss_login_callback_port,
    submit_cli_login_code_to_stdin,
    should_refresh_provider_auth_status,
    unsupported_provider_auth_status,
    write_cli_credentials,
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


def test_pkce_and_oauth_url_helpers_preserve_provider_params():
    from urllib.parse import parse_qs, urlparse

    verifier = base64url_no_padding(b"abc123")
    challenge = pkce_code_challenge(verifier)

    assert verifier == "YWJjMTIz"
    assert "=" not in challenge

    claude = parse_qs(urlparse(claude_oauth_authorization_url(challenge, "state-1")).query)
    assert claude["client_id"] == ["9d1c250a-e61b-44d9-88ed-5944d1962f5e"]
    assert claude["redirect_uri"] == ["https://platform.claude.com/oauth/code/callback"]
    assert claude["code_challenge"] == [challenge]
    assert claude["code_challenge_method"] == ["S256"]
    assert claude["state"] == ["state-1"]
    assert "user:sessions:claude_code" in claude["scope"][0]

    gemini = parse_qs(urlparse(gemini_oauth_authorization_url(challenge, "state-2")).query)
    assert gemini["client_id"] == [
        "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
    ]
    assert gemini["redirect_uri"] == ["https://codeassist.google.com/authcode"]
    assert gemini["access_type"] == ["offline"]
    assert gemini["code_challenge"] == [challenge]
    assert gemini["code_challenge_method"] == ["S256"]
    assert gemini["state"] == ["state-2"]
    assert "https://www.googleapis.com/auth/cloud-platform" in gemini["scope"][0]


def test_cli_oauth_code_and_credentials_payload_helpers_preserve_shapes():
    assert claude_auth_code_from_callback("AUTH_CODE#STATE") == "AUTH_CODE"
    assert claude_auth_code_from_callback("  AUTH_CODE  ") == "AUTH_CODE"
    assert claude_auth_code_from_callback("") == ""

    assert claude_credentials_payload(
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 60,
            "scope": "one two",
        },
        now_ms=1_000,
    ) == {
        "claudeAiOauth": {
            "accessToken": "access",
            "refreshToken": "refresh",
            "expiresAt": 61_000,
            "scopes": ["one", "two"],
        }
    }
    assert gemini_credentials_payload(
        {"refresh_token": "refresh"},
        client_secret="secret",
    ) == {
        "type": "authorized_user",
        "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
        "client_secret": "secret",
        "refresh_token": "refresh",
    }


def test_oauth_login_credentials_for_code_exchanges_claude_callback_code():
    class FakeResponse:
        def read(self):
            return json.dumps({
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 60,
                "scope": "one two",
            }).encode("utf-8")

    seen = {}

    def request_factory(url, *, data, headers):
        seen["request"] = (url, data, headers)
        return {"url": url}

    credentials, status_code, error = oauth_login_credentials_for_code(
        "claude",
        "AUTH_CODE#STATE",
        "verifier",
        now_ms=1_000,
        request_factory=request_factory,
        urlopen_fn=lambda request, *, timeout: FakeResponse(),
    )

    assert status_code is None
    assert error is None
    assert credentials == {
        "claudeAiOauth": {
            "accessToken": "access",
            "refreshToken": "refresh",
            "expiresAt": 61_000,
            "scopes": ["one", "two"],
        }
    }
    assert parse_qs(seen["request"][1].decode("utf-8"))["code"] == ["AUTH_CODE"]


def test_oauth_login_credentials_for_code_exchanges_gemini_code():
    class FakeResponse:
        def read(self):
            return b'{"refresh_token": "refresh"}'

    seen = {}

    def request_factory(url, *, data, headers):
        seen["request"] = (url, data, headers)
        return {"url": url}

    credentials, status_code, error = oauth_login_credentials_for_code(
        "gemini",
        " AUTH_CODE ",
        "verifier",
        now_ms=1_000,
        request_factory=request_factory,
        urlopen_fn=lambda request, *, timeout: FakeResponse(),
        client_secret="client-secret",
    )

    assert status_code is None
    assert error is None
    assert credentials == {
        "type": "authorized_user",
        "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
        "client_secret": "client-secret",
        "refresh_token": "refresh",
    }
    body = parse_qs(seen["request"][1].decode("utf-8"))
    assert body["code"] == ["AUTH_CODE"]
    assert body["client_secret"] == ["client-secret"]


def test_oauth_login_credentials_for_code_returns_route_error_details():
    credentials, status_code, error = oauth_login_credentials_for_code(
        "claude",
        "#STATE",
        "verifier",
        now_ms=1_000,
        request_factory=lambda *args, **kwargs: object(),
        urlopen_fn=lambda *args, **kwargs: object(),
    )

    assert credentials is None
    assert status_code == 400
    assert error == "Invalid code format."

    credentials, status_code, error = oauth_login_credentials_for_code(
        "gemini",
        "AUTH_CODE",
        "verifier",
        now_ms=1_000,
        request_factory=lambda *args, **kwargs: object(),
        urlopen_fn=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    assert credentials is None
    assert status_code == 400
    assert error == "Token exchange failed: network down"


def test_oauth_token_request_specs_preserve_provider_fields_and_headers():
    claude_url, claude_body, claude_headers = claude_oauth_token_request_spec(
        "AUTH_CODE",
        "verifier",
    )
    claude_form = parse_qs(claude_body.decode("utf-8"))
    assert claude_url == "https://platform.claude.com/v1/oauth/token"
    assert claude_form == {
        "grant_type": ["authorization_code"],
        "client_id": ["9d1c250a-e61b-44d9-88ed-5944d1962f5e"],
        "code": ["AUTH_CODE"],
        "code_verifier": ["verifier"],
        "redirect_uri": ["https://platform.claude.com/oauth/code/callback"],
    }
    assert claude_headers == {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "claude-code/2.1.86",
        "Accept": "application/json",
    }

    gemini_url, gemini_body, gemini_headers = gemini_oauth_token_request_spec(
        "AUTH_CODE",
        "verifier",
        client_secret="client-secret",
    )
    gemini_form = parse_qs(gemini_body.decode("utf-8"))
    assert gemini_url == "https://oauth2.googleapis.com/token"
    assert gemini_form == {
        "grant_type": ["authorization_code"],
        "client_id": [
            "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
        ],
        "client_secret": ["client-secret"],
        "code": ["AUTH_CODE"],
        "code_verifier": ["verifier"],
        "redirect_uri": ["https://codeassist.google.com/authcode"],
    }
    assert gemini_headers == {"Content-Type": "application/x-www-form-urlencoded"}


def test_claude_refresh_request_spec_preserves_fields_and_headers():
    url, body, headers = claude_oauth_refresh_request_spec("refresh-token")

    assert url == "https://platform.claude.com/v1/oauth/token"
    assert parse_qs(body.decode("utf-8")) == {
        "grant_type": ["refresh_token"],
        "client_id": ["9d1c250a-e61b-44d9-88ed-5944d1962f5e"],
        "refresh_token": ["refresh-token"],
    }
    assert headers == {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "claude-code/2.1.86",
        "Accept": "application/json",
    }


def test_claude_refresh_helpers_read_and_update_credentials():
    credentials = {
        "claudeAiOauth": {
            "accessToken": "old-access",
            "refreshToken": "old-refresh",
            "expiresAt": 100,
            "scopes": ["existing"],
        }
    }

    assert claude_refresh_token_from_credentials(credentials) == "old-refresh"
    assert claude_refresh_token_from_credentials({}) is None

    assert apply_claude_refresh_tokens(
        credentials,
        {"access_token": "new-access", "expires_in": 60},
        previous_refresh_token="old-refresh",
        now_ms=1_000,
    ) == {
        "claudeAiOauth": {
            "accessToken": "new-access",
            "refreshToken": "old-refresh",
            "expiresAt": 61_000,
            "scopes": ["existing"],
        }
    }
    assert apply_claude_refresh_tokens(
        credentials,
        {
            "access_token": "scoped-access",
            "refresh_token": "new-refresh",
            "expires_in": 30,
            "scope": "one two",
        },
        previous_refresh_token="old-refresh",
        now_ms=2_000,
    ) == {
        "claudeAiOauth": {
            "accessToken": "scoped-access",
            "refreshToken": "new-refresh",
            "expiresAt": 32_000,
            "scopes": ["one", "two"],
        }
    }


def test_cli_credentials_path_uses_provider_specific_files(tmp_path):
    assert cli_credentials_path("claude", home_path=tmp_path) == (
        tmp_path / ".claude" / ".credentials.json"
    )
    assert cli_credentials_path("gemini", home_path=tmp_path) == (
        tmp_path / ".gemini" / "oauth_creds.json"
    )
    with pytest.raises(ValueError):
        cli_credentials_path("openai", home_path=tmp_path)


def test_write_cli_credentials_creates_parent_and_private_file(tmp_path, monkeypatch):
    monkeypatch.setattr("jane_web.cli_login_helpers.Path.home", lambda: tmp_path)

    credentials_path = write_cli_credentials("claude", {"token": "secret"})

    assert credentials_path == tmp_path / ".claude" / ".credentials.json"
    assert json.loads(credentials_path.read_text(encoding="utf-8")) == {"token": "secret"}
    assert stat.S_IMODE(credentials_path.stat().st_mode) == 0o600


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


def test_submit_cli_login_code_to_stdin_writes_code_and_flushes():
    writes = []

    class FakeStdin:
        def write(self, text):
            writes.append(text)

        def flush(self):
            writes.append("<flush>")

    class FakeProcessWithStdin:
        stdin = FakeStdin()

    assert submit_cli_login_code_to_stdin(FakeProcessWithStdin(), "ABC-123") == (
        True,
        None,
        None,
    )
    assert writes == ["ABC-123\n", "<flush>"]


def test_submit_cli_login_code_to_stdin_reports_missing_stdin_or_write_error():
    class NoStdinProcess:
        stdin = None

    assert submit_cli_login_code_to_stdin(NoStdinProcess(), "ABC-123") == (
        False,
        "This login session does not accept code entry.",
        400,
    )

    class BrokenStdin:
        def write(self, text):
            raise RuntimeError("closed")

        def flush(self):
            raise AssertionError("flush should not run")

    class BrokenProcess:
        stdin = BrokenStdin()

    assert submit_cli_login_code_to_stdin(BrokenProcess(), "ABC-123") == (
        False,
        "Could not submit authentication code: closed",
        500,
    )


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


def test_provider_auth_status_cache_and_refresh_helpers_preserve_policy():
    class Result:
        returncode = 0
        stdout = "Logged in as user@example.com"

    cached_details = {"provider": "claude", "logged_in": True}
    cache = {"claude": (10.0, cached_details)}
    details = {"provider": "claude", "logged_in": False}
    calls = []

    assert cached_provider_auth_status("claude", cache, 14.9) is cached_details
    assert cached_provider_auth_status("claude", cache, 15.0) is None
    assert cached_provider_auth_status("gemini", cache, 14.0) is None
    assert should_refresh_provider_auth_status("claude", details)
    assert not should_refresh_provider_auth_status("gemini", details)
    assert not should_refresh_provider_auth_status("claude", {"logged_in": True})
    assert refresh_provider_auth_status_details(
        details,
        ["claude", "auth", "status"],
        run_command_fn=lambda cmd: calls.append(cmd) or Result(),
    ) is details
    assert details["logged_in"] is True
    assert calls == [["claude", "auth", "status"]]


def test_provider_auth_status_details_uses_fresh_cache_without_running_command():
    cached = {"claude": (10.0, {"provider": "claude", "logged_in": True})}
    calls = []

    details = provider_auth_status_details(
        "claude",
        cache=cached,
        now_fn=lambda: 12.0,
        run_command_fn=lambda cmd: calls.append(cmd),
        attempt_refresh_fn=lambda: False,
    )

    assert details == {"provider": "claude", "logged_in": True}
    assert calls == []


def test_provider_auth_status_details_runs_status_and_caches_success():
    class Result:
        returncode = 0
        stdout = '{"loggedIn": true, "email": "user@example.com"}'
        stderr = ""

    cache = {}
    details = provider_auth_status_details(
        "claude",
        cache=cache,
        now_fn=lambda: 20.0,
        run_command_fn=lambda cmd: Result(),
        attempt_refresh_fn=lambda: False,
    )

    assert details["logged_in"] is True
    assert details["email_hint"] == "us***@example.com"
    assert cache == {"claude": (20.0, details)}


def test_provider_auth_status_details_preserves_failure_without_caching():
    class Result:
        returncode = 2
        stdout = ""
        stderr = "first\nlast failure"

    cache = {}
    details = provider_auth_status_details(
        "claude",
        cache=cache,
        now_fn=lambda: 20.0,
        run_command_fn=lambda cmd: Result(),
        attempt_refresh_fn=lambda: False,
    )

    assert details == {
        "provider": "claude",
        "supported": True,
        "status_returncode": 2,
        "logged_in": False,
        "status_stderr_tail": "last failure",
    }
    assert cache == {}


def test_provider_auth_status_details_refreshes_claude_and_rechecks_once():
    class LoggedOut:
        returncode = 0
        stdout = "Not logged in"
        stderr = ""

    class LoggedIn:
        returncode = 0
        stdout = "Logged in"
        stderr = ""

    results = [LoggedOut(), LoggedIn()]
    details = provider_auth_status_details(
        "claude",
        cache={},
        now_fn=lambda: 20.0,
        run_command_fn=lambda cmd: results.pop(0),
        attempt_refresh_fn=lambda: True,
    )

    assert details["logged_in"] is True
    assert results == []


def test_extract_oauth_state_reads_state_param():
    assert extract_oauth_state("https://example.com/callback?code=abc&state=xyz") == "xyz"
    assert extract_oauth_state("https://example.com/callback?code=abc") is None
    assert extract_oauth_state("") is None


def test_proc_net_listen_socket_ports_filters_local_listeners_and_known_ports():
    lines = [
        "sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode",
        "0: 0100007F:1F91 00000000:0000 0A 0 0 0 0 0 1001",  # 8081 known
        "1: 0100007F:A1B2 00000000:0000 0A 0 0 0 0 0 1002",
        "2: 00000000:A1B3 00000000:0000 0A 0 0 0 0 0 1003",
        "3: 0200007F:A1B4 00000000:0000 0A 0 0 0 0 0 1004",
        "4: 0100007F:A1B5 00000000:0000 01 0 0 0 0 0 1005",
        "5: 00000000000000000000000001000000:A1B6 00000000:0000 0A 0 0 0 0 0 1006",
        "bad line",
    ]

    assert proc_net_listen_socket_ports(lines) == [
        (0xA1B2, 1002),
        (0xA1B3, 1003),
        (0xA1B6, 1006),
    ]


def test_proc_net_listen_socket_candidates_reads_paths_once_and_preserves_order():
    files = {
        "/proc/net/tcp": "\n".join([
            "sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode",
            "0: 0100007F:A1B2 00000000:0000 0A 0 0 0 0 0 1002",
            "1: 0100007F:A1B3 00000000:0000 0A 0 0 0 0 0 1003",
        ]),
        "/proc/net/tcp6": "\n".join([
            "sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode",
            "0: 00000000000000000000000001000000:A1B3 00000000:0000 0A 0 0 0 0 0 2003",
            "1: 00000000000000000000000001000000:A1B4 00000000:0000 0A 0 0 0 0 0 2004",
        ]),
    }
    opened = []

    def fake_open(path):
        opened.append(path)
        if path not in files:
            raise FileNotFoundError(path)
        return io.StringIO(files[path])

    ports, inode_to_port = proc_net_listen_socket_candidates(
        ["/proc/net/tcp", "/proc/net/missing", "/proc/net/tcp6"],
        open_fn=fake_open,
    )

    assert opened == ["/proc/net/tcp", "/proc/net/missing", "/proc/net/tcp6"]
    assert ports == [0xA1B2, 0xA1B3, 0xA1B4]
    assert inode_to_port == {1002: 0xA1B2, 1003: 0xA1B3, 2003: 0xA1B3, 2004: 0xA1B4}


def test_ss_login_callback_port_matches_claude_or_node_unknown_localhost_port():
    lines = [
        "LISTEN 0 128 127.0.0.1:8081 0.0.0.0:* users:((\"node\",pid=1,fd=1))",
        "LISTEN 0 128 127.0.0.1:41474 0.0.0.0:* users:((\"node\",pid=2,fd=3))",
        "LISTEN 0 128 127.0.0.1:41475 0.0.0.0:* users:((\"other\",pid=3,fd=3))",
    ]

    assert ss_login_callback_port(lines) == 41474
    assert ss_login_callback_port(["LISTEN 127.0.0.1:41475 users:((\"other\"))"]) is None


def test_proc_stat_parent_pid_reads_parent_from_proc_stat_text():
    assert proc_stat_parent_pid("123 (node) S 45 0 0") == 45
    assert proc_stat_parent_pid("123 (node worker) S 45 0 0") == 45
    assert proc_stat_parent_pid("malformed") is None


def test_process_ids_with_children_preserves_one_proc_scan_behavior(tmp_path):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "10").mkdir()
    (proc_root / "10" / "stat").write_text("10 (claude) S 1 0 0", encoding="utf-8")
    (proc_root / "20").mkdir()
    (proc_root / "20" / "stat").write_text("20 (node) S 10 0 0", encoding="utf-8")
    (proc_root / "30").mkdir()
    (proc_root / "30" / "stat").write_text("30 (other) S 999 0 0", encoding="utf-8")
    (proc_root / "not-a-pid").mkdir()

    assert process_ids_with_children(proc_root, 10) == [10, 20]


def test_process_tree_socket_port_matches_first_process_fd_socket(tmp_path):
    proc_root = tmp_path / "proc"
    root = proc_root / "10"
    child = proc_root / "20"
    root_fd = root / "fd"
    child_fd = child / "fd"
    root_fd.mkdir(parents=True)
    child_fd.mkdir(parents=True)
    (root / "stat").write_text("10 (claude) S 1 0 0", encoding="utf-8")
    (child / "stat").write_text("20 (node) S 10 0 0", encoding="utf-8")
    (root_fd / "3").symlink_to("pipe:[999]")
    (child_fd / "4").symlink_to("socket:[1002]")

    assert process_tree_socket_port(10, {1002: 41474}, proc_root=proc_root) == 41474


def test_process_tree_socket_port_returns_none_without_matching_inode(tmp_path):
    proc_root = tmp_path / "proc"
    root = proc_root / "10"
    fd_dir = root / "fd"
    fd_dir.mkdir(parents=True)
    (root / "stat").write_text("10 (claude) S 1 0 0", encoding="utf-8")
    (fd_dir / "3").symlink_to("socket:[9999]")

    assert process_tree_socket_port(10, {1002: 41474}, proc_root=proc_root) is None


def test_oauth_token_exchange_error_preserves_provider_rate_limit_messages():
    class ErrorWithBody(Exception):
        def __init__(self, body):
            super().__init__("http error")
            self._body = body

        def read(self):
            return self._body

    assert oauth_token_exchange_error(
        "claude",
        ErrorWithBody(b'{"error":{"type":"rate_limit_error"}}'),
    ) == (
        429,
        "Token exchange failed: Anthropic's servers are rate-limiting requests for this application. "
        "This is a known issue. Please try again in a few minutes.",
    )
    assert oauth_token_exchange_error(
        "gemini",
        ErrorWithBody(b'{"error":"rateLimitExceeded"}'),
    ) == (
        429,
        "Token exchange failed: Google's servers are rate-limiting requests for this application. "
        "Please try again in a few minutes.",
    )


def test_oauth_token_exchange_error_uses_body_or_exception_detail():
    class ErrorWithBody(Exception):
        def __init__(self, body):
            super().__init__("http error")
            self._body = body

        def read(self):
            return self._body

    assert oauth_token_exchange_error("claude", RuntimeError("network down")) == (
        400,
        "Token exchange failed: network down",
    )
    assert oauth_token_exchange_error("claude", ErrorWithBody(b"bad request")) == (
        400,
        "Token exchange failed: bad request",
    )
    assert oauth_token_exchange_error("claude", None) == (
        400,
        "Token exchange failed: No token response",
    )


def test_oauth_token_response_decodes_json_and_preserves_request_shape():
    class FakeResponse:
        def read(self):
            return b'{"access_token": "access"}'

    seen = {}

    def request_factory(url, *, data, headers):
        seen["request"] = (url, data, headers)
        return {"url": url}

    tokens, error = oauth_token_response(
        "https://token.example",
        b"body",
        {"Content-Type": "application/x-www-form-urlencoded"},
        request_factory=request_factory,
        urlopen_fn=lambda request, *, timeout: FakeResponse(),
    )

    assert tokens == {"access_token": "access"}
    assert error is None
    assert seen["request"] == (
        "https://token.example",
        b"body",
        {"Content-Type": "application/x-www-form-urlencoded"},
    )


def test_oauth_token_response_preserves_fetch_or_parse_errors():
    exc = RuntimeError("network down")
    tokens, error = oauth_token_response(
        "https://token.example",
        b"body",
        {},
        request_factory=lambda *args, **kwargs: object(),
        urlopen_fn=lambda *args, **kwargs: (_ for _ in ()).throw(exc),
    )

    assert tokens is None
    assert error is exc


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


def test_cli_login_output_update_preserves_auth_url_device_code_ordering():
    assert cli_login_output_update(
        "Use code MMVV-CSOZV",
        auth_url=None,
        device_code=None,
    ) == (None, None, "Use code MMVV-CSOZV")

    assert cli_login_output_update(
        "Open https://example.com/device)",
        auth_url=None,
        device_code=None,
    ) == ("https://example.com/device", None, "Open https://example.com/device)")

    assert cli_login_output_update(
        "Use code MMVV-CSOZV",
        auth_url="https://example.com/device",
        device_code=None,
    ) == ("https://example.com/device", "MMVV-CSOZV", "Use code MMVV-CSOZV")

    assert cli_login_output_update(
        "Use code ZZZZ-9999",
        auth_url="https://example.com/device",
        device_code="MMVV-CSOZV",
    ) == ("https://example.com/device", "MMVV-CSOZV", "Use code ZZZZ-9999")
