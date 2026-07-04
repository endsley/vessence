import asyncio
import json
import stat
import urllib.request

from jane_web import main as jane_main


class FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def _raise_urlopen(exc):
    def _urlopen(*args, **kwargs):
        raise exc

    return _urlopen


class FakeTokenResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_claude_cli_login_code_token_exchange_error_returns_json(monkeypatch):
    monkeypatch.setattr(jane_main, "_claude_oauth_verifier", "verifier")
    monkeypatch.setattr(jane_main, "_claude_oauth_state", "state")
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen(RuntimeError("network down")))

    response = asyncio.run(
        jane_main.cli_login_code(
            FakeRequest({"provider": "claude", "code": "AUTH_CODE#state"})
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "ok": False,
        "error": "Token exchange failed: network down",
    }


def test_claude_cli_login_code_writes_credentials_and_invalidates_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(jane_main, "_claude_oauth_verifier", "verifier")
    monkeypatch.setattr(jane_main, "_claude_oauth_state", "state")
    monkeypatch.setattr(jane_main, "_cli_login_authenticated", False)
    monkeypatch.setattr(jane_main.time, "time", lambda: 1.0)
    monkeypatch.setattr("jane_web.cli_login_helpers.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeTokenResponse({
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 60,
            "scope": "one two",
        }),
    )
    monkeypatch.setattr(jane_main, "_provider_auth_status", lambda provider: True)
    jane_main._auth_status_cache["claude"] = (0.0, {"logged_in": False})

    response = asyncio.run(
        jane_main.cli_login_code(
            FakeRequest({"provider": "claude", "code": "AUTH_CODE#state"})
        )
    )

    credentials_path = tmp_path / ".claude" / ".credentials.json"
    assert response.status_code == 200
    assert json.loads(response.body) == {"ok": True, "authenticated": True}
    assert json.loads(credentials_path.read_text(encoding="utf-8")) == {
        "claudeAiOauth": {
            "accessToken": "access",
            "refreshToken": "refresh",
            "expiresAt": 61_000,
            "scopes": ["one", "two"],
        }
    }
    assert stat.S_IMODE(credentials_path.stat().st_mode) == 0o600
    assert "claude" not in jane_main._auth_status_cache


def test_gemini_cli_login_code_token_exchange_error_returns_json(monkeypatch):
    monkeypatch.setattr(jane_main, "_gemini_oauth_verifier", "verifier")
    monkeypatch.setattr(jane_main, "_gemini_oauth_state", "state")
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen(RuntimeError("network down")))

    response = asyncio.run(
        jane_main.cli_login_code(
            FakeRequest({"provider": "gemini", "code": "AUTH_CODE"})
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "ok": False,
        "error": "Token exchange failed: network down",
    }


def test_gemini_cli_login_code_writes_credentials_and_invalidates_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(jane_main, "_gemini_oauth_verifier", "verifier")
    monkeypatch.setattr(jane_main, "_gemini_oauth_state", "state")
    monkeypatch.setattr(jane_main, "_cli_login_authenticated", False)
    monkeypatch.setenv("GEMINI_CLI_OAUTH_SECRET", "client-secret")
    monkeypatch.setattr("jane_web.cli_login_helpers.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeTokenResponse({"refresh_token": "refresh"}),
    )
    jane_main._auth_status_cache["gemini"] = (0.0, {"logged_in": False})

    response = asyncio.run(
        jane_main.cli_login_code(
            FakeRequest({"provider": "gemini", "code": "AUTH_CODE"})
        )
    )

    credentials_path = tmp_path / ".gemini" / "oauth_creds.json"
    assert response.status_code == 200
    assert json.loads(response.body) == {"ok": True, "authenticated": True}
    assert json.loads(credentials_path.read_text(encoding="utf-8")) == {
        "type": "authorized_user",
        "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
        "client_secret": "client-secret",
        "refresh_token": "refresh",
    }
    assert stat.S_IMODE(credentials_path.stat().st_mode) == 0o600
    assert "gemini" not in jane_main._auth_status_cache


def test_non_oauth_cli_login_code_submits_code_to_process_stdin(monkeypatch):
    writes = []

    class DummyStdin:
        def write(self, text):
            writes.append(text)

        def flush(self):
            writes.append("<flush>")

    class DummyProcess:
        stdin = DummyStdin()
        returncode = None

        def poll(self):
            return None

    jane_main._cli_login_process = DummyProcess()
    jane_main._cli_login_provider = "openai"
    jane_main._cli_login_authenticated = False
    monkeypatch.setattr(jane_main, "_provider_auth_status", lambda provider: True)
    monkeypatch.setattr(jane_main, "_cli_login_debug_snapshot", lambda provider: {"provider": provider})

    response = asyncio.run(
        jane_main.cli_login_code(
            FakeRequest({"provider": "openai", "code": "ABC-123"})
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body) == {
        "ok": True,
        "authenticated": True,
        "debug": {"provider": "openai"},
    }
    assert writes == ["ABC-123\n", "<flush>"]
    assert jane_main._cli_login_authenticated is True


def test_non_oauth_cli_login_code_reports_missing_stdin(monkeypatch):
    class DummyProcess:
        stdin = None
        returncode = None

        def poll(self):
            return None

    jane_main._cli_login_process = DummyProcess()
    jane_main._cli_login_provider = "openai"
    jane_main._cli_login_authenticated = False
    monkeypatch.setattr(jane_main, "_provider_auth_status", lambda provider: False)

    response = asyncio.run(
        jane_main.cli_login_code(
            FakeRequest({"provider": "openai", "code": "ABC-123"})
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "ok": False,
        "error": "This login session does not accept code entry.",
    }
