from agent_skills import transcript_quality_review
from agent_skills.transcript_review_vocal import (
    build_vocal_summary_payload,
    spoken_vocal_severity,
    top_vocal_issue,
    vocal_issue_breakdown,
    vocal_severity_counts,
    vocal_what_was_wrong,
)


def test_vocal_summary_helpers_preserve_counts_breakdown_and_top_issue_policy():
    issues = [
        {"severity": "LOW", "issue": "Minor oddity."},
        {"severity": "MEDIUM", "issue": "Medium issue."},
        {"severity": "CRITICAL", "issue": "Timer failed."},
        {"severity": "LOW", "issue": "Another minor."},
    ]
    counts = vocal_severity_counts(issues)

    assert counts == {"CRITICAL": 1, "MEDIUM": 1, "LOW": 2}
    assert spoken_vocal_severity(counts) == "critical"
    assert spoken_vocal_severity({"CRITICAL": 0, "MEDIUM": 1, "LOW": 0}) == "medium"
    assert spoken_vocal_severity({"CRITICAL": 0, "MEDIUM": 0, "LOW": 1}) == "low"
    assert vocal_issue_breakdown(counts, len(issues)) == "1 critical, 1 medium, 2 minor"
    assert vocal_issue_breakdown({"SURPRISE": 1}, 1) == "1 items"
    assert top_vocal_issue(issues) == issues[2]
    assert vocal_what_was_wrong(issues, "1 critical") == (
        "Reviewing yesterday's conversations I spotted 1 critical issues. "
        "The most urgent was: Timer failed"
    )


def test_vocal_summary_payload_for_empty_review_uses_summary_field():
    assert build_vocal_summary_payload([]) == {
        "job": "Transcript Review",
        "summary": (
            "I reviewed yesterday's conversations and nothing looked "
            "off — all turns handled cleanly."
        ),
        "severity": "info",
    }


def test_vocal_summary_payload_counts_severities_and_prefers_critical_issue():
    payload = build_vocal_summary_payload([
        {"severity": "LOW", "issue": "Minor oddity."},
        {"severity": "MEDIUM", "issue": "Medium issue."},
        {"severity": "CRITICAL", "issue": "Timer failed."},
        {"severity": "LOW", "issue": "Another minor."},
    ])

    assert payload["severity"] == "critical"
    assert payload["what_was_wrong"] == (
        "Reviewing yesterday's conversations I spotted 1 critical, 1 medium, "
        "2 minor issues. The most urgent was: Timer failed"
    )
    assert payload["why_it_mattered"] == "These would have degraded your experience if left alone"
    assert "apply-fixes" in payload["what_was_done"]


def test_vocal_summary_payload_handles_unknown_severity_and_empty_issue_text():
    payload = build_vocal_summary_payload([
        {"severity": "SURPRISE", "issue": ""},
    ])

    assert payload["severity"] == "low"
    assert payload["what_was_wrong"] == (
        "Reviewing yesterday's conversations I spotted 1 items issues."
    )


def test_transcript_quality_review_reexports_vocal_payload_builder():
    assert transcript_quality_review.build_vocal_summary_payload is build_vocal_summary_payload
