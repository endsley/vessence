from pathlib import Path

from agent_skills import transcript_quality_review
from agent_skills.transcript_review_prompts import (
    CLAUDE_FIX_PROMPT_TEMPLATE,
    CODEX_PROMPT_TEMPLATE,
    FRONTIER_FIX_PROMPT_TEMPLATE,
    build_codex_review_prompt,
    build_frontier_fix_prompt,
)


def test_codex_review_prompt_inserts_context_and_preserves_json_contract():
    prompt = build_codex_review_prompt("turns and logs")

    assert CODEX_PROMPT_TEMPLATE.format(context="turns and logs") == prompt
    assert "--- BEGIN TRANSCRIPT + LOGS ---\n\nturns and logs" in prompt
    assert "emit ONLY a JSON array" in prompt
    assert '"severity": "CRITICAL|MEDIUM|LOW"' in prompt


def test_frontier_fix_prompt_inserts_report_path_content_and_policy():
    prompt = build_frontier_fix_prompt(Path("/tmp/report.md"), "## Issue 1")

    assert FRONTIER_FIX_PROMPT_TEMPLATE.format(
        report_path=Path("/tmp/report.md"),
        report_content="## Issue 1",
    ) == prompt
    assert CLAUDE_FIX_PROMPT_TEMPLATE is FRONTIER_FIX_PROMPT_TEMPLATE
    assert "append a \"## Fixes Applied\" section to the report at\n   /tmp/report.md" in prompt
    assert "Do NOT add regex/keyword \"fast paths\"" in prompt
    assert "## Issue 1" in prompt


def test_transcript_quality_review_reexports_prompt_contract():
    assert transcript_quality_review.CODEX_PROMPT_TEMPLATE is CODEX_PROMPT_TEMPLATE
    assert transcript_quality_review.CLAUDE_FIX_PROMPT_TEMPLATE is CLAUDE_FIX_PROMPT_TEMPLATE
    assert transcript_quality_review.build_codex_review_prompt is build_codex_review_prompt
    assert transcript_quality_review.build_frontier_fix_prompt is build_frontier_fix_prompt
