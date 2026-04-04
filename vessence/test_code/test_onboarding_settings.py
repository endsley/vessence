from pathlib import Path

from fastapi.testclient import TestClient

from onboarding import main as onboarding_main


def test_first_run_setup_persists_google_oauth_fields(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.post(
        "/api/setup",
        json={
            "google_api_key": "AIzaSy12345678901234567890123456789012345",
            "google_client_id": "client-id.apps.googleusercontent.com",
            "google_client_secret": "secret-value",
            "allowed_google_emails": "chieh@example.com",
            "user_name": "Chieh",
            "jane_brain": "gemini",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "next": "/interview"}

    contents = env_path.read_text()
    assert "GOOGLE_CLIENT_ID=client-id.apps.googleusercontent.com" in contents
    assert "GOOGLE_CLIENT_SECRET=secret-value" in contents
    assert "ALLOWED_GOOGLE_EMAILS=chieh@example.com" in contents


def test_quick_setup_creates_minimal_profile_and_completes_onboarding(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.post(
        "/api/setup",
        json={
            "jane_brain": "claude",
            "auth_method": "account",
            "create_minimal_profile": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "next": "/success"}
    assert "USER_NAME=User" in env_path.read_text()
    assert profile_path.exists()
    assert onboarding_main.onboarding_complete() is True


def test_first_run_setup_rejects_partial_google_oauth_config(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.post(
        "/api/setup",
        json={
            "google_api_key": "AIzaSy12345678901234567890123456789012345",
            "google_client_id": "client-id.apps.googleusercontent.com",
            "user_name": "Chieh",
            "jane_brain": "gemini",
        },
    )

    assert response.status_code == 400
    assert "Google Sign-In setup is incomplete" in response.json()["detail"]


def test_settings_save_persists_google_oauth_fields(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("JANE_BRAIN=gemini\nCLOUDFLARE_DOMAIN=vessences.com\n")

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)

    client = TestClient(onboarding_main.app)
    response = client.post(
        "/api/settings",
        json={
            "google_client_id": "client-id.apps.googleusercontent.com",
            "google_client_secret": "secret-value",
            "allowed_google_emails": "chieh@example.com",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}

    contents = env_path.read_text()
    assert "GOOGLE_CLIENT_ID=client-id.apps.googleusercontent.com" in contents
    assert "GOOGLE_CLIENT_SECRET=secret-value" in contents
    assert "ALLOWED_GOOGLE_EMAILS=chieh@example.com" in contents


def test_settings_page_reports_google_oauth_configured(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"
    env_path.write_text(
        "\n".join(
            [
                "JANE_BRAIN=gemini",
                "USER_NAME=Chieh",
                "CLOUDFLARE_DOMAIN=vessences.com",
                "GOOGLE_CLIENT_ID=client-id.apps.googleusercontent.com",
                "GOOGLE_CLIENT_SECRET=secret-value",
                "ALLOWED_GOOGLE_EMAILS=chieh@example.com",
            ]
        )
        + "\n"
    )
    profile_path.write_text("# User Profile\n")

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Configured" in response.text
    assert "chieh@example.com" in response.text
    assert "vessences.com" in response.text


def test_root_stays_on_setup_until_interview_is_complete(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"
    env_path.write_text("JANE_BRAIN=claude\nUSER_NAME=Chieh\n")

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Vessence \u2014 Setup" in response.text
    assert "Open Vault" not in response.text
    assert 'href="http://localhost:8081"' not in response.text


def test_success_redirects_back_to_setup_until_onboarding_complete(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    profile_path = tmp_path / "user_profile.md"
    env_path.write_text("JANE_BRAIN=claude\nUSER_NAME=Chieh\n")

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "PROFILE", profile_path)

    client = TestClient(onboarding_main.app)
    response = client.get("/success", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
