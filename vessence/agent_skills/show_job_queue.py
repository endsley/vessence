#!/usr/bin/env python3
"""show_job_queue.py — Load and return the job queue as structured data."""

import json
import os
import sys
from agent_skills.job_queue_view import (
    PRIORITY_LABEL,
    PRIORITY_SORT,
    STATUS_ICON,
    format_markdown_table_data as _format_markdown_table_data,
    parse_job_file_content as _parse_job_file_content,
)

VESSENCE_HOME = os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence"))
QUEUE_DIR = os.path.join(VESSENCE_HOME, "configs", "job_queue")
SYSTEM_DEFAULTS_PATH = os.path.join(VESSENCE_HOME, "configs", "system_functional_defaults.json")
DEFAULT_JOB_QUEUE_COLUMNS = ["#", "Job", "Summary", "Status", "Result"]

def load_job_queue_columns() -> list[str]:
    try:
        with open(SYSTEM_DEFAULTS_PATH) as f:
            payload = json.load(f)
    except Exception:
        return DEFAULT_JOB_QUEUE_COLUMNS

    columns = payload.get("job_queue", {}).get("columns")
    if isinstance(columns, list) and all(isinstance(item, str) for item in columns):
        return columns
    return DEFAULT_JOB_QUEUE_COLUMNS


def load_jobs() -> list[dict]:
    jobs = []
    if not os.path.isdir(QUEUE_DIR):
        return jobs
    for fname in sorted(os.listdir(QUEUE_DIR)):
        if not fname.endswith(".md") or fname == "README.md" or fname.startswith("completed"):
            continue
        parsed = _parse_job_file(os.path.join(QUEUE_DIR, fname), fname)
        if parsed:
            jobs.append(parsed)

    # Sort: incomplete first, then by priority, then by file
    jobs.sort(key=lambda x: (
        "complete" in x["status"].lower(),
        PRIORITY_SORT.get(x["priority"].lower(), 3),
        x["file"],
    ))
    return jobs


def _parse_job_file(fpath: str, fname: str) -> dict | None:
    """Parse a single job .md file and return structured data."""
    try:
        with open(fpath) as f:
            content = f.read()
    except Exception:
        return None

    return _parse_job_file_content(content, fname)


def load_completed_jobs() -> list[dict]:
    """Load jobs from the completed/ subdirectory."""
    completed_dir = os.path.join(QUEUE_DIR, "completed")
    jobs = []
    if not os.path.isdir(completed_dir):
        return jobs
    for fname in sorted(os.listdir(completed_dir)):
        if not fname.endswith(".md") or fname == "README.md":
            continue
        parsed = _parse_job_file(os.path.join(completed_dir, fname), fname)
        if parsed:
            jobs.append(parsed)
    return jobs


def get_job_queue_data() -> dict:
    """Return structured job queue data as a dict."""
    jobs = load_jobs()
    return {
        "columns": load_job_queue_columns(),
        "jobs": jobs,
        "count": len(jobs),
    }


def get_completed_jobs_data() -> dict:
    """Return structured completed jobs data as a dict."""
    jobs = load_completed_jobs()
    return {
        "columns": load_job_queue_columns(),
        "jobs": jobs,
        "count": len(jobs),
    }


def format_markdown_table(data: dict | None = None) -> str:
    """Return the job queue as a markdown table."""
    if data is None:
        data = get_job_queue_data()
    return _format_markdown_table_data(data, DEFAULT_JOB_QUEUE_COLUMNS)


def main():
    completed = "--completed" in sys.argv
    md = "--markdown" in sys.argv or "--md" in sys.argv
    data = get_completed_jobs_data() if completed else get_job_queue_data()
    if md:
        print(format_markdown_table(data))
    else:
        print(json.dumps(data))


if __name__ == "__main__":
    main()
