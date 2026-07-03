"""Brain/provider selection helpers for Jane proxy."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, MutableMapping
from pathlib import Path
from typing import Any

from jane.config import PROVIDER_MODELS, normalize_frontier_provider


def brain_name(
    *,
    env_file_path: str | Path | None,
    environ: MutableMapping[str, str] | None = None,
    normalize_provider: Callable[[str], str] = normalize_frontier_provider,
) -> str:
    environ = environ if environ is not None else os.environ
    env_path = Path(env_file_path) if env_file_path else None
    if env_path and env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "JANE_BRAIN":
                provider = normalize_provider(value.strip())
                if provider in {"claude", "gemini", "openai"}:
                    environ["JANE_BRAIN"] = provider
                    return provider
    return normalize_provider(environ.get("JANE_BRAIN", "gemini"))


def session_log_id(session_id: str | None) -> str:
    return session_id[:12] if session_id else "none"


def use_gemini_api(brain_name: str, environ: Mapping[str, str] = os.environ) -> bool:
    """Use Gemini API brain instead of CLI-based persistent Gemini."""

    return brain_name == "gemini" and environ.get("JANE_WEB_GEMINI_API", "1") != "0"


def use_persistent_gemini(brain_name: str, environ: Mapping[str, str] = os.environ) -> bool:
    return brain_name == "gemini" and environ.get("JANE_WEB_PERSISTENT_GEMINI", "0") == "1"


def use_persistent_claude(brain_name: str, environ: Mapping[str, str] = os.environ) -> bool:
    return brain_name == "claude" and environ.get("JANE_WEB_PERSISTENT_CLAUDE", "1") != "0"


def use_standing_codex(brain_name: str, environ: Mapping[str, str] = os.environ) -> bool:
    return brain_name in {"openai", "codex"} and environ.get("JANE_WEB_STANDING_CODEX", "1") != "0"


def use_persistent_codex(brain_name: str, environ: Mapping[str, str] = os.environ) -> bool:
    return (
        brain_name in {"openai", "codex"}
        and not use_standing_codex(brain_name, environ)
        and environ.get("JANE_WEB_PERSISTENT_CODEX", "1") != "0"
    )


def web_chat_model(
    provider: str,
    *,
    environ: Mapping[str, str] = os.environ,
    provider_models: Mapping[str, Mapping[str, str]] = PROVIDER_MODELS,
    normalize_provider: Callable[[str], str] = normalize_frontier_provider,
) -> str:
    env_vars = {
        "claude": "JANE_MODEL_CLAUDE",
        "gemini": "JANE_MODEL_GEMINI",
        "openai": "JANE_MODEL_OPENAI",
        "codex": "JANE_MODEL_OPENAI",
    }
    normalized = normalize_provider(provider)
    env_var = env_vars.get(normalized)
    if env_var:
        configured = environ.get(env_var, "").strip()
        if configured:
            return configured
    return provider_models.get(normalized, provider_models["claude"])["smart"]
