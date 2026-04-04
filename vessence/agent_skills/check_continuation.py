#!/usr/bin/env python3
"""
check_continuation.py — Should Jane self-continue to the next job?

Returns JSON: {"should_continue": bool, "prompt_index": int|null, "prompt_text": str|null, "reason": str}

Conditions (ALL must be true):
  1. The user is idle (>5 min since last activity per idle_state.json)
  2. No items in active_queue.json (absent = empty queue)
  3. There is a pending job in configs/job_queue/
"""

import json
import time
import os
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import (
    ACTIVE_QUEUE_PATH,
    IDLE_STATE_PATH,
    VESSENCE_HOME,
)

ACTIVE_QUEUE_FILE = ACTIVE_QUEUE_PATH
IDLE_STATE_FILE = IDLE_STATE_PATH
IDLE_THRESHOLD = 300  # 5 minutes in seconds
JOBS_DIR = os.path.join(VESSENCE_HOME, "configs", "job_queue")

PRIORITY_MAP = {"high": 1, "1": 1, "medium": 2, "2": 2, "low": 3, "3": 3}


def get_next_pending_job():
    """Returns (job_num, title) of highest-priority pending job, or (None, None)."""
    if not os.path.isdir(JOBS_DIR):
        return None, None

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
            jobs.append((priority, job_num, title))
        except Exception:
            continue

    if not jobs:
        return None, None

    jobs.sort()
    _, job_num, title = jobs[0]
    return job_num, title


def queue_is_empty():
    try:
        with open(ACTIVE_QUEUE_FILE) as f:
            q = json.load(f)
        return len(q.get("items", [])) == 0
    except (FileNotFoundError, json.JSONDecodeError):
        return True


def is_user_idle():
    try:
        with open(IDLE_STATE_FILE) as f:
            state = json.load(f)
        last_ts = state.get("last_active_ts", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        last_ts = 0
    elapsed = time.time() - last_ts if last_ts else 999999
    return elapsed >= IDLE_THRESHOLD


def main():
    if not queue_is_empty():
        print(json.dumps({
            "should_continue": False, "prompt_index": None,
            "prompt_text": None, "reason": "Active queue not empty"
        }))
        return

    job_num, title = get_next_pending_job()
    if job_num is None:
        print(json.dumps({
            "should_continue": False, "prompt_index": None,
            "prompt_text": None, "reason": "No pending jobs"
        }))
        return

    if not is_user_idle():
        print(json.dumps({
            "should_continue": False, "prompt_index": None,
            "prompt_text": None, "reason": "user is active"
        }))
        return

    print(json.dumps({
        "should_continue": True,
        "prompt_index": job_num,
        "prompt_text": f"[new]\nrun job queue:",
        "reason": "All conditions met"
    }))


if __name__ == "__main__":
    main()
