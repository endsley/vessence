#!/usr/bin/env python3
"""
job_queue_runner.py — Autonomous job queue processor.

Reads configs/job_queue/, finds the highest-priority pending job,
runs it via the Jane web API, marks it complete/incomplete, and logs to memory.

Checks idle state before running — stops if user becomes active.

Usage:
    job_queue_runner.py
    job_queue_runner.py --force   # skip idle check (for testing)
    job_queue_runner.py --add "task text"  # create a minimal job from text
"""

import os
import sys
import time
import argparse
import datetime
import logging
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from jane.config import ENV_FILE_PATH
load_dotenv(ENV_FILE_PATH)

from jane.config import (
    VESSENCE_HOME,
    USER_STATE_PATH, IDLE_STATE_PATH,
    IDLE_THRESHOLD_SECS as IDLE_THRESHOLD,
    ADD_FACT_SCRIPT as ADD_FACT,
    JOB_QUEUE_LOG, LOGS_DIR,
    QUEUE_PAUSE_BETWEEN_SECS,
)
from agent_skills.job_queue_docs import (
    PRIORITY_MAP,
    SELF_CONTINUATION_INSTRUCTION,
    build_prompt as _build_prompt_doc,
    parse_job_content as _parse_job_content,
    set_status_content as _set_status_content,
)
from agent_skills.job_queue_creation import (
    build_job_creation_draft as _build_job_creation_draft,
    job_safe_name as _job_safe_name,
    minimal_job_content as _minimal_job_content,
    next_job_number as _next_job_number,
)
from agent_skills.queue_progress_announcements import (
    append_queue_progress_announcement as _append_queue_progress_announcement,
    queue_announcements_path as _queue_announcements_path,
    queue_progress_id as _queue_progress_id,
    queue_progress_json_line as _queue_progress_json_line,
)
from agent_skills.queue_jane_api import (
    parse_queue_stream_lines as _parse_queue_stream_lines,
    queue_chat_payload as _queue_chat_payload,
    run_queue_chat_request as _run_queue_chat_request,
)
from agent_skills.job_queue_memory import (
    job_completion_fact as _job_completion_fact,
    job_number_from_file as _job_number_from_file,
)
from agent_skills.prompt_queue_idle import (
    is_idle_from_timestamp as _is_idle_from_timestamp,
    most_recent_activity_timestamp_any as _most_recent_activity_timestamp_any,
    read_activity_timestamp_any as _read_activity_timestamp_any,
)

JOBS_DIR = os.path.join(VESSENCE_HOME, "configs", "job_queue")
COMPLETED_DIR = os.path.join(JOBS_DIR, "completed")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [job_runner] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(JOB_QUEUE_LOG)],
)
logger = logging.getLogger("job_queue_runner")


# ── Idle check ─────────────────────────────────────────────────────────────────
def is_idle() -> bool:
    now = time.time()
    most_recent_ts = _most_recent_activity_timestamp_any(
        (
            (USER_STATE_PATH, ("last_message_ts", "last_active_ts")),
            (IDLE_STATE_PATH, ("last_message_ts", "last_active_ts")),
        ),
        logger=logger,
    )

    if most_recent_ts == 0:
        return True
    idle_secs = now - most_recent_ts
    logger.info(f"Idle check: {idle_secs:.0f}s since last activity (threshold: {IDLE_THRESHOLD}s)")
    return _is_idle_from_timestamp(now, most_recent_ts, IDLE_THRESHOLD)


# ── Job file parsing ────────────────────────────────────────────────────────────
def _parse_job(fpath: str) -> dict:
    with open(fpath) as f:
        content = f.read()
    return _parse_job_content(content, fpath)


def load_pending_jobs() -> list[dict]:
    """Return all pending jobs sorted by priority (1 = highest)."""
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
            job = _parse_job(fpath)
            if job["status"] == "pending":
                jobs.append(job)
        except Exception:
            continue
    jobs.sort(key=lambda j: j["priority"])
    return jobs


def get_next_pending_job() -> dict | None:
    jobs = load_pending_jobs()
    return jobs[0] if jobs else None


# ── Job file mutation ────────────────────────────────────────────────────────────
def _set_status(fpath: str, new_status: str, result_summary: str = ""):
    with open(fpath) as f:
        content = f.read()
    content = _set_status_content(content, new_status, result_summary)
    with open(fpath, "w") as f:
        f.write(content)


def mark_job_complete(job: dict, result_summary: str = ""):
    _set_status(job["file"], "completed", result_summary)
    logger.info(f"Marked complete: {job['title']}")
    # Auto-archive if needed
    try:
        from agent_skills.job_queue_utils import archive_completed
        archive_completed()
    except Exception:
        pass


def mark_job_incomplete(job: dict, result_summary: str = ""):
    _set_status(job["file"], "incomplete", result_summary)
    logger.info(f"Marked incomplete: {job['title']}")


# ── Build prompt from job content ────────────────────────────────────────────────
def build_prompt(job: dict) -> str:
    return _build_prompt_doc(job)


