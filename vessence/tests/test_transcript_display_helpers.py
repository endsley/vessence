from agent_skills import show_transcript
from agent_skills.transcript_display_helpers import (
    first_user_preview_text,
    parse_turns_flag_args,
    speaker_label,
    strip_context_prefix,
)


def test_show_transcript_uses_extracted_display_helpers():
    assert show_transcript._first_user_preview_text is first_user_preview_text
    assert show_transcript._parse_turns_flag_args is parse_turns_flag_args
    assert show_transcript._speaker_label is speaker_label


def test_speaker_label_preserves_user_vs_jane_mapping():
    assert speaker_label("user") == "YOU"
    assert speaker_label("assistant") == "JANE"
    assert speaker_label("tool") == "JANE"


def test_first_user_preview_strips_context_prefix_and_collapses_whitespace():
    text = "[CURRENT CONVERSATION STATE]   hello\n\nworld"
    assert first_user_preview_text(text) == "hello world"
    assert strip_context_prefix("[ANDROID message] do this") == "do this"


def test_first_user_preview_truncates_with_existing_ellipsis_character():
    assert first_user_preview_text("abcdef", max_len=3) == "abc…"


def test_parse_turns_flag_args_handles_absent_valid_missing_and_invalid():
    assert parse_turns_flag_args(["--latest"]) == (None, ["--latest"], None)
    assert parse_turns_flag_args(["--turns", "4", "--latest"]) == (
        4,
        ["--latest"],
        None,
    )
    assert parse_turns_flag_args(["--turns"]) == (
        None,
        ["--turns"],
        "--turns requires a number",
    )
    assert parse_turns_flag_args(["--turns", "x"]) == (
        None,
        ["--turns", "x"],
        "--turns: not an integer: x",
    )
