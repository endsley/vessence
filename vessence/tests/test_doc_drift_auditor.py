from types import SimpleNamespace

from agent_skills import doc_drift_auditor as auditor
from agent_skills.doc_drift_helpers import (
    build_drift_report,
    drift_vocal_summary_kwargs,
    extract_active_cron_script_names,
    extract_class_map_keys,
    extract_doc_table_classes,
    extract_documented_cron_script_names,
    extract_inactive_documented_cron_script_names,
)


def test_doc_drift_auditor_exposes_extracted_parsers():
    assert auditor._drift_vocal_summary_kwargs is drift_vocal_summary_kwargs
    assert auditor._extract_class_map_keys is extract_class_map_keys
    assert auditor._extract_doc_table_classes is extract_doc_table_classes


def test_paused_cron_section_is_not_claimed_active(tmp_path, monkeypatch):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "CRON_JOBS.md").write_text(
        "\n".join(
            [
                "## 1. Auto Pull",
                "- **Script Path:** `$VESSENCE_HOME/startup_code/auto_pull.sh`",
                "",
                "## Paused: Kathia Schedule Scraper",
                "- **Script Path:** `$VESSENCE_HOME/startup_code/run_kathia_schedule.py`",
                "",
                "## Removed Jobs (historical reference)",
                "- **Script Path:** `$VESSENCE_HOME/agent_skills/old_job.py`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="0 * * * * $VESSENCE_HOME/startup_code/auto_pull.sh\n",
            stderr="",
        )

    monkeypatch.setattr(auditor, "CONFIGS", configs)
    monkeypatch.setattr(auditor.subprocess, "run", fake_run)
    auditor._warnings.clear()
    auditor._changes.clear()

    auditor.audit_cron()

    assert auditor._warnings == []


def test_class_map_parser_normalizes_space_aliases():
    source = """
_CLASS_MAP = {
    "WEATHER": "weather",
    "NATIONALGRID BILLS": "nationalgrid bills",
    "NATIONALGRID_BILLS": "nationalgrid bills",
}
"""

    assert auditor._extract_class_map_keys(source) == {
        "WEATHER",
        "NATIONALGRID_BILLS",
    }


def test_doc_table_class_parser_allows_digits_and_first_column_only():
    doc = """
| Class | Route | Notes |
| --- | --- | --- |
| WEATHER | weather | normal row |
| FORCE_STAGE3 | others | explicit escalation |
| notes | FORCE_STAGE3 | prose in another cell should not count |
| `READ_EMAIL` | email | backtick formatted |

| Env Var | Default | Notes |
| --- | --- | --- |
| JANE_PIPELINE | v2 | not a class |
"""

    assert auditor._extract_doc_table_classes(doc) == {
        "WEATHER",
        "FORCE_STAGE3",
        "READ_EMAIL",
    }


def test_cron_helpers_extract_active_documented_and_inactive_scripts():
    cron_lines = [
        "SHELL=/bin/bash",
        "# 0 * * * * /repo/disabled.py",
        "0 * * * * /repo/active.py",
        "@daily /repo/job.sh",
        "FOO=bar",
    ]
    doc_text = "\n".join([
        "## Active",
        "- **Script Path:** `$VESSENCE_HOME/startup_code/active.py`",
        "",
        "## Paused: Job",
        "- **Script Path:** `$VESSENCE_HOME/startup_code/job.sh`",
        "",
        "## Removed Jobs",
        "- **Script Path:** `$VESSENCE_HOME/startup_code/old.py`",
    ])

    assert extract_active_cron_script_names(cron_lines) == {"active.py", "job.sh"}
    assert extract_documented_cron_script_names(doc_text) == {
        "active.py",
        "job.sh",
        "old.py",
    }
    assert extract_inactive_documented_cron_script_names(doc_text) == {
        "job.sh",
        "old.py",
    }


def test_build_drift_report_preserves_sections_and_empty_state():
    assert build_drift_report([], [], "2026-07-02 12:00") == (
        "# Doc Drift Report — 2026-07-02 12:00\n\n"
        "All docs in sync. ✅\n\n"
    )
    assert build_drift_report(
        ["- CRON_JOBS.md: fixed row"],
        ["pipeline doc missing WEATHER"],
        "2026-07-02 12:00",
    ) == (
        "# Doc Drift Report — 2026-07-02 12:00\n\n"
        "## Auto-fixed\n\n"
        "- CRON_JOBS.md: fixed row\n"
        "\n"
        "## Needs human review\n\n"
        "- pipeline doc missing WEATHER\n\n"
    )


def test_drift_vocal_summary_kwargs_preserves_message_branches() -> None:
    assert drift_vocal_summary_kwargs([], []) == {
        "job": "Doc Drift Audit",
        "summary": (
            "I checked that docs like the cron registry, skill "
            "registry, and pipeline class map still match the code. "
            "Everything lined up — no drift."
        ),
        "severity": "info",
    }

    fixes_only = drift_vocal_summary_kwargs(["- fixed"], [])
    assert fixes_only["severity"] == "info"
    assert fixes_only["what_was_wrong"] == "I found 1 doc that needed small fixes"
    assert fixes_only["what_was_done"] == (
        "I auto-fixed 1 and flagged the rest in the doc drift report for you to review"
    )

    warnings_only = drift_vocal_summary_kwargs([], ["missing class"])
    assert warnings_only["severity"] == "medium"
    assert warnings_only["what_was_wrong"] == "I found 1 spot where docs drifted from the code"
    assert warnings_only["what_was_done"] == (
        "I flagged them in the doc drift report for your review — "
        "the ambiguous ones need a human call"
    )
