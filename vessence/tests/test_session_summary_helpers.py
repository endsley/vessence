from jane import session_summary
from jane.session_summary_helpers import (
    MAX_STATE_CHARS,
    build_session_summary_prompt,
    clean_field,
    coerce_summary_json_output,
    extract_json_object,
    fallback_summary,
    format_session_summary,
    guess_topic_label,
    is_trivial_turn,
    sanitize_summary,
    strip_system_metadata,
    summary_path,
)


def test_session_summary_keeps_legacy_helper_aliases():
    assert session_summary.format_session_summary is format_session_summary
    assert session_summary._is_trivial_turn is is_trivial_turn
    assert session_summary._strip_system_metadata is strip_system_metadata
    assert session_summary._build_session_summary_prompt is build_session_summary_prompt
    assert session_summary._coerce_summary_json_output is coerce_summary_json_output
    assert session_summary._extract_json_object is extract_json_object
    assert session_summary._sanitize_summary is sanitize_summary
    assert session_summary._clean_field is clean_field
    assert session_summary._fallback_summary is fallback_summary
    assert session_summary._guess_topic_label is guess_topic_label
    assert session_summary._summary_path_for_base is summary_path


def test_summary_path_sanitizes_session_id_and_uses_default_for_empty_safe_id(tmp_path):
    assert summary_path(tmp_path, "session/with spaces") == tmp_path / "session_with_spaces.json"
    assert summary_path(tmp_path, "...") == tmp_path / "default.json"
    assert summary_path(str(tmp_path), "abc-123.def") == tmp_path / "abc-123.def.json"


def test_format_session_summary_preserves_numbered_shape_and_topic_limit():
    summary = {
        "topics": [
            {"topic": "Vessence", "state": "Refactor running", "open_loop": "Run tests"},
            {"topic": "", "state": "State only", "open_loop": ""},
            {"topic": "Third", "state": "", "open_loop": ""},
            {"topic": "Fourth", "state": "hidden", "open_loop": ""},
        ]
    }

    assert format_session_summary(summary) == "\n".join([
        "1. Topic: Vessence",
        "   State: Refactor running",
        "   Open loop: Run tests",
        "2. Topic: Untitled",
        "   State: State only",
        "3. Topic: Third",
    ])
    assert format_session_summary({"topics": []}) == ""


def test_is_trivial_turn_preserves_skip_policy():
    assert is_trivial_turn("", "anything")
    assert is_trivial_turn("thanks!", "Done.")
    assert is_trivial_turn("what time is it", "It is noon.")
    assert is_trivial_turn("short", "short reply")
    assert not is_trivial_turn(
        "Please refactor the session summary helper into a separate module.",
        "I moved the pure helpers and ran tests.",
    )


def test_strip_system_metadata_removes_protocol_blocks_and_keeps_user_text():
    text = (
        "**Class Protocol: hidden\n\n"
        "keep this\n"
        "<class_protocol>secret</class_protocol>\n"
        "[EXTRACTED PARAMS] hidden\n\n"
        "[CURRENT CONVERSATION STATE] hidden [END CURRENT CONVERSATION STATE]\n"
        "(voice request — read aloud)\n"
        "[STANDING BRAIN MODE] hidden\n\n"
        "[Retrieved Memory] hidden\n\n"
        "also keep"
    )

    assert strip_system_metadata(text) == "keep this\n\n\n\n\n\n\n\n\n\nalso keep"


def test_extract_json_object_uses_balanced_object_and_rejects_non_objects():
    assert extract_json_object(
        'prefix {"topics":[{"topic":"A { brace }","state":"ok","open_loop":""}]} trailing'
    ) == {"topics": [{"topic": "A { brace }", "state": "ok", "open_loop": ""}]}
    assert extract_json_object("") is None
    assert extract_json_object("[1, 2, 3]") is None
    assert extract_json_object('{"topics": [') is None


def test_build_session_summary_prompt_preserves_qwen_contract():
    prompt = build_session_summary_prompt(
        {"topics": [{"topic": "A", "state": "B", "open_loop": ""}]},
        "clean user",
        "clean assistant",
    )

    assert "Current summary:\n{\"topics\": [{\"topic\": \"A\", \"state\": \"B\", \"open_loop\": \"\"}]}" in prompt
    assert "Latest user message:\nclean user" in prompt
    assert "Latest Jane response:\nclean assistant" in prompt
    assert "Keep max 3 topics" in prompt
    assert prompt.endswith('```json\n{"topics":[')


def test_coerce_summary_json_output_preserves_braced_output_and_wraps_suffix_only_output():
    assert coerce_summary_json_output(' {"topics": []}') == ' {"topics": []}'
    assert coerce_summary_json_output('{"topics": []}') == '{"topics": []}'
    assert coerce_summary_json_output('"topic":"A"}]}') == '{"topics":["topic":"A"}]}'


def test_sanitize_summary_dedupes_truncates_and_skips_empty_topics():
    summary = sanitize_summary({
        "topics": [
            {"topic": "Memory", "state": " first ", "open_loop": ""},
            {"topic": "memory", "state": "duplicate", "open_loop": ""},
            {"topic": "", "state": "", "open_loop": ""},
            {"topic": "Long", "state": "x" * (MAX_STATE_CHARS + 10), "open_loop": " next "},
            {"topic": "Ignored", "state": "too many", "open_loop": ""},
        ]
    })

    assert summary == {
        "topics": [
            {"topic": "Memory", "state": "first", "open_loop": ""},
            {"topic": "Long", "state": "x" * MAX_STATE_CHARS, "open_loop": "next"},
            {"topic": "Ignored", "state": "too many", "open_loop": ""},
        ]
    }


def test_fallback_summary_prepends_candidate_and_preserves_non_duplicate_topics():
    current = {
        "topics": [
            {"topic": "Memory Retrieval", "state": "old", "open_loop": ""},
            {"topic": "Other", "state": "kept", "open_loop": ""},
        ]
    }

    summary = fallback_summary(
        current,
        "We discussed memory retrieval work. Then a second sentence.",
        "Next, run focused tests.",
    )

    assert summary["topics"][0] == {
        "topic": "Memory Retrieval",
        "state": "We discussed memory retrieval work.",
        "open_loop": "Next, run focused tests.",
    }
    assert summary["topics"][1] == {"topic": "Other", "state": "kept", "open_loop": ""}
