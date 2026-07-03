"""Pure text helpers for job queue memory facts."""

from __future__ import annotations

from pathlib import Path

from agent_skills.prompt_queue_memory import truncate_with_ellipsis


def job_number_from_file(path: str) -> str:
    return Path(path).stem.split("_")[0]


def job_completion_fact(
    job_num: str,
    title: str,
    result: str,
    date_str: str,
) -> str:
    return (
        f"Job #{job_num} completed autonomously on {date_str}. "
        f"Title: {title}. "
        f"Result: {truncate_with_ellipsis(result, 300)}"
    )
