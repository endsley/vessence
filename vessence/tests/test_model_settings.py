from jane_web.model_settings import (
    AVAILABLE_MODELS,
    build_model_settings_payload,
    current_provider_payload,
    current_model_for_provider,
    default_models,
    legacy_model_env_var,
    model_env_var,
    model_save_target,
    model_tiers,
    provider_availability,
)


PROVIDER_MODELS = {
    "claude": {"smart": "claude-default"},
    "gemini": {"smart": "gemini-default"},
    "openai": {"smart": "openai-default"},
}


def test_default_models_and_env_var_mapping():
    assert default_models(PROVIDER_MODELS) == {
        "claude": "claude-default",
        "gemini": "gemini-default",
        "openai": "openai-default",
    }
    assert model_env_var("gemini") == "JANE_MODEL_GEMINI"
    assert model_env_var("unknown") == "JANE_MODEL_CLAUDE"
    assert legacy_model_env_var("gemini") == "BRAIN_HEAVY_GEMINI"


def test_current_model_prefers_provider_env_then_legacy_then_default():
    assert current_model_for_provider(
        "gemini",
        {"JANE_MODEL_GEMINI": "gemini-current", "BRAIN_HEAVY_GEMINI": "legacy"},
        PROVIDER_MODELS,
    ) == ("gemini-current", "gemini-default", "JANE_MODEL_GEMINI")
    assert current_model_for_provider(
        "gemini",
        {"BRAIN_HEAVY_GEMINI": "legacy"},
        PROVIDER_MODELS,
    ) == ("legacy", "gemini-default", "JANE_MODEL_GEMINI")
    assert current_model_for_provider("gemini", {}, PROVIDER_MODELS) == (
        "gemini-default",
        "gemini-default",
        "JANE_MODEL_GEMINI",
    )


def test_model_tiers_preserve_display_order_roles_and_models():
    assert model_tiers(
        orchestrator_model="orchestrator",
        smart_model="smart",
        cheap_model="cheap",
        local_llm_model="local",
    ) == [
        {"tier": "Orchestrator", "role": "The Primary Brain (Reasoning, Code)", "model": "orchestrator"},
        {"tier": "Agent", "role": "The Specialist (Research, Memory)", "model": "smart"},
        {"tier": "Utility", "role": "The Worker (Archival, Triage)", "model": "cheap"},
        {"tier": "Local", "role": "Privacy & Speed (Local Processing)", "model": "local"},
    ]


def test_build_model_settings_payload_uses_current_provider_and_tiers():
    payload = build_model_settings_payload(
        {"JANE_BRAIN": "openai", "JANE_MODEL_OPENAI": "gpt-current"},
        provider_models=PROVIDER_MODELS,
        smart_model="smart",
        cheap_model="cheap",
        local_llm_model="local",
    )

    assert payload["provider"] == "openai"
    assert payload["model"] == {
        "current": "gpt-current",
        "default": "openai-default",
        "env_var": "JANE_MODEL_OPENAI",
    }
    assert payload["available_models"] is AVAILABLE_MODELS
    assert payload["tiers"] == [
        {"tier": "Orchestrator", "role": "The Primary Brain (Reasoning, Code)", "model": "gpt-current"},
        {"tier": "Agent", "role": "The Specialist (Research, Memory)", "model": "smart"},
        {"tier": "Utility", "role": "The Worker (Archival, Triage)", "model": "cheap"},
        {"tier": "Local", "role": "Privacy & Speed (Local Processing)", "model": "local"},
    ]


def test_model_save_target_selects_current_provider_env_var():
    assert model_save_target({"model": "gemini-new"}, {"JANE_BRAIN": "gemini"}) == (
        "JANE_MODEL_GEMINI",
        "gemini-new",
        None,
    )
    assert model_save_target({"model": "unknown-provider-model"}, {"JANE_BRAIN": "unknown"}) == (
        "JANE_MODEL_CLAUDE",
        "unknown-provider-model",
        None,
    )


def test_model_save_target_preserves_missing_model_error_for_falsey_values():
    assert model_save_target({}, {"JANE_BRAIN": "openai"}) == (
        None,
        None,
        {"ok": False, "error": "No model specified"},
    )
    assert model_save_target({"model": ""}, {"JANE_BRAIN": "openai"}) == (
        None,
        "",
        {"ok": False, "error": "No model specified"},
    )


def test_provider_availability_marks_installation_and_active_provider():
    installed = {"claude": "/bin/claude", "codex": "/bin/codex"}

    assert provider_availability("openai", cli_resolver=installed.get) == [
        {"provider": "claude", "installed": True, "active": False},
        {"provider": "gemini", "installed": False, "active": False},
        {"provider": "openai", "installed": True, "active": True},
    ]


def test_current_provider_payload_preserves_health_defaults():
    assert current_provider_payload("gemini", {}, cli_resolver=lambda _name: None) == {
        "provider": "gemini",
        "model": "unknown",
        "alive": False,
        "available": [
            {"provider": "claude", "installed": False, "active": False},
            {"provider": "gemini", "installed": False, "active": True},
            {"provider": "openai", "installed": False, "active": False},
        ],
    }
