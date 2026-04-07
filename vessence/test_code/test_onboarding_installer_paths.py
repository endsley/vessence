from fastapi.testclient import TestClient

from onboarding import main as onboarding_main


def test_settings_page_uses_direct_local_urls_when_no_domain(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"
    env_path.write_text("USER_NAME=TestUser\nJANE_BRAIN=claude\n", encoding="utf-8")
    profile_path.write_text("# User Profile\n", encoding="utf-8")

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Vessence Settings" in response.text
    assert "Open Jane" not in response.text
    assert "Open Vault" not in response.text


def test_preset_claude_brain_defaults_to_account_auth_on_setup(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"
    env_path.write_text("JANE_BRAIN=claude\nUSER_NAME=TestUser\n", encoding="utf-8")

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.get("/")

    assert response.status_code == 200
    assert "authMethod: 'account'" in response.text
    assert "Connect Your Account" in response.text
    assert '@click="continueFromBrainStep()"' in response.text
    assert "window.location.replace(this.janeUrl);" in response.text
    assert "cliAuthCodeAccepted" in response.text
    assert "Code submitted. Waiting for Claude Code CLI to finish sign-in..." in response.text


def test_preset_gemini_brain_defaults_to_api_key_on_setup(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"
    env_path.write_text("JANE_BRAIN=gemini\nUSER_NAME=TestUser\n", encoding="utf-8")

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.get("/")

    assert response.status_code == 200
    assert "authMethod: 'apikey'" in response.text
    assert "Enter Your API Key" in response.text


def test_cli_login_proxies_claude_account_auth_request(monkeypatch):
    class DummyResponse:
        status_code = 200

        def json(self):
            return {"auth_url": "https://claude.com/cai/oauth/authorize?code=true"}

    class DummyAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            assert json == {"provider": "claude"}
            assert url.endswith("/api/cli-login")
            return DummyResponse()

    monkeypatch.setattr(onboarding_main.httpx, "AsyncClient", lambda timeout=60: DummyAsyncClient())

    client = TestClient(onboarding_main.app)
    response = client.post("/api/cli-login", json={"provider": "claude"})

    assert response.status_code == 200
    assert response.json() == {"auth_url": "https://claude.com/cai/oauth/authorize?code=true"}


def test_cli_login_code_proxy_forwards_authentication_code(monkeypatch):
    class DummyResponse:
        status_code = 200

        def json(self):
            return {"ok": True, "authenticated": True}

    class DummyAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            assert url.endswith("/api/cli-login/code")
            assert json == {"provider": "claude", "code": "ABC-123"}
            return DummyResponse()

    monkeypatch.setattr(onboarding_main.httpx, "AsyncClient", lambda timeout=30: DummyAsyncClient())

    client = TestClient(onboarding_main.app)
    response = client.post("/api/cli-login/code", json={"provider": "claude", "code": "ABC-123"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "authenticated": True}
