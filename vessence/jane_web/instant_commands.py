"""Instant chat command classification and formatting helpers."""

from __future__ import annotations


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
