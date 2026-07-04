import datetime as dt

from agent_skills import transcript_quality_review
from agent_skills.transcript_review_format import (
    android_event_line,
    build_codex_report_markdown,
    build_condensed_context,
    codex_issue_section,
    codex_report_header,
    extract_json_array_text,
    parse_codex_issues,
    pipeline_event_line,
    prompt_dump_turn,
    strip_prompt_dump_context,
)


def test_transcript_quality_review_reexports_context_builder():
    assert transcript_quality_review._build_condensed_context is build_condensed_context
    assert transcript_quality_review._prompt_dump_turn is prompt_dump_turn
    assert transcript_quality_review._pipeline_event_line is pipeline_event_line
    assert transcript_quality_review._android_event_line is android_event_line
    assert transcript_quality_review._parse_codex_issues is parse_codex_issues


def test_prompt_dump_turn_filters_date_and_strips_conversation_state():
    record = {
        "timestamp": "2026-07-01T09:00:00Z",
        "session_id": "abcdef1234567890",
        "message": "[CURRENT]\n[END CURRENT CONVERSATION STATE] real message",
        "mode": "voice",
    }

    assert strip_prompt_dump_context(record["message"]) == "real message"
    assert prompt_dump_turn(record, "2026-07-01") == {
        "time": "2026-07-01T09:00:00Z",
        "session": "abcdef123456",
        "user_msg": "real message",
        "mode": "voice",
    }
    assert prompt_dump_turn(record, "2026-07-02") is None


def test_pipeline_and_android_event_filters_preserve_existing_summaries():
    assert pipeline_event_line(
        "2026-07-01 stage1_classifier classified weather\n",
        "2026-07-01",
    ) == "2026-07-01 stage1_classifier classified weather"
    assert pipeline_event_line("2026-07-01 irrelevant\n", "2026-07-01") is None

    assert android_event_line(
        {
            "timestamp": "2026-07-01T09:00:00Z",
            "category": "voice_flow",
            "message": "handled",
            "path": "stage2",
            "text_len": 12,
        },
        "2026-07-01",
    ) == "2026-07-01T09:00:00Z [voice_flow] handled path=stage2 text_len=12"
    assert android_event_line(
        {
            "timestamp": "2026-07-01T09:00:00Z",
            "category": "tool_handler",
            "message": "timer",
            "detail": "ok",
        },
        "2026-07-01",
    ) == "2026-07-01T09:00:00Z [tool_handler] timer detail=ok"
    assert android_event_line(
        {"timestamp": "2026-07-01T09:00:00Z", "category": "other", "message": "skip"},
        "2026-07-01",
    ) is None


def test_codex_issue_json_extraction_and_parsing():
    output = "```json\n[{\"issue\": \"bad\"}]\n```"

    assert extract_json_array_text(output) == '[{"issue": "bad"}]'
    assert parse_codex_issues(output) == [{"issue": "bad"}]
    assert extract_json_array_text("no json") is None
    assert parse_codex_issues("[not json]") is None


def test_build_condensed_context_keeps_sections_and_recent_events():
    turns = [
        {
            "time": "2026-07-01 09:00:00",
            "session": "abcdef123456",
            "user_msg": "hello " * 100,
        },
    ]
    pipeline_events = [f"server {i}" for i in range(505)]
    android_events = [f"android {i}" for i in range(305)]

    context = build_condensed_context(turns, pipeline_events, android_events, max_chars=100_000)

    assert "## User Turns (chronological)" in context
    assert "[2026-07-01 09:00:00] (abcdef123456)" in context
    assert "server 0" not in context
    assert "server 504" in context
    assert "android 0" not in context
    assert "android 304" in context


def test_build_condensed_context_truncates_at_max_chars():
    context = build_condensed_context(
        [{"time": "t", "session": "s", "user_msg": "x" * 500}],
        ["server"],
        ["android"],
        max_chars=80,
    )

    assert context.endswith("[TRUNCATED]")


def test_codex_report_section_helpers_preserve_header_and_issue_shape():
    generated_at = dt.datetime(2026, 7, 2, 13, 14, 15)
    issue = {
        "severity": "MEDIUM",
        "turn_time": "2026-07-01 09:01:00",
        "user_msg_snippet": "set a timer",
        "issue": "Timer failed",
        "root_cause": "Parser rejected duration",
        "suggested_fix": "Adjust parser",
        "relevant_log_lines": ["timer handler warning"],
    }

    assert codex_report_header("2026-07-01", generated_at) == (
        "# Transcript Quality Review — 2026-07-01\n\n"
        "Generated: 2026-07-02 13:14:15\n\n"
    )
    assert codex_issue_section(1, issue) == (
        "## Issue 1 [MEDIUM]\n\n"
        "**Turn:** 2026-07-01 09:01:00\n"
        "**User said:** set a timer\n\n"
        "**Problem:** Timer failed\n\n"
        "**Root cause:** Parser rejected duration\n\n"
        "**Suggested fix:** Adjust parser\n\n"
        "**Log evidence:**\n"
        "```\n"
        "timer handler warning\n"
        "```\n"
        "\n---\n\n"
    )


def test_build_codex_report_markdown_for_empty_and_issues():
    generated_at = dt.datetime(2026, 7, 2, 13, 14, 15)
    empty = build_codex_report_markdown([], "2026-07-01", generated_at=generated_at)
    assert empty == (
        "# Transcript Quality Review — 2026-07-01\n\n"
        "Generated: 2026-07-02 13:14:15\n\n"
        "No issues found. All turns look reasonable.\n"
    )

    report = build_codex_report_markdown(
        [
            {
                "severity": "MEDIUM",
                "turn_time": "2026-07-01 09:01:00",
                "user_msg_snippet": "set a timer",
                "issue": "Timer failed",
                "root_cause": "Parser rejected duration",
                "suggested_fix": "Adjust parser",
                "relevant_log_lines": ["timer handler warning"],
            },
        ],
        "2026-07-01",
        generated_at=generated_at,
    )

    assert "## Issue 1 [MEDIUM]" in report
    assert "**User said:** set a timer" in report
    assert "```\ntimer handler warning\n```" in report
