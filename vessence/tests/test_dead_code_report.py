import datetime as dt

from agent_skills import dead_code_auditor
from agent_skills.dead_code_report import (
    _auto_deleted_section_lines,
    _dead_function_item,
    _dead_functions_section_lines,
    _dead_files_section_lines,
    _duplicate_functions_section_lines,
    _duplicate_group_lines,
    _relative_path_item,
    build_dead_code_report_markdown,
)


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


def test_dead_code_report_item_helpers_preserve_markdown_shapes(tmp_path):
    path = tmp_path / "agent_skills" / "old.py"
    duplicate_groups = [
        (f"hash-{index}", [tmp_path / "agent_skills" / f"{index}.py"])
        for index in range(22)
    ]

    assert _relative_path_item(tmp_path, path) == "- `agent_skills/old.py`"
    assert _relative_path_item(tmp_path, path, indent="    ") == "    - `agent_skills/old.py`"
    assert _dead_function_item(tmp_path, path, "unused_func") == (
        "- `agent_skills/old.py` :: `unused_func()`"
    )
    lines = _duplicate_group_lines(tmp_path, duplicate_groups)
    assert lines[:2] == [
        "- group `hash-0`:",
        "    - `agent_skills/0.py`",
    ]
    assert lines[-1] == "- … and 2 more groups"


def test_dead_code_report_section_helpers_preserve_section_shapes(tmp_path):
    deleted = tmp_path / "agent_skills" / "old.py"
    dead_file = tmp_path / "agent_skills" / "unused.py"
    dead_functions = [
        (tmp_path / "agent_skills" / f"live_{index}.py", f"unused_{index}")
        for index in range(52)
    ]
    duplicate_groups = [("abc123", [tmp_path / "agent_skills" / "a.py"])]

    assert _auto_deleted_section_lines(tmp_path, [deleted]) == [
        "## Auto-deleted (1 files)\n",
        "- `agent_skills/old.py`",
        "",
    ]
    assert _auto_deleted_section_lines(tmp_path, []) == []
    assert _dead_files_section_lines(tmp_path, [dead_file]) == [
        "## Dead files — review needed (1)\n",
        "(Candidates for deletion, but failed an auto-delete safety check —",
        " usually means the file is too new, too large, or outside agent_skills/test_code.)\n",
        "- `agent_skills/unused.py`",
        "",
    ]
    assert _dead_files_section_lines(tmp_path, []) == []
    dead_function_lines = _dead_functions_section_lines(tmp_path, dead_functions)
    assert dead_function_lines[:4] == [
        "## Possibly-dead functions (52)\n",
        "(No references found via grep. May be false positives if called via",
        " getattr, dynamic dispatch, or HTTP route registration.)\n",
        "- `agent_skills/live_0.py` :: `unused_0()`",
    ]
    assert dead_function_lines[-2:] == ["- … and 2 more", ""]
    assert _dead_functions_section_lines(tmp_path, []) == []
    assert _duplicate_functions_section_lines(tmp_path, duplicate_groups) == [
        "## Duplicate function bodies (1 groups)\n",
        "(Identical bodies — candidates for extraction into a shared helper.)\n",
        "- group `abc123`:",
        "    - `agent_skills/a.py`",
        "",
    ]
    assert _duplicate_functions_section_lines(tmp_path, []) == []


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
