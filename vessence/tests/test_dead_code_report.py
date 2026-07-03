import datetime as dt

from agent_skills import dead_code_auditor
from agent_skills.dead_code_report import build_dead_code_report_markdown


def test_dead_code_auditor_reexports_report_renderer():
    assert dead_code_auditor.build_dead_code_report_markdown is build_dead_code_report_markdown


def test_build_dead_code_report_markdown_for_clean_codebase(tmp_path):
    report = build_dead_code_report_markdown(
        root=tmp_path,
        auto_deleted=[],
        dead_files=[],
        dead_functions=[],
        duplicate_groups=[],
        generated_at=dt.datetime(2026, 7, 2, 9, 30),
    )

    assert report == (
        "# Dead Code Report — 2026-07-02 09:30\n\n"
        "Codebase clean — no dead code candidates found. ✅\n"
        "\n"
    )


def test_build_dead_code_report_markdown_for_all_sections(tmp_path):
    deleted = tmp_path / "agent_skills" / "old.py"
    dead_file = tmp_path / "agent_skills" / "unused.py"
    dead_func_file = tmp_path / "agent_skills" / "live.py"
    dup_a = tmp_path / "agent_skills" / "a.py"
    dup_b = tmp_path / "agent_skills" / "b.py"

    report = build_dead_code_report_markdown(
        root=tmp_path,
        auto_deleted=[deleted],
        dead_files=[dead_file],
        dead_functions=[(dead_func_file, "unused_func")],
        duplicate_groups=[("abc123", [dup_a, dup_b])],
        generated_at=dt.datetime(2026, 7, 2, 9, 30),
    )

    assert "## Auto-deleted (1 files)" in report
    assert "- `agent_skills/old.py`" in report
    assert "## Dead files — review needed (1)" in report
    assert "- `agent_skills/unused.py`" in report
    assert "## Possibly-dead functions (1)" in report
    assert "- `agent_skills/live.py` :: `unused_func()`" in report
    assert "## Duplicate function bodies (1 groups)" in report
    assert "- group `abc123`:" in report
    assert "    - `agent_skills/a.py`" in report
    assert "    - `agent_skills/b.py`" in report
