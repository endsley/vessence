"""Model settings payload helpers for Jane web."""

from __future__ import annotations

import os
import shutil
from typing import Any, Callable, Mapping

from jane.config import (
    CHEAP_MODEL,
    LOCAL_LLM_MODEL,
    PROVIDER_MODELS,
    SMART_MODEL,
    normalize_frontier_provider,
)

AVAILABLE_MODELS = {
    "claude": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-6"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "openai": ["gpt-5.4-mini", "gpt-5.4", "gpt-4.1-mini", "gpt-4.1", "o3"],
}

ENV_VAR_FOR_MODEL = {
    "claude": "JANE_MODEL_CLAUDE",
    "gemini": "JANE_MODEL_GEMINI",
    "openai": "JANE_MODEL_OPENAI",
}

PROVIDER_CLI_BINARIES = (
    ("claude", "claude"),
    ("gemini", "gemini"),
    ("openai", "codex"),
)


def default_models(provider_models: Mapping[str, Mapping[str, str]] = PROVIDER_MODELS) -> dict[str, str]:
    return {provider: config["smart"] for provider, config in provider_models.items()}


def model_env_var(provider: str) -> str:
    return ENV_VAR_FOR_MODEL.get(provider, ENV_VAR_FOR_MODEL["claude"])


def current_model_for_provider(
    provider: str,
    environ: Mapping[str, str] = os.environ,
    provider_models: Mapping[str, Mapping[str, str]] = PROVIDER_MODELS,
) -> tuple[str, str, str]:
    defaults = default_models(provider_models)
    default = defaults.get(provider, defaults["claude"])
    env_var = model_env_var(provider)
    legacy_var = f"BRAIN_HEAVY_{provider.upper()}"
    current = environ.get(env_var) or environ.get(legacy_var) or default
    return current, default, env_var


def model_tiers(
    *,
    orchestrator_model: str,
    smart_model: str,
    cheap_model: str,
    local_llm_model: str,
) -> list[dict[str, str]]:
    return [
        {"tier": "Orchestrator", "role": "The Primary Brain (Reasoning, Code)", "model": orchestrator_model},
        {"tier": "Agent", "role": "The Specialist (Research, Memory)", "model": smart_model},
        {"tier": "Utility", "role": "The Worker (Archival, Triage)", "model": cheap_model},
        {"tier": "Local", "role": "Privacy & Speed (Local Processing)", "model": local_llm_model},
    ]


def build_model_settings_payload(
    environ: Mapping[str, str] = os.environ,
    *,
    provider_models: Mapping[str, Mapping[str, str]] = PROVIDER_MODELS,
    smart_model: str = SMART_MODEL,
    cheap_model: str = CHEAP_MODEL,
    local_llm_model: str = LOCAL_LLM_MODEL,
) -> dict:
    provider = normalize_frontier_provider(environ.get("JANE_BRAIN", "claude"))
    current, default, env_var = current_model_for_provider(provider, environ, provider_models)

    return {
        "provider": provider,
        "model": {"current": current, "default": default, "env_var": env_var},
        "available_models": AVAILABLE_MODELS,
        "tiers": model_tiers(
            orchestrator_model=current,
            smart_model=smart_model,
            cheap_model=cheap_model,
            local_llm_model=local_llm_model,
        ),
    }


def model_save_target(
    body: Mapping[str, Any],
    environ: Mapping[str, str] = os.environ,
) -> tuple[str | None, Any, dict[str, str] | None]:
    provider = normalize_frontier_provider(environ.get("JANE_BRAIN", "claude"))
    env_var = model_env_var(provider)
    model = body.get("model")
    if not model:
        return None, model, {"ok": False, "error": "No model specified"}
    return env_var, model, None


def provider_availability(
    active_provider: str,
    *,
    cli_resolver: Callable[[str], str | None] = shutil.which,
    provider_binaries: tuple[tuple[str, str], ...] = PROVIDER_CLI_BINARIES,
) -> list[dict[str, Any]]:
    return [
        {
            "provider": provider,
            "installed": cli_resolver(cli_name) is not None,
            "active": provider == active_provider,
        }
        for provider, cli_name in provider_binaries
    ]


def current_provider_payload(
    active_provider: str,
    health: Mapping[str, Any],
    *,
    cli_resolver: Callable[[str], str | None] = shutil.which,
) -> dict[str, Any]:
    return {
        "provider": active_provider,
        "model": health.get("model", "unknown"),
        "alive": health.get("alive", False),
        "available": provider_availability(active_provider, cli_resolver=cli_resolver),
    }
