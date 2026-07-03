from agent_skills import claude_cli_llm
from agent_skills.cli_llm_policy import (
    TRUNCATION_MARKER,
    extract_json_text,
    fallback_provider_sequence,
    model_for_tier,
    should_try_fallback,
    truncate_prompt_for_cli,
)


def test_claude_cli_llm_exposes_policy_helpers():
    assert claude_cli_llm._extract_json_text is extract_json_text
    assert claude_cli_llm._fallback_provider_sequence is fallback_provider_sequence
    assert claude_cli_llm._model_for_tier is model_for_tier
    assert claude_cli_llm._should_try_fallback is should_try_fallback
    assert claude_cli_llm._truncate_prompt_for_cli is truncate_prompt_for_cli


def test_truncate_prompt_for_cli_preserves_short_prompts_and_truncates_long_prompts():
    prompt = "x" * 32000
    assert truncate_prompt_for_cli(prompt) == prompt

    long_prompt = "a" * 1000 + "middle" + "z" * 31000
    truncated = truncate_prompt_for_cli(long_prompt)
    assert truncated.startswith("a" * 1000)
    assert TRUNCATION_MARKER in truncated
    assert truncated.endswith("z" * 31000)
    assert "middle" not in truncated


def test_should_try_fallback_matches_existing_error_policy():
    assert should_try_fallback("rate limit exceeded")
    assert should_try_fallback("quota exhausted")
    assert should_try_fallback("CLI timed out after 60s")
    assert should_try_fallback("CLI (codex) failed (exit 1): bad")
    assert not should_try_fallback("CLI not found: claude")


def test_fallback_provider_sequence_excludes_current_provider():
    assert fallback_provider_sequence("openai") == ["gemini", "claude"]
    assert fallback_provider_sequence("gemini") == ["openai", "claude"]
    assert fallback_provider_sequence("other") == ["openai", "gemini", "claude"]


def test_model_for_tier_uses_smart_for_agent_or_orchestrator_and_cheap_otherwise():
    config = {"smart": "smart-model", "cheap": "cheap-model"}
    assert model_for_tier(config, "orchestrator") == "smart-model"
    assert model_for_tier(config, "agent") == "smart-model"
    assert model_for_tier(config, "utility") == "cheap-model"


def test_extract_json_text_strips_json_and_generic_fences():
    assert extract_json_text('```json\n{"ok": true}\n```') == '{"ok": true}'
    assert extract_json_text('```\n{"ok": true}\n```') == '{"ok": true}'
    assert extract_json_text('{"ok": true}') == '{"ok": true}'
