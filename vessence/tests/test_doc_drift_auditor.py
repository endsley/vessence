from types import SimpleNamespace

from agent_skills import doc_drift_auditor as auditor


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
