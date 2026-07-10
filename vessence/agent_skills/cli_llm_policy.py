"""Pure policy helpers for claude_cli_llm.py."""
from __future__ import annotations


TRUNCATION_MARKER = "\n... [TRUNCATED] ...\n"


def truncate_prompt_for_cli(
    prompt: str,
    *,
    limit: int = 32000,
    head_chars: int = 1000,
    tail_chars: int = 31000,
) -> str:
    if len(prompt) <= limit:
        return prompt
    return prompt[:head_chars] + TRUNCATION_MARKER + prompt[-tail_chars:]


def should_try_fallback(error_message: str) -> bool:
    lowered = error_message.lower()
    return (
        "limit" in lowered
        or "quota" in lowered
        or "timed out" in lowered
        or "failed" in lowered
        or "empty response" in lowered
    )


def fallback_provider_sequence(current_provider: str, sequence: tuple[str, ...] = ("openai", "gemini", "claude")) -> list[str]:
    return [provider for provider in sequence if provider != current_provider]


def model_for_tier(provider_config: dict, tier: str) -> str:
    if tier == "orchestrator" or tier == "agent":
        return provider_config["smart"]
    return provider_config["cheap"]


def extract_json_text(text: str) -> str:
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    if "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text
