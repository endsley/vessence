#!/usr/bin/env python3
"""
run_queue_next.py — Get the next pending job from the job queue.

Used by Jane's `run job queue:` command to drive explicit queue execution.
Unlike check_continuation.py, this never checks idle state — it always
returns the next pending job if one exists.

Returns JSON:
  {"has_next": true,  "prompt_index": N, "prompt_text": "...", "remaining": M}
  {"has_next": false, "prompt_index": null, "prompt_text": null, "remaining": 0}
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import VESSENCE_HOME

JOBS_DIR = os.path.join(VESSENCE_HOME, "configs", "job_queue")
PRIORITY_MAP = {"high": 1, "1": 1, "medium": 2, "2": 2, "low": 3, "3": 3}


def get_pending_jobs() -> list[dict]:
    """Returns list of pending jobs sorted by priority."""
    if not os.path.isdir(JOBS_DIR):
        return []
    jobs = []
    for fname in sorted(os.listdir(JOBS_DIR)):
        if not fname.endswith(".md") or fname == "README.md":
            continue
        fpath = os.path.join(JOBS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath) as f:
                content = f.read()
            status_m = re.search(r"^Status:\s*(.+)", content, re.MULTILINE)
            if not status_m or status_m.group(1).strip().split()[0].lower() != "pending":
                continue
            title_m = re.search(r"^# Job:\s*(.+)", content, re.MULTILINE)
            priority_m = re.search(r"^Priority:\s*(.+)", content, re.MULTILINE)
            title = title_m.group(1).strip() if title_m else fname
            priority_raw = priority_m.group(1).strip().lower() if priority_m else "3"
            priority = PRIORITY_MAP.get(priority_raw, 3)
            num_m = re.match(r"^(\d+)", fname)
            job_num = int(num_m.group(1)) if num_m else 999
            jobs.append({"num": job_num, "title": title, "priority": priority, "file": fpath})
        except Exception:
            continue
    jobs.sort(key=lambda j: (j["priority"], j["num"]))
    return jobs


def main():
    jobs = get_pending_jobs()

    if not jobs:
        print(json.dumps({
            "has_next": False,
            "prompt_index": None,
            "prompt_text": None,
            "remaining": 0,
        }))
        return

    first = jobs[0]
    print(json.dumps({
        "has_next": True,
        "prompt_index": first["num"],
        "prompt_text": f"[new]\nJob #{first['num']}: {first['title']}",
        "remaining": len(jobs),
    }))


if __name__ == "__main__":
    main()
