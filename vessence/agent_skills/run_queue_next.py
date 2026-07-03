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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skills.job_queue_docs import (
    PRIORITY_MAP,
    pending_job_summaries_from_dir as _pending_job_summaries_from_dir,
    pending_job_summary as _pending_job_summary,
    sort_pending_job_summaries as _sort_pending_job_summaries,
)
from jane.config import VESSENCE_HOME

JOBS_DIR = os.path.join(VESSENCE_HOME, "configs", "job_queue")


def get_pending_jobs() -> list[dict]:
    """Returns list of pending jobs sorted by priority."""
    return _pending_job_summaries_from_dir(JOBS_DIR)


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
