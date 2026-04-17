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
import json
import time
import re
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
    most_recent_ts = 0

    for path in [USER_STATE_PATH, IDLE_STATE_PATH]:
        try:
            with open(path) as f:
                state = json.load(f)
            ts = state.get("last_message_ts", 0) or state.get("last_active_ts", 0)
            if ts > most_recent_ts:
                most_recent_ts = ts
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if most_recent_ts == 0:
        return True
    idle_secs = now - most_recent_ts
    logger.info(f"Idle check: {idle_secs:.0f}s since last activity (threshold: {IDLE_THRESHOLD}s)")
    return idle_secs >= IDLE_THRESHOLD


# ── Job file parsing ────────────────────────────────────────────────────────────
PRIORITY_MAP = {"high": 1, "1": 1, "medium": 2, "2": 2, "low": 3, "3": 3}


def _parse_job(fpath: str) -> dict:
    with open(fpath) as f:
        content = f.read()
    title_m = re.search(r"^# Job:\s*(.+)", content, re.MULTILINE)
    status_m = re.search(r"^Status:\s*(.+)", content, re.MULTILINE)
    priority_m = re.search(r"^Priority:\s*(.+)", content, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else Path(fpath).stem
    status = status_m.group(1).strip().split()[0].lower() if status_m else "unknown"
    priority_raw = priority_m.group(1).strip().lower() if priority_m else "3"
    priority = PRIORITY_MAP.get(priority_raw, 3)
    return {"file": fpath, "title": title, "status": status, "priority": priority, "content": content}


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
    content = re.sub(r"^Status:\s*.+", f"Status: {new_status}", content, count=1, flags=re.MULTILINE)
    if result_summary:
        if "## Result" in content:
            content = re.sub(r"## Result\s*\n.*", f"## Result\n{result_summary}", content, count=1, flags=re.DOTALL)
        else:
            content = content.rstrip() + f"\n\n## Result\n{result_summary}\n"
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
SELF_CONTINUATION_INSTRUCTION = (
    "\n\n## Self-Continuation\n"
    "At the end of EVERY response, run:\n"
    "```bash\n"
    "/home/chieh/google-adk-env/adk-venv/bin/python "
    "$VESSENCE_HOME/agent_skills/check_continuation.py\n"
    "```\n"
    "If `should_continue` is true: display "
    "`**[Auto-continuing → Job #N]:** [text]` and execute `run job queue:`. "
    "Repeat until false. If false, stop silently."
)


def build_prompt(job: dict) -> str:
    content = job["content"]
    # Extract key sections: Objective, Context, Steps
    sections = ["Objective", "Context", "Steps", "Verification", "Files Involved", "Notes"]
    prompt_parts = [f"# Task: {job['title']}", ""]
    for section in sections:
        m = re.search(rf"^## {section}\s*\n(.*?)(?=^## |\Z)", content, re.MULTILINE | re.DOTALL)
        if m:
            body = m.group(1).strip()
            if body:
                prompt_parts.append(f"## {section}")
                prompt_parts.append(body)
                prompt_parts.append("")
    prompt_text = "\n".join(prompt_parts).strip()
    # Inject self-continuation so the CLI automation agent can chain jobs
    prompt_text += SELF_CONTINUATION_INSTRUCTION
    return prompt_text


# ── Run via Jane web API ─────────────────────────────────────────────────────────
def run_job(job: dict) -> tuple[str, bool]:
    prompt_text = build_prompt(job)
    short_desc = job["title"]

    _announcements_path = os.path.join(
        os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")),
        "data", "jane_announcements.jsonl"
    )
    _progress_id = f"job_{int(time.time()*1000)}"

    def _push_announcement(msg_text: str, is_final: bool = False):
        try:
            entry = json.dumps({
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "queue_progress",
                "id": _progress_id,
                "message": msg_text,
                "final": is_final,
            })
            with open(_announcements_path, "a") as f:
                f.write(entry + "\n")
        except Exception:
            pass

    _push_announcement(f"**Working on job:** {short_desc}")
    logger.info(f"Running job: {short_desc}")

    jane_url = os.environ.get("JANE_WEB_URL", "http://localhost:8081")
    api_url = f"{jane_url}/api/jane/chat/stream"

    try:
        resp = requests.post(
            api_url,
            json={
                "message": prompt_text,
                "session_id": "job_queue_session",
                "platform": "queue",
            },
            stream=True,
            timeout=(10, None),
        )
        if resp.status_code == 401:
            resp = requests.post(
                f"{jane_url}/api/jane/chat",
                json={
                    "message": prompt_text,
                    "session_id": "job_queue_session",
                    "platform": "queue",
                },
                timeout=(10, 600),
            )
            if resp.ok:
                data = resp.json()
                result = data.get("text", "")
                _push_announcement(f"**Completed job:** {short_desc}", is_final=True)
                return result, bool(result)
            else:
                _push_announcement(f"**Failed:** HTTP {resp.status_code}", is_final=True)
                return f"Error: HTTP {resp.status_code}", False

        response_text = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "delta":
                response_text += event.get("data", "")
            elif event.get("type") == "done":
                if not response_text:
                    response_text = event.get("data", "")
                break
            elif event.get("type") == "error":
                err = event.get("data", "Unknown error")
                _push_announcement(f"**Failed:** {err[:100]}", is_final=True)
                return f"Error: {err}", False

        try:
            from agent_skills.work_log_tools import log_activity
            snippet = (response_text or "")[:150].replace("\n", " ").strip()
            log_activity(f"Job completed: {short_desc} → {snippet}", category="job_completed")
        except Exception:
            pass

        _push_announcement(f"**Completed job:** {short_desc}", is_final=True)
        return response_text, bool(response_text.strip())

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
    job_num = Path(job["file"]).stem.split("_")[0]
    fact = (
        f"Job #{job_num} completed autonomously on {date_str}. "
        f"Title: {job['title']}. "
        f"Result: {result[:300]}{'...' if len(result) > 300 else ''}"
    )
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
    text = text.strip()
    # Use first line (up to 60 chars) as the short name
    first_line = text.splitlines()[0][:60].strip()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", first_line.lower())[:40].strip("_")
    if not safe_name:
        safe_name = "task"

    # Find next job number
    existing = [f for f in os.listdir(JOBS_DIR) if f.endswith(".md") and f != "README.md" and not os.path.isdir(os.path.join(JOBS_DIR, f))]
    nums = []
    for f in existing:
        m = re.match(r"^(\d+)", f)
        if m:
            nums.append(int(m.group(1)))
    next_num = max(nums, default=0) + 1

    fname = f"{next_num:02d}_{safe_name}.md"
    fpath = os.path.join(JOBS_DIR, fname)
    today = datetime.date.today().isoformat()

    content = f"""# Job: {first_line}
Status: pending
Priority: medium
Created: {today}

## Objective
{text}

## Context
Added via `prompt:` / `add job:` command.

## Steps
1. Complete the task described in the Objective.

## Verification
Verify the objective is met.
"""
    with open(fpath, "w") as f:
        f.write(content)
    logger.info(f"Created job: {fname}")
    print(f"Added to job queue as #{next_num}: {first_line[:60]}{'...' if len(first_line) > 60 else ''}")
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
