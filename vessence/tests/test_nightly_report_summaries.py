from agent_skills import nightly_self_improve
from agent_skills.nightly_report_summaries import (
    bullet,
    condense_tldr_items,
    extract_markdown_bullets,
    pipeline_metric_bullet,
    summarize_generic_log,
    summarize_pipeline,
    summarize_transcript_review,
)


def test_orchestrator_uses_report_summary_helpers():
    assert nightly_self_improve._bullet is bullet
    assert nightly_self_improve._condense_tldr_items is condense_tldr_items
    assert nightly_self_improve._summarize_pipeline is summarize_pipeline


def test_nightly_job_summary_helpers_dispatch_reports_and_artifacts(tmp_path, monkeypatch):
    report = """
## Issue 1 [HIGH]
**Problem:** Jane answered stale context.
**Suggested fix:** Add a better guard.
"""
    problems, improvements, followups = nightly_self_improve.job_output_summary(
        "Transcript Quality Review",
        report,
        "Report written: configs/transcript_review_report.md",
    )

    assert "- Transcript review found 1 issues: 1 high." in problems
    assert "- Jane answered stale context." in problems
    assert "- Report written: configs/transcript_review_report.md" in improvements
    assert followups == ["- Add a better guard."]

    existing = tmp_path / "report.md"
    missing = tmp_path / "missing.md"
    existing.write_text("report", encoding="utf-8")
    monkeypatch.setitem(nightly_self_improve.JOB_ARTIFACTS, "Example Job", [existing, missing])
    monkeypatch.setattr(nightly_self_improve, "_read_text", lambda path: f"read:{path.name}")

    assert nightly_self_improve.existing_job_artifacts("Example Job") == [str(existing)]
    assert nightly_self_improve.primary_job_report_text("Example Job") == "read:report.md"
    assert nightly_self_improve.primary_job_report_text("Unknown Job") == ""


def test_bullet_collapses_whitespace():
    assert bullet("  one\n\t two   three ") == "- one two three"


def test_condense_tldr_items_filters_truncates_and_limits_items():
    long_text = "x" * 170

    assert condense_tldr_items(
        [
            "",
            "- Job ended with status `exit-1`.",
            "- First\nproblem",
            f"- {long_text}",
            "- Fourth",
        ],
        skip_prefixes=("Job ended with status",),
        limit=2,
    ) == [
        "First problem",
        f"{'x' * 157}...",
    ]


def test_extract_markdown_bullets_stops_at_next_heading():
    report = """
## Needs human review

- First issue
- Second issue

## Other

- Ignored
"""

    assert extract_markdown_bullets(report, "## Needs human review") == [
        "- First issue",
        "- Second issue",
    ]


def test_pipeline_metric_bullet_extracts_markdown_count_lines():
    report = "- Prompts audited: **30**\n- Other: plain"

    assert pipeline_metric_bullet(report, "Prompts audited") == "- Prompts audited: 30."
    assert pipeline_metric_bullet(report, "Classification failures") is None


def test_summarize_pipeline_collects_counts_failures_and_autofixes():
    report = """
- Prompts audited: **30**
- Classification failures: **2**
- Response failures: **1**
- Auto-fixes applied: **3**

## Response failures

- Prompt 14 failed response validation
"""
    log_tail = "AUTO-FIX: Added route exemplar\nAdded exemplar: calendar"

    problems, improvements = summarize_pipeline(report, log_tail)

    assert "- Prompts audited: 30." in problems
    assert "- Response failures: 1." in problems
    assert "- Prompt 14 failed response validation" in problems
    assert "- Auto-fixes applied: 3." in improvements
    assert "- AUTO-FIX: Added route exemplar" in improvements


def test_summarize_transcript_review_counts_severities_and_fields():
    report = """
## Issue 1 [HIGH]
**Problem:** Jane answered stale context.
**Suggested fix:** Add a better guard.

## Issue 2 [MEDIUM]
**Problem:** The client dropped an event.
"""

    problems, improvements = summarize_transcript_review(
        report,
        "Report written: configs/transcript_review_report.md",
    )

    assert "- Transcript review found 2 issues: 1 high, 1 medium." in problems
    assert "- Jane answered stale context." in problems
    assert "- The client dropped an event." in problems
    assert "- Report written: configs/transcript_review_report.md" in improvements


def test_summarize_generic_log_finds_errors_and_success_signals():
    problems, improvements = summarize_generic_log(
        "WARNING retry failed\nDone - wrote report\nCommitted changes",
    )

    assert problems == ["- WARNING retry failed"]
    assert improvements == ["- Done - wrote report", "- Committed changes"]
