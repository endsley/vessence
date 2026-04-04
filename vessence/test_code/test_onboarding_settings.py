from pathlib import Path

from fastapi.testclient import TestClient

from onboarding import main as onboarding_main


def test_first_run_setup_persists_google_oauth_fields(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "DATA_DIR", tmp_path)

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


def test_first_run_setup_rejects_partial_google_oauth_config(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)
    monkeypatch.setattr(onboarding_main, "DATA_DIR", tmp_path)

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
    env_path.write_text(
        "\n".join(
            [
                "JANE_BRAIN=gemini",
                "CLOUDFLARE_DOMAIN=vessences.com",
                "GOOGLE_CLIENT_ID=client-id.apps.googleusercontent.com",
                "GOOGLE_CLIENT_SECRET=secret-value",
                "ALLOWED_GOOGLE_EMAILS=chieh@example.com",
            ]
        )
        + "\n"
    )

    monkeypatch.setattr(onboarding_main, "ENV_FILE", env_path)

    client = TestClient(onboarding_main.app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Configured" in response.text
    assert "chieh@example.com" in response.text
    assert "vessences.com" in response.text
