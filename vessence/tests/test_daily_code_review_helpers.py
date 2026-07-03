import datetime as dt

from agent_skills import daily_code_review
from agent_skills.daily_code_review_helpers import (
    build_review_question,
    build_review_report,
    is_reviewable_file,
    truncate_file_diff,
    truncated_files_notice,
)


def test_daily_code_review_uses_extracted_helpers():
    assert daily_code_review._build_review_question is build_review_question
    assert daily_code_review._build_review_report is build_review_report
    assert daily_code_review._is_reviewable_file is is_reviewable_file
    assert daily_code_review._truncate_file_diff is truncate_file_diff
    assert daily_code_review._truncated_files_notice is truncated_files_notice


def test_is_reviewable_file_checks_extension_and_skip_patterns():
    extensions = {".py", ".kt"}
    skip_patterns = ["test_code/", "node_modules/"]

    assert is_reviewable_file("agent_skills/foo.py", extensions, skip_patterns)
    assert not is_reviewable_file("README.md", extensions, skip_patterns)
    assert not is_reviewable_file("test_code/foo.py", extensions, skip_patterns)


def test_truncate_file_diff_uses_strict_greater_than_limit():
    assert truncate_file_diff("abc", max_chars=3) == "abc"
    assert truncate_file_diff("abcd", max_chars=3) == "abc\n... (truncated)"


def test_truncated_files_notice_preserves_legacy_counting_formula():
    assert truncated_files_notice(10, 3) == "\n... and 7 more files (truncated)"


def test_build_review_question_preserves_focus_and_first_twenty_files():
    files = [f"file_{i}.py" for i in range(25)]
    question = build_review_question(files)

    assert question.startswith(
        "Daily code review: 25 files changed in the last 24 hours. "
        "Files: file_0.py, file_1.py"
    )
    assert "file_19.py" in question
    assert "file_20.py" not in question
    assert "Free speed wins — optimizations" in question
    assert "NEVER suggest speed improvements that compromise quality" in question


def test_build_review_report_preserves_markdown_shape():
    report = build_review_report(
        dt.datetime(2026, 7, 2, 8, 30),
        ["a.py", "b.kt"],
        "No issues.",
    )

    assert report == (
        "# Daily Code Review — 2026-07-02\n\n"
        "**Files reviewed:** 2\n"
        "**Files:** a.py, b.kt\n\n"
        "---\n\n"
        "No issues.\n"
    )
