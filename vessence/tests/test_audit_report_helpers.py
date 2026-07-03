from agent_skills import nightly_audit, notify_audit_results
from agent_skills.audit_report_helpers import (
    audit_announcement_message,
    audit_announcement_payload,
    audit_notification_state,
    extract_health_summary,
    extract_notification_brief,
)


def test_audit_scripts_use_extracted_report_helpers() -> None:
    assert nightly_audit._extract_health_summary is extract_health_summary
    assert notify_audit_results._extract_brief is extract_notification_brief
    assert notify_audit_results._audit_announcement_message is audit_announcement_message
    assert notify_audit_results._audit_announcement_payload is audit_announcement_payload
    assert notify_audit_results._audit_notification_state is audit_notification_state


def test_extract_notification_brief_strips_headings_collapses_blanks_and_truncates() -> None:
    report = "# Audit Report\n\nBody line\n\n\n## Details\nMore detail"
    assert extract_notification_brief(report) == "Body line\n\nMore detail"
    assert extract_notification_brief("# H\n" + ("x" * 20), max_chars=10) == "xxxxxxx..."


def test_extract_health_summary_reads_section_until_next_heading() -> None:
    report = """
# Audit

## Health Summary
System is healthy.
One small issue remains.
**Fixed Issues**
Ignored.
""".strip()
    assert extract_health_summary(report) == "System is healthy. One small issue remains."


def test_extract_health_summary_truncates_and_falls_back_to_first_line() -> None:
    assert extract_health_summary("## Health Summary\n" + ("x" * 300), max_chars=20) == "x" * 20
    assert extract_health_summary("# No section here\nBody", max_chars=20) == "No section here"
    assert extract_health_summary("", max_chars=20) == ""


def test_audit_announcement_helpers_preserve_payload_shapes() -> None:
    message = audit_announcement_message(local_stamp="2026-07-02 11:00 AM", brief="All clear.")
    assert message == (
        "**Morning audit summary**\n"
        "Latest audit run: 2026-07-02 11:00 AM\n\n"
        "All clear."
    )
    assert audit_announcement_payload(
        timestamp="2026-07-02T15:00:00+00:00",
        announcement_id="audit_result_2026-07-02",
        message=message,
    ) == {
        "timestamp": "2026-07-02T15:00:00+00:00",
        "type": "queue_progress",
        "id": "audit_result_2026-07-02",
        "message": message,
        "final": True,
    }
    assert audit_notification_state(
        today="2026-07-02",
        generated_at="2026-07-02T14:00:00+00:00",
        announcement_id="audit_result_2026-07-02",
    ) == {
        "last_notified_date": "2026-07-02",
        "last_report_generated_at": "2026-07-02T14:00:00+00:00",
        "announcement_id": "audit_result_2026-07-02",
    }
