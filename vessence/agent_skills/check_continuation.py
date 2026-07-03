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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skills.job_queue_docs import (
    PRIORITY_MAP,
    pending_job_summaries_from_dir as _pending_job_summaries_from_dir,
    pending_job_summary as _pending_job_summary,
    sort_pending_job_summaries as _sort_pending_job_summaries,
)
from agent_skills.continuation_policy import (
    active_queue_not_empty_result as _active_queue_not_empty_result,
    continue_job_result as _continue_job_result,
    idle_state_is_idle as _idle_state_is_idle,
    no_pending_jobs_result as _no_pending_jobs_result,
    queue_payload_is_empty as _queue_payload_is_empty,
    user_active_result as _user_active_result,
)
from jane.config import (
    ACTIVE_QUEUE_PATH,
    IDLE_STATE_PATH,
    VESSENCE_HOME,
)

ACTIVE_QUEUE_FILE = ACTIVE_QUEUE_PATH
IDLE_STATE_FILE = IDLE_STATE_PATH
IDLE_THRESHOLD = 300  # 5 minutes in seconds
JOBS_DIR = os.path.join(VESSENCE_HOME, "configs", "job_queue")


def get_next_pending_job():
    """Returns (job_num, title) of highest-priority pending job, or (None, None)."""
    jobs = _pending_job_summaries_from_dir(JOBS_DIR)
    if not jobs:
        return None, None
    first = jobs[0]
    return first["num"], first["title"]


def queue_is_empty():
    try:
        with open(ACTIVE_QUEUE_FILE) as f:
            q = json.load(f)
        return _queue_payload_is_empty(q)
    except (FileNotFoundError, json.JSONDecodeError):
        return True


def is_user_idle():
    try:
        with open(IDLE_STATE_FILE) as f:
            state = json.load(f)
        last_ts = state.get("last_active_ts", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        last_ts = 0
    return _idle_state_is_idle(
        {"last_active_ts": last_ts},
        now=time.time(),
        threshold_seconds=IDLE_THRESHOLD,
    )


def main():
    if not queue_is_empty():
        print(json.dumps(_active_queue_not_empty_result()))
        return

    job_num, title = get_next_pending_job()
    if job_num is None:
        print(json.dumps(_no_pending_jobs_result()))
        return

    if not is_user_idle():
        print(json.dumps(_user_active_result()))
        return

    print(json.dumps(_continue_job_result(job_num)))


if __name__ == "__main__":
    main()
