from agent_skills import git_backup
from agent_skills.git_backup_helpers import (
    backup_commit_prompt,
    default_backup_summary,
    fallback_backup_summary,
    normalize_commit_summary,
)


def test_git_backup_exposes_helpers():
    assert git_backup._backup_commit_prompt is backup_commit_prompt
    assert git_backup._default_backup_summary is default_backup_summary
    assert git_backup._fallback_backup_summary is fallback_backup_summary
    assert git_backup._normalize_commit_summary is normalize_commit_summary


def test_backup_commit_prompt_caps_diff_and_preserves_prompt_shape():
    prompt = backup_commit_prompt("abcdef", max_diff_chars=3)
    assert prompt == (
        "You are a code summary expert. Summarize the following git changes concisely for a commit message. "
        "Keep it under 80 characters.\n\nChanges:\nabc"
    )


def test_normalize_commit_summary_strips_quotes_and_single_lines_output():
    assert normalize_commit_summary(' "Update files"\n') == "Update files"
    assert normalize_commit_summary("'Line one\nLine two'") == "Line one Line two"


def test_default_and_fallback_backup_summaries():
    assert default_backup_summary() == "Regular automated backup"
    assert fallback_backup_summary("2026-07-02T12:00:00") == "Automated backup: 2026-07-02T12:00:00"
