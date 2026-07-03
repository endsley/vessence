"""Pure display helpers for show_job_queue.py."""
from __future__ import annotations

import re


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


def parse_job_file_content(content: str, fname: str) -> dict:
    """Parse one job Markdown document into display-row data."""
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

    return {
        "num": fname.split("_")[0],
        "file": fname,
        "name": name,
        "status": status,
        "status_icon": STATUS_ICON.get(status.lower(), "❓"),
        "priority": priority,
        "priority_label": PRIORITY_LABEL.get(priority.lower(), priority),
        "summary": summary,
        "result": result,
    }


def format_markdown_table_data(data: dict, default_columns: list[str]) -> str:
    """Return a Markdown table for already-loaded queue data."""
    jobs = data.get("jobs", [])
    if not jobs:
        return "Job queue is empty."
    columns = data.get("columns", default_columns)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = []
    for job in jobs:
        cells = {
            "#": job["num"],
            "Job": job["name"],
            "Summary": job.get("summary") or "—",
            "Status": f'{job.get("status_icon", "")} {job["status"]}',
            "Result": job.get("result") or "—",
        }
        row = "| " + " | ".join(str(cells.get(column, "—")) for column in columns) + " |"
        rows.append(row)
    plural = "s" if data["count"] != 1 else ""
    return f"**Job Queue: {data['count']} job{plural}**\n\n{header}\n{separator}\n" + "\n".join(rows)
