from agent_skills import save_context_summary
from agent_skills.context_summary_helpers import (
    clean_qwen_summary,
    context_snapshot_fact,
    last_summary_record,
    parse_hook_payload,
    response_text_from_payload,
    should_summarize_response,
)


def test_save_context_summary_exposes_helpers():
    assert save_context_summary._clean_qwen_summary is clean_qwen_summary
    assert save_context_summary._context_snapshot_fact is context_snapshot_fact
    assert save_context_summary._last_summary_record is last_summary_record
    assert save_context_summary._parse_hook_payload is parse_hook_payload
    assert save_context_summary._response_text_from_payload is response_text_from_payload
    assert save_context_summary._should_summarize_response is should_summarize_response


def test_save_context_summary_utcnow_helper_preserves_naive_shape():
    assert save_context_summary._utcnow().tzinfo is None


def test_parse_hook_payload_accepts_dict_json_only():
    assert parse_hook_payload('{"message": "hello"}') == {"message": "hello"}
    assert parse_hook_payload("  ") == {}
    assert parse_hook_payload("not json") == {}
    assert parse_hook_payload("[1, 2, 3]") == {}


def test_response_text_and_summary_gate_preserve_message_threshold():
    assert response_text_from_payload({"message": "hello"}) == "hello"
    assert response_text_from_payload({"other": "hello"}) == ""
    assert not should_summarize_response("x" * 49)
    assert should_summarize_response("x" * 50)
    assert not should_summarize_response(" " * 100)


def test_clean_qwen_summary_strips_header_lines_and_joins_remaining_output():
    stdout = """
--- qwen output ---
First sentence.
Second sentence.
--- metadata ---
"""
    assert clean_qwen_summary(stdout) == "First sentence. Second sentence."


def test_context_snapshot_fact_and_record_shapes():
    assert context_snapshot_fact("2026-07-02T12:00:00Z", "Did work.") == (
        "[Context snapshot 2026-07-02T12:00:00Z] Did work."
    )
    assert last_summary_record("2026-07-02T12:00:00Z", "Did work.") == {
        "timestamp": "2026-07-02T12:00:00Z",
        "summary": "Did work.",
    }
