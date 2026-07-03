"""Pure helpers for git_backup.py."""
from __future__ import annotations


def backup_commit_prompt(diff: str, *, max_diff_chars: int = 4000) -> str:
    capped_diff = diff[:max_diff_chars]
    return (
        f"You are a code summary expert. Summarize the following git changes concisely for a commit message. "
        f"Keep it under 80 characters.\n\nChanges:\n{capped_diff}"
    )


def normalize_commit_summary(summary: str) -> str:
    return summary.strip().strip('"').strip("'").replace("\n", " ")


def default_backup_summary() -> str:
    return "Regular automated backup"


def fallback_backup_summary(timestamp: str) -> str:
    return f"Automated backup: {timestamp}"
