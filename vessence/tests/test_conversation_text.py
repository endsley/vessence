from memory.v1.conversation_text import (
    ASSISTANT_FILLER_PATTERNS,
    LOW_VALUE_EXACT_TURNS,
    USER_LOW_VALUE_PATTERNS,
    _code_change_summary_prompt,
    _generic_turn_summary_prompt,
    build_short_term_summary_plan,
    compact_whitespace,
    is_low_value_short_question,
    looks_like_bad_thematic_output,
    looks_like_code_edit,
    matches_any_pattern,
    normalize_summary_bullet_line,
    normalize_short_term_summary,
    prepare_thematic_turn,
    should_store_short_term_turn,
    strip_injected_metadata,
)


def test_compact_whitespace_collapses_runs_and_handles_empty_values():
    assert compact_whitespace(" one\n\t two   three ") == "one two three"
    assert compact_whitespace("") == ""
    assert compact_whitespace(None) == ""


def test_strip_injected_metadata_removes_protocol_and_state_blocks():
    text = """keep this
<class_protocol>
metadata
</class_protocol>
[EXTRACTED PARAMS] hidden

[CURRENT CONVERSATION STATE] old [END CURRENT CONVERSATION STATE]
(voice request — transcribed)
[STANDING BRAIN MODE] on
also keep"""

    assert strip_injected_metadata(text) == "keep this\n\n\n\n\nalso keep"


def test_bad_thematic_output_requires_protocol_signal():
    assert looks_like_bad_thematic_output("Class protocol: use this metadata")
    assert looks_like_bad_thematic_output("I need clarification about [CURRENT CONVERSATION STATE]")
    assert not looks_like_bad_thematic_output("I need clarification about the meeting time.")
    assert not looks_like_bad_thematic_output("")


def test_prepare_thematic_turn_skips_metadata_only_and_labels_real_turns():
    assert prepare_thematic_turn("<class_protocol>x</class_protocol>", "[EXTRACTED PARAMS] y") == ""
    assert prepare_thematic_turn("Please refactor memory code", "Done in memory/v1/file.py") == (
        "User: Please refactor memory code\nJane: Done in memory/v1/file.py"
    )


def test_should_store_short_term_turn_filters_low_value_chatter():
    assert "thanks" in LOW_VALUE_EXACT_TURNS
    assert is_low_value_short_question("user", "why?")
    assert not is_low_value_short_question("assistant", "why?")
    assert not is_low_value_short_question("user", "why did this fail?")
    assert matches_any_pattern("hey jane, testing?", USER_LOW_VALUE_PATTERNS)
    assert matches_any_pattern("i'm here. what do you need?", ASSISTANT_FILLER_PATTERNS)

    assert not should_store_short_term_turn("user", "thanks")
    assert not should_store_short_term_turn("user", "why?")
    assert should_store_short_term_turn("user", "MEMORY_SYSTEM_OK")
    assert not should_store_short_term_turn("assistant", "I'm here. What do you need?")
    assert should_store_short_term_turn("user", "Remember that the RA cron should keep source artifacts.")


def test_short_term_summary_prompt_helpers_preserve_prompt_contracts():
    code_prompt = _code_change_summary_prompt("assistant", "Patched memory/v1/file.py")
    assert code_prompt.startswith(
        "Summarize this assistant turn as a compact code-change memory note"
    )
    assert "- Start each bullet with '- '." in code_prompt
    assert "Role: assistant\nTurn: Patched memory/v1/file.py" in code_prompt

    generic_prompt = _generic_turn_summary_prompt("user", "Decision: keep behavior stable.")
    assert generic_prompt.startswith("Compress this single conversation turn")
    assert "- Do not add analysis or speculation." in generic_prompt
    assert "Role: user\nTurn: Decision: keep behavior stable." in generic_prompt


def test_code_edit_detection_and_summary_normalization():
    assert looks_like_code_edit("*** Begin Patch\n*** Update File: memory/v1/file.py")
    assert not looks_like_code_edit("Discussed project priorities.")

    assert normalize_summary_bullet_line("  * added test ") == "- added test"
    assert normalize_summary_bullet_line("1. changed file") == "- changed file"
    assert normalize_summary_bullet_line("- kept bullet") == "- kept bullet"
    assert normalize_summary_bullet_line("plain line") == "plain line"
    assert normalize_summary_bullet_line(" \n ") == ""

    assert normalize_short_term_summary("line one\n line two", preserve_bullets=False) == "line one line two"
    assert normalize_short_term_summary("1. changed file\n* added test", preserve_bullets=True) == (
        "- changed file\n- added test"
    )
    assert normalize_short_term_summary("No durable context.\n- No durable context.", preserve_bullets=True) == (
        "No durable context."
    )


def test_build_short_term_summary_plan_handles_empty_and_short_rule_based_turns():
    empty = build_short_term_summary_plan("user", " \n ")
    assert empty.immediate_summary == ""
    assert empty.summary_style == "concise_turn_memory_v1"
    assert empty.prompt is None
    assert not empty.preserve_bullets

    short = build_short_term_summary_plan("user", "  Remember the green tea preference.  ")
    assert short.immediate_summary == "Remember the green tea preference."
    assert short.summary_style == "rule_based_turn_memory_v1"
    assert short.prompt is None
    assert not short.preserve_bullets


def test_build_short_term_summary_plan_uses_generic_prompt_for_long_turns():
    long_content = "Decision: keep refactors behavior-preserving. " * 5
    plan = build_short_term_summary_plan("user", long_content)

    assert plan.immediate_summary is None
    assert plan.summary_style == "concise_turn_memory_v1"
    assert "Compress this single conversation turn" in (plan.prompt or "")
    assert "Decision: keep refactors behavior-preserving." in (plan.prompt or "")
    assert not plan.preserve_bullets


def test_build_short_term_summary_plan_uses_code_change_prompt_for_assistant_edits():
    plan = build_short_term_summary_plan(
        "assistant",
        "*** Begin Patch\n*** Update File: memory/v1/conversation_text.py",
    )

    assert plan.immediate_summary is None
    assert plan.summary_style == "code_change_turn_memory_v1"
    assert "compact code-change memory note" in (plan.prompt or "")
    assert "memory/v1/conversation_text.py" in (plan.prompt or "")
    assert plan.preserve_bullets
