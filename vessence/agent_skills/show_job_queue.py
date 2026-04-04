#!/usr/bin/env python3
"""show_job_queue.py — Load and return the job queue as structured data."""

import json
import os
import re
import sys

VESSENCE_HOME = os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence"))
QUEUE_DIR = os.path.join(VESSENCE_HOME, "configs", "job_queue")
SYSTEM_DEFAULTS_PATH = os.path.join(VESSENCE_HOME, "configs", "system_functional_defaults.json")
DEFAULT_JOB_QUEUE_COLUMNS = ["#", "Job", "Summary", "Status", "Result"]

PRIORITY_LABEL = {
    "high": "🔴 High", "1": "🔴 High",
    "medium": "🟡 Medium", "2": "🟡 Medium",
    "low": "🟢 Low", "3": "🟢 Low",
}

PRIORITY_SORT = {"high": 0, "1": 0, "medium": 1, "2": 1, "low": 2, "3": 2}

STATUS_ICON = {
    "pending": "⏳",
    "in_progress": "🔄",
    "completed": "✅",
    "blocked": "🚫",
}


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

    name_match = re.search(r"^# Job:\s*(.+)", content, re.MULTILINE)
    status_match = re.search(r"^Status:\s*(.+)", content, re.MULTILINE)
    priority_match = re.search(r"^Priority:\s*(.+)", content, re.MULTILINE)
    objective_match = re.search(r"^## Objective\s*\n(.+)", content, re.MULTILINE)
    result_match = re.search(r"^## Result\s*\n(.+)", content, re.MULTILINE)

    name = name_match.group(1).strip() if name_match else fname
    status = status_match.group(1).strip().split("\n")[0] if status_match else "unknown"
    priority = priority_match.group(1).strip() if priority_match else "?"

    summary = ""
    if objective_match:
        raw = objective_match.group(1).strip()
        dot = raw.find(".")
        summary = raw[: dot + 1] if dot != -1 else raw
        if len(summary) > 80:
            summary = summary[:77] + "..."

    result = "—"
    if "complete" in status and result_match:
        result = result_match.group(1).strip()
    elif "complete" not in status:
        result = "Awaiting execution"

    num = fname.split("_")[0]

    return {
        "num": num,
        "file": fname,
        "name": name,
        "status": status,
        "status_icon": STATUS_ICON.get(status.lower(), "❓"),
        "priority": priority,
        "priority_label": PRIORITY_LABEL.get(priority.lower(), priority),
        "summary": summary,
        "result": result,
    }


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
    jobs = data.get("jobs", [])
    if not jobs:
        return "Job queue is empty."
    cols = data.get("columns", DEFAULT_JOB_QUEUE_COLUMNS)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = []
    for j in jobs:
        cells = {
            "#": j["num"],
            "Job": j["name"],
            "Summary": j.get("summary") or "\u2014",
            "Status": f'{j.get("status_icon", "")} {j["status"]}',
            "Result": j.get("result") or "\u2014",
        }
        row = "| " + " | ".join(str(cells.get(c, "\u2014")) for c in cols) + " |"
        rows.append(row)
    return f"**Job Queue: {data['count']} job{'s' if data['count'] != 1 else ''}**\n\n{header}\n{sep}\n" + "\n".join(rows)


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
