#!/usr/bin/env python3
"""show_job_queue.py — Display the job queue as a formatted table."""

import os
import re
import sys

QUEUE_DIR = os.path.join(
    os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence")),
    "configs", "job_queue"
)


def load_jobs() -> list[dict]:
    jobs = []
    if not os.path.isdir(QUEUE_DIR):
        return jobs
    for fname in sorted(os.listdir(QUEUE_DIR)):
        if not fname.endswith(".md") or fname == "README.md" or fname.startswith("completed"):
            continue
        fpath = os.path.join(QUEUE_DIR, fname)
        try:
            with open(fpath) as f:
                content = f.read()
        except Exception:
            continue

        name_match = re.search(r"^# Job:\s*(.+)", content, re.MULTILINE)
        status_match = re.search(r"^Status:\s*(.+)", content, re.MULTILINE)
        priority_match = re.search(r"^Priority:\s*(.+)", content, re.MULTILINE)
        objective_match = re.search(r"^## Objective\s*\n(.+)", content, re.MULTILINE)
        result_match = re.search(r"^## Result\s*\n(.+)", content, re.MULTILINE)

        name = name_match.group(1).strip() if name_match else fname
        status = status_match.group(1).strip().split("\n")[0] if status_match else "unknown"
        priority = priority_match.group(1).strip() if priority_match else "?"

        # Summary: first sentence of ## Objective, capped at 80 chars
        summary = ""
        if objective_match:
            raw = objective_match.group(1).strip()
            dot = raw.find(".")
            summary = raw[: dot + 1] if dot != -1 else raw
            if len(summary) > 80:
                summary = summary[:77] + "..."

        # Result: first line of ## Result section, or "—"
        result = "\u2014"
        if "complete" in status and result_match:
            result = result_match.group(1).strip()

        jobs.append({
            "file": fname,
            "name": name,
            "status": status,
            "priority": priority,
            "summary": summary,
            "result": result,
        })
    return jobs


PRIORITY_LABEL = {
    "high": "🔴 High", "1": "🔴 High",
    "medium": "🟡 Medium", "2": "🟡 Medium",
    "low": "🟢 Low", "3": "🟢 Low",
}

PRIORITY_SORT = {"high": 0, "1": 0, "medium": 1, "2": 1, "low": 2, "3": 2}


def format_table(jobs: list[dict]) -> str:
    pending = [j for j in jobs if "complete" not in j["status"]]
    completed = [j for j in jobs if "complete" in j["status"]]

    parts = []

    if pending:
        rows = ""
        for j in sorted(pending, key=lambda x: PRIORITY_SORT.get(x["priority"].lower(), 3)):
            num = j["file"].split("_")[0]
            pri = PRIORITY_LABEL.get(j["priority"].lower(), j["priority"])
            summary = j.get("summary", "\u2014")
            rows += f"<tr><td style='border: 2px solid #333; padding: 8px;'>{num}</td><td style='border: 2px solid #333; padding: 8px;'>{pri}</td><td style='border: 2px solid #333; padding: 8px;'>{j['name']}</td><td style='border: 2px solid #333; padding: 8px;'>{summary}</td></tr>"
        parts.append(
            f"<b>Pending: {len(pending)} job{'s' if len(pending) != 1 else ''}</b>"
            f"<table style='border: 2px solid #333; border-collapse: collapse;'><tr><th style='border: 2px solid #333; padding: 8px;'>#</th><th style='border: 2px solid #333; padding: 8px;'>Priority</th><th style='border: 2px solid #333; padding: 8px;'>Job</th><th style='border: 2px solid #333; padding: 8px;'>Summary</th></tr>{rows}</table>"
        )

    if completed:
        rows = ""
        for j in sorted(completed, key=lambda x: x["file"]):
            num = j["file"].split("_")[0]
            summary = j.get("summary", "\u2014")
            rows += f"<tr><td style='border: 2px solid #333; padding: 8px;'>{num}</td><td style='border: 2px solid #333; padding: 8px;'>{j['name']}</td><td style='border: 2px solid #333; padding: 8px;'>{summary}</td></tr>"
        parts.append(
            f"<b>Completed: {len(completed)} job{'s' if len(completed) != 1 else ''}</b>"
            f"<table style='border: 2px solid #333; border-collapse: collapse;'><tr><th style='border: 2px solid #333; padding: 8px;'>#</th><th style='border: 2px solid #333; padding: 8px;'>Job</th><th style='border: 2px solid #333; padding: 8px;'>Summary</th></tr>{rows}</table>"
        )

    if not parts:
        return "Job queue is empty."

    return "\n".join(parts)


def main():
    jobs = load_jobs()
    print(format_table(jobs))


if __name__ == "__main__":
    main()
