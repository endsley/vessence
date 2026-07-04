"""Instant chat command classification and formatting helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


JOB_QUEUE_PHRASES = {
    "show job queue", "job queue", "show me the job queue",
    "show jobs", "list jobs", "pending jobs", "/jobs",
}
COMPLETED_JOBS_PHRASES = {
    "show completed jobs", "completed jobs", "show me completed jobs",
    "finished jobs", "done jobs", "completed job queue",
}
COMMANDS_PHRASES = {"my commands", "commands", "show commands", "show me my commands", "list commands"}
CRON_PHRASES = {"show cron jobs", "cron jobs", "cron"}


def normalize_instant_command(message: str) -> str | None:
    msg = message.lower().strip().rstrip(":").strip()
    if len(msg) > 40:
        return None
    return msg


def instant_command_kind(message: str) -> str | None:
    msg = normalize_instant_command(message)
    if msg is None:
        return None
    if msg in JOB_QUEUE_PHRASES:
        return "job_queue"
    if msg in COMPLETED_JOBS_PHRASES:
        return "completed_jobs"
    if msg in COMMANDS_PHRASES:
        return "commands"
    if msg in CRON_PHRASES:
        return "cron"
    return None


def commands_markdown() -> str:
    return (
        "| Command | What it does |\n"
        "|---|---|\n"
        "| `add job:` | Creates a job spec from conversation |\n"
        "| `show job queue:` | Shows jobs table |\n"
        "| `run job queue:` | Executes highest-priority job |\n"
        "| `build essence:` | Starts essence builder interview |\n"
        "| `my commands:` | Shows this reference |"
    )


def cron_jobs_markdown(crontab_stdout: str) -> str:
    lines = [
        line for line in crontab_stdout.strip().split("\n")
        if line.strip() and not line.startswith("#")
    ]
    if not lines:
        return "No active cron jobs."
    return "```\n" + "\n".join(lines) + "\n```"


def _load_job_queue_helpers() -> tuple[Callable[[], Any], Callable[[Any], str]]:
    from agent_skills.show_job_queue import format_markdown_table, get_job_queue_data

    return get_job_queue_data, format_markdown_table


def _load_completed_jobs_helpers() -> tuple[Callable[[], Any], Callable[[Any], str]]:
    from agent_skills.show_job_queue import format_markdown_table, get_completed_jobs_data

    return get_completed_jobs_data, format_markdown_table


def _crontab_stdout() -> str:
    import subprocess

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
    return result.stdout


def _table_command_response(
    helpers: Callable[[], tuple[Callable[[], Any], Callable[[Any], str]]],
    *,
    empty_message: str,
    error_message: str,
) -> str:
    try:
        load_data, format_table = helpers()
        return format_table(load_data()) or empty_message
    except Exception:
        return error_message


def instant_command_response(
    message: str,
    *,
    job_queue_helpers: Callable[[], tuple[Callable[[], Any], Callable[[Any], str]]] = (
        _load_job_queue_helpers
    ),
    completed_jobs_helpers: Callable[[], tuple[Callable[[], Any], Callable[[Any], str]]] = (
        _load_completed_jobs_helpers
    ),
    crontab_stdout: Callable[[], str] = _crontab_stdout,
) -> str | None:
    kind = instant_command_kind(message)
    if kind == "job_queue":
        return _table_command_response(
            job_queue_helpers,
            empty_message="Job queue is empty.",
            error_message="Could not load job queue.",
        )

    if kind == "completed_jobs":
        return _table_command_response(
            completed_jobs_helpers,
            empty_message="No completed jobs.",
            error_message="Could not load completed jobs.",
        )

    if kind == "commands":
        return commands_markdown()

    if kind == "cron":
        try:
            return cron_jobs_markdown(crontab_stdout())
        except Exception:
            return "Could not load cron jobs."

    return None
