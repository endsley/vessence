"""Pure helpers for job_queue_utils.py."""

from __future__ import annotations


def parse_job_listing(content: str, fname: str, fpath: str) -> dict:
    status = "unknown"
    title = fname
    priority = 5
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# Job:"):
            title = line[7:].strip()
        elif line.startswith("Status:"):
            status = line[7:].strip().split()[0].lower()
        elif line.startswith("Priority:"):
            try:
                priority = int(line[9:].strip().split()[0])
            except ValueError:
                pass
    return {
        "file": fname,
        "path": fpath,
        "title": title,
        "status": status,
        "priority": priority,
    }


def completed_jobs_to_archive(jobs: list[dict], threshold: int) -> list[dict]:
    completed = [job for job in jobs if job["status"].startswith("complete")]
    if len(completed) <= threshold:
        return []
    return completed
