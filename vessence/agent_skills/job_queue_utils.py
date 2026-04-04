#!/usr/bin/env python3
"""
job_queue_utils.py — Job queue management utilities.

Auto-archives completed jobs when the count exceeds a threshold.
Can be called after marking a job complete, or via cron.
"""

import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger("job_queue")

JOBS_DIR = os.path.join(
    os.environ.get("VESSENCE_HOME", os.path.join(str(Path.home()), "ambient", "vessence")),
    "configs", "job_queue",
)
COMPLETED_DIR = os.path.join(JOBS_DIR, "completed")
ARCHIVE_THRESHOLD = 10  # Archive when completed count exceeds this


def list_jobs() -> list[dict]:
    """List all jobs with their status."""
    jobs = []
    for fname in sorted(os.listdir(JOBS_DIR)):
        if not fname.endswith(".md") or fname == "README.md":
            continue
        fpath = os.path.join(JOBS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        status = "unknown"
        title = fname
        priority = 5
        with open(fpath, "r") as f:
            for line in f:
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
        jobs.append({"file": fname, "path": fpath, "title": title, "status": status, "priority": priority})
    return jobs


def archive_completed(threshold: int = ARCHIVE_THRESHOLD) -> int:
    """
    Move completed job files to completed/ subdirectory when the count exceeds threshold.
    Returns the number of jobs archived.
    """
    jobs = list_jobs()
    completed = [j for j in jobs if j["status"].startswith("complete")]

    if len(completed) <= threshold:
        return 0

    os.makedirs(COMPLETED_DIR, exist_ok=True)
    archived = 0
    for job in completed:
        src = job["path"]
        dst = os.path.join(COMPLETED_DIR, job["file"])
        try:
            shutil.move(src, dst)
            logger.info(f"Archived: {job['file']}")
            archived += 1
        except Exception as e:
            logger.warning(f"Failed to archive {job['file']}: {e}")

    if archived:
        logger.info(f"Archived {archived} completed jobs (threshold: {threshold})")
    return archived


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if "--list" in sys.argv:
        for j in list_jobs():
            print(f"  [{j['status']}] P{j['priority']} — {j['title']}")
    else:
        n = archive_completed()
        if n:
            print(f"Archived {n} completed jobs.")
        else:
            print(f"No archiving needed (completed jobs <= {ARCHIVE_THRESHOLD}).")
