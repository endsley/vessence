from pathlib import Path

from jane import standing_brain
from jane_web import jane_proxy


def test_configured_provider_prefers_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("JANE_BRAIN=claude\n", encoding="utf-8")

    monkeypatch.setenv("JANE_BRAIN", "gemini")
    monkeypatch.setattr("jane.config.ENV_FILE_PATH", str(env_path))

    assert standing_brain._configured_provider() == "claude"


def test_configured_provider_falls_back_to_process_env(monkeypatch):
    monkeypatch.setattr("jane.config.ENV_FILE_PATH", str(Path("/nonexistent/.env")))
    monkeypatch.setenv("JANE_BRAIN", "openai")

    assert standing_brain._configured_provider() == "openai"


def test_jane_proxy_brain_name_prefers_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("JANE_BRAIN=claude\n", encoding="utf-8")

    monkeypatch.setattr("jane.config.ENV_FILE_PATH", str(env_path))
    monkeypatch.setattr(jane_proxy, "ENV_FILE_PATH", str(env_path))
    monkeypatch.setenv("JANE_BRAIN", "gemini")

    assert jane_proxy._get_brain_name() == "claude"


def test_jane_proxy_brain_name_falls_back_to_process_env(monkeypatch):
    missing = str(Path("/nonexistent/.env"))
    monkeypatch.setattr("jane.config.ENV_FILE_PATH", missing)
    monkeypatch.setattr(jane_proxy, "ENV_FILE_PATH", missing)
    monkeypatch.setenv("JANE_BRAIN", "openai")

    assert jane_proxy._get_brain_name() == "openai"
