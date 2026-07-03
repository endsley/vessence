import datetime as dt
import json

from agent_skills import self_improve_log
from agent_skills.self_improve_log_helpers import (
    SEVERITIES,
    TIMESTAMP_FORMAT,
    build_vocal_summary_record,
    compose_summary,
    normalize_severity,
    parse_recent_summary_line,
    recent_summaries_from_lines,
)


def test_self_improve_log_uses_extracted_helpers():
    assert self_improve_log._SEVERITIES is SEVERITIES
    assert self_improve_log._TIMESTAMP_FORMAT == TIMESTAMP_FORMAT
    assert self_improve_log._build_vocal_summary_record is build_vocal_summary_record
    assert self_improve_log._recent_summaries_from_lines is recent_summaries_from_lines


def test_normalize_severity_preserves_allowed_values_and_info_fallback():
    assert normalize_severity("CRITICAL") == "critical"
    assert normalize_severity("medium") == "medium"
    assert normalize_severity("") == "info"
    assert normalize_severity(None) == "info"
    assert normalize_severity("urgent") == "info"


def test_compose_summary_prefers_explicit_summary_and_builds_structured_summary():
    assert compose_summary("Already written", what_was_wrong="ignored") == "Already written"
    assert compose_summary(
        None,
        what_was_wrong="It broke.",
        why_it_mattered="Users noticed",
        what_was_done="I fixed it!",
    ) == "It broke. Users noticed. I fixed it!."
    assert compose_summary(None) == ""


def test_build_vocal_summary_record_preserves_record_shape_and_optional_fields():
    record = build_vocal_summary_record(
        "Transcript Review",
        timestamp="2026-07-02T12:00:00Z",
        what_was_wrong="A route failed",
        why_it_mattered="Jane answered poorly",
        what_was_done="I added a guard",
        severity="medium",
    )

    assert record == {
        "timestamp": "2026-07-02T12:00:00Z",
        "job": "Transcript Review",
        "severity": "medium",
        "summary": "A route failed. Jane answered poorly. I added a guard.",
        "what_was_wrong": "A route failed",
        "why_it_mattered": "Jane answered poorly",
        "what_was_done": "I added a guard",
    }
    assert build_vocal_summary_record("Empty", timestamp="2026-07-02T12:00:00Z") is None


def test_parse_recent_summary_line_filters_invalid_and_old_entries():
    cutoff = dt.datetime(2026, 7, 1)
    recent = {"timestamp": "2026-07-02T12:00:00Z", "summary": "new"}

    assert parse_recent_summary_line(json.dumps(recent), cutoff=cutoff) == recent
    assert parse_recent_summary_line("", cutoff=cutoff) is None
    assert parse_recent_summary_line("{bad json", cutoff=cutoff) is None
    assert parse_recent_summary_line('{"timestamp": "bad"}', cutoff=cutoff) is None
    assert parse_recent_summary_line(
        '{"timestamp": "2026-06-30T23:59:59Z"}',
        cutoff=cutoff,
    ) is None


def test_recent_summaries_from_lines_returns_newest_first_and_preserves_limit_zero_behavior():
    cutoff = dt.datetime(2026, 7, 1)
    lines = [
        '{"timestamp": "2026-07-01T00:00:00Z", "summary": "oldest"}',
        '{"timestamp": "2026-07-02T00:00:00Z", "summary": "newest"}',
    ]

    assert [entry["summary"] for entry in recent_summaries_from_lines(lines, cutoff=cutoff)] == [
        "newest",
        "oldest",
    ]
    assert [entry["summary"] for entry in recent_summaries_from_lines(lines, cutoff=cutoff, limit=1)] == [
        "newest",
    ]
    assert [entry["summary"] for entry in recent_summaries_from_lines(lines, cutoff=cutoff, limit=0)] == [
        "newest",
        "oldest",
    ]
