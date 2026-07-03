import datetime as dt
from pathlib import Path

from agent_skills import nightly_audit
from agent_skills.nightly_audit_helpers import (
    first_script_lines,
    is_sleep_window_hour,
    latest_audit_summary_payload,
    truncate_text,
)


def test_nightly_audit_uses_extracted_helpers():
    assert nightly_audit._truncate_text is truncate_text
    assert nightly_audit._first_script_lines is first_script_lines
    assert nightly_audit._latest_audit_summary_payload is latest_audit_summary_payload
    assert nightly_audit._is_sleep_window_hour is is_sleep_window_hour


def test_truncate_text_preserves_existing_marker_and_boundary():
    assert truncate_text("abc", 3) == "abc"
    assert truncate_text("abcd", 3) == "abc\n... [truncated at 3 chars]"


def test_first_script_lines_preserves_splitlines_behavior():
    assert first_script_lines("a\nb\nc\n", 2) == "a\nb"
    assert first_script_lines("", 200) == ""


def test_latest_audit_summary_payload_preserves_json_shape():
    now = dt.datetime(2026, 7, 2, 8, 30)
    payload = latest_audit_summary_payload(
        now,
        "\nReport body\n",
        Path("/tmp/audit.md"),
        "Healthy",
    )

    assert payload == {
        "generated_at": "2026-07-02T08:30:00",
        "report_path": "/tmp/audit.md",
        "health_summary": "Healthy",
        "report": "Report body",
    }


def test_is_sleep_window_hour_preserves_existing_bounds():
    assert not is_sleep_window_hour(0)
    assert is_sleep_window_hour(1)
    assert is_sleep_window_hour(6)
    assert not is_sleep_window_hour(7)
