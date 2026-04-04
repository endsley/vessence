from pathlib import Path

from fastapi.testclient import TestClient

import jane_web.main as jane_main


def test_claude_cli_login_candidates_prefer_modern_auth_command():
    assert jane_main._cli_login_candidates("claude") == [
        ["claude", "auth", "login"],
        ["claude", "login"],
    ]


def test_cli_login_retries_claude_candidates_until_auth_url(monkeypatch):
    attempts = []
    responses = iter(
        [
            (None, ["Not logged in - please run /login"]),
            ("https://claude.com/cai/oauth/authorize?code=true", ["Opening browser to sign in…"]),
        ]
    )

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(jane_main, "_terminate_cli_login_process", lambda: None)
    monkeypatch.setattr(jane_main, "_provider_auth_status", lambda provider: False)

    def fake_attempt(cmd):
        attempts.append(cmd)
        return next(responses)

    monkeypatch.setattr(jane_main, "_attempt_cli_login_command", fake_attempt)

    with TestClient(jane_main.app) as client:
        response = client.post("/api/cli-login", json={"provider": "claude"})

    assert response.status_code == 200
    assert response.json() == {"auth_url": "https://claude.com/cai/oauth/authorize?code=true"}
    assert attempts == [["claude", "auth", "login"], ["claude", "login"]]


def test_claude_transcript_login_extracts_copy_paste_url(tmp_path, monkeypatch):
    transcript = tmp_path / "claude-auth.log"
    transcript.write_text(
        "Opening browser to sign in…\n"
        "If the browser didn't open, visit: https://claude.com/cai/oauth/authorize?code=true&state=abc\n",
        encoding="utf-8",
    )

    class DummyProcess:
        def poll(self):
            return None

        def kill(self):
            return None

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(jane_main.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))
    monkeypatch.setattr(jane_main.subprocess, "Popen", lambda *args, **kwargs: DummyProcess())
    monkeypatch.setattr(jane_main.time, "sleep", lambda seconds: None)

    auth_url, output_lines = jane_main._attempt_claude_login_via_transcript(["claude", "auth", "login"])

    assert auth_url == "https://claude.com/cai/oauth/authorize?code=true&state=abc"
    assert any("visit: https://claude.com/cai/oauth/authorize?code=true&state=abc" in line for line in output_lines)


def test_cli_login_code_submits_authentication_code(monkeypatch):
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
    jane_main._cli_login_provider = "claude"
    jane_main._cli_login_authenticated = False

    attempts = {"count": 0}

    def fake_status(provider):
        attempts["count"] += 1
        return attempts["count"] >= 2

    monkeypatch.setattr(jane_main, "_provider_auth_status", fake_status)

    with TestClient(jane_main.app) as client:
        response = client.post("/api/cli-login/code", json={"provider": "claude", "code": "ABC-123"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["authenticated"] is True
    assert "debug" in response.json()
    assert writes == ["ABC-123\n", "<flush>"]


def test_cli_login_status_detects_auth_while_process_still_running(monkeypatch):
    class DummyProcess:
        returncode = None

        def poll(self):
            return None

    jane_main._cli_login_process = DummyProcess()
    jane_main._cli_login_provider = "claude"
    jane_main._cli_login_authenticated = False

    monkeypatch.setattr(jane_main, "_provider_auth_status", lambda provider: provider == "claude")

    with TestClient(jane_main.app) as client:
        response = client.get("/api/cli-login/status")

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert "debug" in response.json()
    assert jane_main._cli_login_authenticated is True


def test_cli_login_status_includes_debug_snapshot(monkeypatch):
    class DummyProcess:
        returncode = None

        def poll(self):
            return None

    jane_main._cli_login_process = DummyProcess()
    jane_main._cli_login_provider = "claude"
    jane_main._cli_login_authenticated = False
    monkeypatch.setattr(jane_main, "_read_cli_transcript_lines", lambda path: ["line 1", "line 2", "line 3", "line 4"])
    monkeypatch.setattr(
        jane_main,
        "_provider_auth_status_details",
        lambda provider: {"provider": provider, "supported": True, "logged_in": False, "status_returncode": 0},
    )
    monkeypatch.setattr(jane_main, "_provider_auth_status", lambda provider: False)

    with TestClient(jane_main.app) as client:
        response = client.get("/api/cli-login/status")

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert data["debug"]["process_state"] == "running"
    assert data["debug"]["auth_status"]["supported"] is True
    assert data["debug"]["transcript_tail"] == ["line 2", "line 3", "line 4"]


def test_localhost_index_bootstraps_without_google_oauth(monkeypatch):
    monkeypatch.setattr(jane_main, "create_session", lambda fingerprint, trusted, user_id=None: "local-session")
    monkeypatch.setattr(jane_main, "prewarm_session", lambda session_id: None)

    with TestClient(jane_main.app) as client:
        response = client.get("/", headers={"host": "localhost:8081"})

    assert response.status_code == 200
    assert "Jane" in response.text
    assert "Sign in with Google" not in response.text
    assert "jane_session=" in response.headers.get("set-cookie", "")


def test_public_host_index_still_shows_login_without_session():
    with TestClient(jane_main.app) as client:
        response = client.get("/", headers={"host": "jane.vessences.com"})

    assert response.status_code == 200
    assert "Sign in with Google" in response.text
