import datetime as dt
from pathlib import Path

from agent_skills import nightly_self_improve
from agent_skills.nightly_report_rendering import (
    concrete_improvements,
    executive_summary_lines,
    stage_detail_lines,
    status_counts,
    summary_log_lines,
    summary_log_preamble,
    tldr_stage_lines,
    top_followups,
    unique_archive_path,
)


def test_nightly_self_improve_uses_report_rendering_helpers():
    assert nightly_self_improve._status_counts is status_counts
    assert nightly_self_improve._unique_archive_path is unique_archive_path
    assert nightly_self_improve._summary_log_preamble is summary_log_preamble
    assert nightly_self_improve._summary_log_lines is summary_log_lines
    assert nightly_self_improve._tldr_stage_lines is tldr_stage_lines
    assert nightly_self_improve._executive_summary_lines is executive_summary_lines
    assert nightly_self_improve._stage_detail_lines is stage_detail_lines


def test_status_counts_preserves_ok_timeout_failed_categories():
    results = [
        {"status": "ok"},
        {"status": "timeout"},
        {"status": "exit-1"},
        {"status": "crashed"},
    ]

    assert status_counts(results) == (1, 1, 2)


def test_unique_archive_path_appends_counter_for_existing_reports(tmp_path):
    started = dt.datetime(2026, 7, 2, 1, 2, 3)
    first = tmp_path / "self_improvement_20260702_010203.md"
    second = tmp_path / "self_improvement_20260702_010203_2.md"
    first.write_text("existing", encoding="utf-8")
    second.write_text("existing", encoding="utf-8")

    assert unique_archive_path(tmp_path, started) == Path(
        tmp_path / "self_improvement_20260702_010203_3.md"
    )


def test_summary_log_preamble_and_lines_preserve_append_log_shape():
    started = dt.datetime(2026, 7, 2, 1, 2, 3)
    results = [
        {"name": "Code Auditor", "status": "ok", "elapsed_s": 12, "log": "/tmp/code.log"},
        {"name": "Memory Janitor", "status": "timeout", "elapsed_s": 34, "log": "/tmp/memory.log"},
        {"name": "Doc Drift", "status": "exit-1", "elapsed_s": 56, "log": ""},
    ]

    assert summary_log_preamble() == (
        "# Nightly Self-Improvement Log\n\n"
        "Each row is one orchestrator run. Columns: job → status → duration.\n\n"
    )
    assert summary_log_lines(results, started) == [
        "\n## 2026-07-02 01:02\n",
        "- ✅ **Code Auditor** — ok (12s) → `code.log`",
        "- ⏱️ **Memory Janitor** — timeout (34s) → `memory.log`",
        "- ❌ **Doc Drift** — exit-1 (56s) → ``",
    ]


def test_tldr_stage_lines_preserves_existing_markers_and_defaults():
    results = [
        {"status": "ok"},
        {"status": "timeout"},
        {"status": "exit-2"},
    ]
    details = [
        {
            "name": "Code Auditor",
            "elapsed_s": 90,
            "problems_tldr_list": ["one problem"],
            "fixes_tldr_list": ["one fix"],
        },
        {
            "name": "Pipeline Audit",
            "elapsed_s": 60,
            "problems_tldr_list": [],
            "fixes_tldr_list": [],
        },
        {
            "name": "Doc Drift",
            "elapsed_s": 30,
            "problems_tldr_list": ["drift"],
            "fixes_tldr_list": [],
        },
    ]

    assert tldr_stage_lines(results, details) == [
        "- 1. ✓ Code Auditor (1.5m)",
        "  - Problems:",
        "    - one problem",
        "  - Fixes:",
        "    - one fix",
        "- 2. ⏱ Pipeline Audit (1.0m)",
        "  - Problems: none detected",
        "  - Fixes: none applied",
        "- 3. ✗ Doc Drift (0.5m)",
        "  - Problems:",
        "    - drift",
    ]


def test_top_followups_strips_bullets_and_keeps_existing_rollup_limit_shape():
    details = [
        {"followups": ["- first", "- second", "- ignored third from stage"]},
        {"followups": ["- third", "- fourth"]},
        {"followups": ["- never reached"]},
    ]

    assert top_followups(details) == ["first", "second", "third", "fourth"]


def test_concrete_improvements_filters_placeholder_text():
    details = [
        {"improvements": ["- No concrete improvement was recorded in the available logs/reports."]},
        {"improvements": ["- Wrote report", "- No concrete improvement in this stage"]},
    ]

    assert concrete_improvements(details) == ["- Wrote report"]


def test_executive_summary_lines_preserves_success_and_attention_text():
    quiet_details = [
        {"improvements": ["- No concrete improvement was recorded in the available logs/reports."]}
    ]
    active_details = [
        {"improvements": ["- Wrote report", "- Committed changes"]},
    ]

    assert executive_summary_lines(0, 0, quiet_details) == [
        "- All stages exited cleanly.",
        "- No concrete fix signals were found; this run mainly produced audits/reports.",
    ]
    assert executive_summary_lines(1, 2, active_details) == [
        "- 3 stage(s) need attention because they timed out or exited non-zero.",
        "- 2 concrete improvement/fix signals were found in logs or reports.",
    ]


def test_stage_detail_lines_preserves_stage_markdown_shape():
    detail = {
        "name": "Doc Drift Auditor",
        "status": "ok",
        "elapsed_s": 75,
        "purpose": "Checked docs.\nFound drift.",
        "problems": ["- Problem one"],
        "improvements": ["- Fix one"],
        "followups": ["- Follow up"],
        "artifacts": ["/tmp/report.md"],
    }

    assert stage_detail_lines(2, detail) == [
        "",
        "## Stage 2: Doc Drift Auditor",
        "",
        "- Status: `ok`",
        "- Duration: 75s (1.2 min)",
        "",
        "### What It Did",
        "",
        "- Checked docs. Found drift.",
        "",
        "### Problems It Found",
        "",
        "- Problem one",
        "",
        "### Improvements It Made",
        "",
        "- Fix one",
        "",
        "### Follow-Up Fixes Recommended",
        "",
        "- Follow up",
        "",
        "### Evidence Files",
        "",
        "- /tmp/report.md",
    ]


def test_stage_detail_lines_preserves_missing_artifact_text():
    detail = {
        "name": "Memory Janitor",
        "status": "timeout",
        "elapsed_s": 60,
        "purpose": "Cleaned memory.",
        "problems": [],
        "improvements": [],
        "followups": [],
        "artifacts": [],
    }

    assert stage_detail_lines(1, detail)[-1] == "- No artifact path was recorded."
