from jane_web.proxy_brain import (
    brain_name,
    session_log_id,
    use_gemini_api,
    use_persistent_claude,
    use_persistent_codex,
    use_persistent_gemini,
    use_standing_codex,
    web_chat_model,
)


PROVIDER_MODELS = {
    "claude": {"smart": "claude-default"},
    "gemini": {"smart": "gemini-default"},
    "openai": {"smart": "openai-default"},
}


def _normalize(value: str) -> str:
    return {"gpt": "openai"}.get(value.strip().lower(), value.strip().lower())


def test_brain_name_prefers_valid_env_file_value_and_updates_environ(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# JANE_BRAIN=claude\nOTHER=value\nJANE_BRAIN=gpt\n", encoding="utf-8")
    environ = {"JANE_BRAIN": "claude"}

    assert brain_name(env_file_path=env_file, environ=environ, normalize_provider=_normalize) == "openai"
    assert environ["JANE_BRAIN"] == "openai"


def test_brain_name_ignores_invalid_env_file_value_and_falls_back_to_environ(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("JANE_BRAIN=unknown\n", encoding="utf-8")
    environ = {"JANE_BRAIN": "gemini"}

    assert brain_name(env_file_path=env_file, environ=environ, normalize_provider=_normalize) == "gemini"
    assert environ["JANE_BRAIN"] == "gemini"
    assert brain_name(env_file_path=None, environ={}, normalize_provider=_normalize) == "gemini"


def test_session_log_id_truncates_or_uses_none_label():
    assert session_log_id("abcdefghijklmnop") == "abcdefghijkl"
    assert session_log_id("") == "none"
    assert session_log_id(None) == "none"


def test_provider_mode_flags_preserve_defaults_and_env_overrides():
    assert use_gemini_api("gemini", {})
    assert not use_gemini_api("gemini", {"JANE_WEB_GEMINI_API": "0"})
    assert not use_gemini_api("claude", {})

    assert not use_persistent_gemini("gemini", {})
    assert use_persistent_gemini("gemini", {"JANE_WEB_PERSISTENT_GEMINI": "1"})

    assert use_persistent_claude("claude", {})
    assert not use_persistent_claude("claude", {"JANE_WEB_PERSISTENT_CLAUDE": "0"})

    assert use_standing_codex("openai", {})
    assert not use_standing_codex("openai", {"JANE_WEB_STANDING_CODEX": "0"})
    assert not use_standing_codex("claude", {})

    assert not use_persistent_codex("openai", {})
    assert use_persistent_codex("openai", {"JANE_WEB_STANDING_CODEX": "0"})
    assert not use_persistent_codex(
        "openai",
        {"JANE_WEB_STANDING_CODEX": "0", "JANE_WEB_PERSISTENT_CODEX": "0"},
    )


def test_web_chat_model_prefers_provider_env_var_then_provider_default():
    assert (
        web_chat_model(
            "gemini",
            environ={"JANE_MODEL_GEMINI": "gemini-current"},
            provider_models=PROVIDER_MODELS,
            normalize_provider=_normalize,
        )
        == "gemini-current"
    )
    assert (
        web_chat_model(
            "codex",
            environ={"JANE_MODEL_OPENAI": "codex-current"},
            provider_models=PROVIDER_MODELS,
            normalize_provider=lambda value: value,
        )
        == "codex-current"
    )
    assert (
        web_chat_model(
            "openai",
            environ={},
            provider_models=PROVIDER_MODELS,
            normalize_provider=_normalize,
        )
        == "openai-default"
    )
    assert (
        web_chat_model(
            "unknown",
            environ={},
            provider_models=PROVIDER_MODELS,
            normalize_provider=_normalize,
        )
        == "claude-default"
    )