# ── Run via Jane web API ─────────────────────────────────────────────────────────
def run_job(job: dict) -> tuple[str, bool]:
    prompt_text = build_prompt(job)
    short_desc = job["title"]

    _announcements_path = _queue_announcements_path(
        os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")),
    )
    _progress_id = _queue_progress_id("job", int(time.time()*1000))

    def _push_announcement(msg_text: str, is_final: bool = False):
        try:
            _append_queue_progress_announcement(
                _announcements_path,
                _progress_id,
                msg_text,
                is_final,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
        except Exception:
            pass

    _push_announcement(f"**Working on job:** {short_desc}")
    logger.info(f"Running job: {short_desc}")

    jane_url = os.environ.get("JANE_WEB_URL", "http://localhost:8081")

    try:
        stream_result = _run_queue_chat_request(
            jane_url,
            prompt_text,
            "job_queue_session",
            post=requests.post,
        )
        if stream_result.error:
            _push_announcement(f"**Failed:** {stream_result.error[:100]}", is_final=True)
            return stream_result.text, False
        response_text = stream_result.text

        if stream_result.source == "stream":
            try:
                from agent_skills.work_log_tools import log_activity
                snippet = (response_text or "")[:150].replace("\n", " ").strip()
                log_activity(f"Job completed: {short_desc} → {snippet}", category="job_completed")
            except Exception:
                pass

        _push_announcement(f"**Completed job:** {short_desc}", is_final=True)
        return response_text, stream_result.success

    except requests.ConnectionError:
        msg = "Jane web is not running — skipping"
        logger.warning(msg)
        _push_announcement(f"**Skipped:** {msg}", is_final=True)
        return msg, False
    except Exception as e:
        _push_announcement(f"**Failed:** {str(e)[:100]}", is_final=True)
        return f"Error: {e}", False


# ── Memory logging ────────────────────────────────────────────────────────────────
def log_to_memory(job: dict, result: str, success: bool):
    if not success:
        return
    import subprocess
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    job_num = _job_number_from_file(job["file"])
    fact = _job_completion_fact(job_num, job["title"], result, date_str)
    try:
        subprocess.run(
            [sys.executable, ADD_FACT, fact, "--topic", "job_queue",
             "--subtopic", f"job_{job_num}"],
            capture_output=True, timeout=30
        )
    except Exception as e:
        logger.warning(f"Failed to log to memory: {e}")


# ── Add job from text (replaces prompt: command) ────────────────────────────────
def add_job_from_text(text: str) -> str:
    """Create a minimal job file from plain text. Returns the job filename."""
    existing = [f for f in os.listdir(JOBS_DIR) if f.endswith(".md") and f != "README.md" and not os.path.isdir(os.path.join(JOBS_DIR, f))]
    draft = _build_job_creation_draft(text, existing)
    fname = draft.filename
    fpath = os.path.join(JOBS_DIR, fname)
    today = datetime.date.today().isoformat()
    content = _minimal_job_content(draft.first_line, draft.text, today)
    with open(fpath, "w") as f:
        f.write(content)
    logger.info(f"Created job: {fname}")
    print(f"Added to job queue as #{draft.number}: {draft.first_line[:60]}{'...' if len(draft.first_line) > 60 else ''}")
    return fname


# ── Lock ────────────────────────────────────────────────────────────────────────
def _acquire_run_lock():
    import fcntl
    lock_path = os.path.join(LOGS_DIR, "job_queue_runner.lock")
    try:
        lock_fh = open(lock_path, "w")
        fcntl.lockf(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fh
    except (IOError, OSError):
        return None


# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Skip idle check")
    parser.add_argument("--add", type=str, metavar="TEXT", help="Create a job from text")
    args = parser.parse_args()

    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(JOBS_DIR, exist_ok=True)

    if args.add:
        add_job_from_text(args.add)
        return

    lock_fh = _acquire_run_lock()
    if lock_fh is None:
        logger.info("Another job runner is already active — exiting.")
        return

    if not args.force and not is_idle():
        logger.info("User is active — exiting without processing.")
        lock_fh.close()
        return

    jobs = load_pending_jobs()
    if not jobs:
        logger.info("No pending jobs.")
        lock_fh.close()
        return

    for job in jobs:
        if not args.force and not is_idle():
            logger.info("User became active — pausing job queue.")
            lock_fh.close()
            return

        try:
            from agent_skills.system_load import wait_until_safe
            if not wait_until_safe(max_wait_minutes=15, check_interval_seconds=60):
                logger.info("System busy after 15 min — stopping.")
                lock_fh.close()
                return
        except Exception:
            pass

        result, success = run_job(job)
        log_to_memory(job, result, success)

        result_summary = result[:300].replace("\n", " ").strip()
        if success:
            mark_job_complete(job, result_summary)
        else:
            mark_job_incomplete(job, result_summary)

        time.sleep(QUEUE_PAUSE_BETWEEN_SECS)

    logger.info("Job queue run complete.")
    lock_fh.close()


if __name__ == "__main__":
    main()
