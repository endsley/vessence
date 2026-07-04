import json
from collections import Counter
from datetime import datetime

from agent_skills import pipeline_audit_100
from agent_skills.pipeline_audit_helpers import (
    build_judge_prompt,
    build_pipeline_audit_report_markdown,
    classification_failure_table_lines,
    count_section_lines,
    parse_judge_response,
    recent_prompt_rows_from_jsonl,
    response_failure_lines,
    strip_system_context,
    summarize_pipeline_events,
)


def test_pipeline_audit_uses_extracted_helpers():
    assert pipeline_audit_100._build_judge_prompt is build_judge_prompt
    assert pipeline_audit_100._build_pipeline_audit_report_markdown is build_pipeline_audit_report_markdown
    assert pipeline_audit_100._strip_system_context is strip_system_context
    assert pipeline_audit_100._recent_prompt_rows_from_jsonl is recent_prompt_rows_from_jsonl
    assert pipeline_audit_100._summarize_pipeline_events is summarize_pipeline_events
    assert pipeline_audit_100._parse_judge_response is parse_judge_response


def test_strip_system_context_removes_xml_and_conversation_state():
    message = (
        "<jane_architecture>hidden</jane_architecture>\n"
        "[CURRENT CONVERSATION STATE]hidden[END CURRENT CONVERSATION STATE]\n"
        "What is the weather?"
    )

    assert strip_system_context(message) == "What is the weather?"


def test_recent_prompt_rows_from_jsonl_filters_dedupes_and_takes_last_n():
    lines = [
        "not json",
        json.dumps({"message": "  hi  ", "timestamp": "t0"}),
        json.dumps({"message": "[system] ignore", "timestamp": "t1"}),
        json.dumps({"message": "first prompt", "timestamp": "t2"}),
        json.dumps({"message": "first prompt", "timestamp": "t3"}),
        json.dumps({"message": "(internal) ignore", "timestamp": "t4"}),
        json.dumps({"message": "second prompt", "timestamp": "t5"}),
    ]

    assert recent_prompt_rows_from_jsonl(lines, 1) == [
        {"prompt": "second prompt", "ts": "t5"}
    ]
    assert recent_prompt_rows_from_jsonl(lines, 10) == [
        {"prompt": "first prompt", "ts": "t2"},
        {"prompt": "second prompt", "ts": "t5"},
    ]


def test_summarize_pipeline_events_preserves_ack_tools_stage_and_response_rules():
    events = [
        {"type": "ack", "data": "Working"},
        {"type": "client_tool_call", "data": '{"tool": "weather"}'},
        {"type": "client_tool_call", "data": {"tool": "calendar"}},
        {"type": "delta", "data": "partial"},
        {"type": "done", "data": "final" * 200, "classification": "weather:High"},
    ]

    summary = summarize_pipeline_events(events)

    assert summary["classification"] == "weather:High"
    assert summary["stage"] == "stage2"
    assert summary["ack"] == "Working"
    assert summary["tool_calls"] == ["weather", "calendar"]
    assert summary["response"] == ("final" * 200)[:500]
    assert summary["events"] is events


def test_summarize_pipeline_events_uses_start_as_stage3_fallback():
    assert summarize_pipeline_events([{"type": "start"}])["stage"] == "stage3"


def test_parse_judge_response_extracts_case_insensitive_fields():
    assert parse_judge_response(
        "correct_class: Weather\n"
        "classification_ok: NO\n"
        "response_ok: yes\n"
    ) == {
        "raw": "correct_class: Weather\nclassification_ok: NO\nresponse_ok: yes\n",
        "correct_class": "weather",
        "classification_ok": False,
        "response_ok": True,
    }


def test_build_judge_prompt_preserves_audit_contract_and_truncates_response() -> None:
    prompt = build_judge_prompt(
        "what is the weather?",
        {
            "classification": "weather:High",
            "stage": "stage2",
            "ack": "",
            "tool_calls": ["weather"],
            "response": "x" * 350,
        },
        ["weather", "others"],
    )

    assert "USER PROMPT: what is the weather?" in prompt
    assert "- Classification: weather:High" in prompt
    assert "- Ack to user: (none)" in prompt
    assert "- Tool calls: ['weather']" in prompt
    assert "- Response text: " + ("x" * 300) in prompt
    assert "x" * 301 not in prompt
    assert "weather, others" in prompt
    assert "CLASSIFICATION_OK: yes | no" in prompt


def test_pipeline_report_section_helpers_preserve_sorting_limits_and_escaping():
    assert count_section_lines("Stage breakdown", {"stage3": 1, "stage2": 3}) == [
        "## Stage breakdown",
        "- stage2: 3",
        "- stage3: 1",
        "",
    ]
    assert count_section_lines(
        "Fixes",
        {"weather": 2},
        line_formatter=lambda key, count: f"- {key}: +{count} exemplars",
    ) == ["## Fixes", "- weather: +2 exemplars", ""]

    classification_failures = [
        {"prompt": f"prompt {index} | pipe", "got": "others", "should_be": "weather"}
        for index in range(31)
    ]
    lines = classification_failure_table_lines(classification_failures)
    assert "| prompt 0 \\| pipe | others | weather |" in lines
    assert not any("prompt 30" in line for line in lines)

    response_failures = [
        {
            "prompt": f"response {index} | pipe",
            "classification": "weather",
            "stage": "stage3",
            "response": "x" * 200,
        }
        for index in range(21)
    ]
    lines = response_failure_lines(response_failures)
    assert "- **response 0 \\| pipe** (weather/stage3): " + ("x" * 150) in lines
    assert not any("response 20" in line for line in lines)
    assert classification_failure_table_lines([]) == []
    assert response_failure_lines([]) == []


def test_build_pipeline_audit_report_markdown_preserves_sections_and_limits():
    classification_failures = [
        {"prompt": f"prompt {index} | with pipe", "got": "others", "should_be": "weather"}
        for index in range(31)
    ]
    response_failures = [
        {
            "prompt": f"response {index} | pipe",
            "classification": "weather",
            "stage": "stage3",
            "response": "x" * 200,
        }
        for index in range(21)
    ]

    report = build_pipeline_audit_report_markdown(
        started=datetime(2026, 7, 2, 12, 30),
        prompt_count=42,
        elapsed_seconds=12.6,
        stage_counts=Counter({"stage2": 3, "stage3": 2}),
        class_counts=Counter({"weather": 4, "others": 1}),
        classification_failures=classification_failures,
        response_failures=response_failures,
        fixes_applied=2,
        fixes_by_class=Counter({"weather": 2}),
    )

    assert report.startswith("# Pipeline Audit Report — 2026-07-02 12:30")
    assert "- Prompts audited: **42**" in report
    assert "- Elapsed: 13s" in report
    assert "- Classification failures: **31**" in report
    assert "- Response failures: **21**" in report
    assert "- stage2: 3" in report
    assert "- weather: 4" in report
    assert "- weather: +2 exemplars" in report
    assert "| prompt 0 \\| with pipe | others | weather |" in report
    assert "prompt 30" not in report
    assert "- **response 0 \\| pipe** (weather/stage3): " + ("x" * 150) in report
    assert "response 20" not in report
