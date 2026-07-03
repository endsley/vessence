"""Pure helpers for auto_commit_wip.py."""
from __future__ import annotations


def committable_status_lines(status_stdout: str) -> list[str]:
    return [
        line
        for line in status_stdout.splitlines()
        if line.strip() and not line[3:].strip().startswith(".git.backup")
    ]


def auto_commit_phase(push: bool) -> str:
    return "post-self-improve" if push else "pre-self-improve WIP"


def auto_commit_message(*, phase: str, timestamp: str, changed_count: int) -> str:
    return (
        f"auto-commit: {phase} ({timestamp})\n\n"
        f"{changed_count} file(s) changed. Committed automatically by the\n"
        f"nightly self-improvement orchestrator."
    )
