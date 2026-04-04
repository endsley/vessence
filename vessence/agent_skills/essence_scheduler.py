#!/usr/bin/env python3
"""
Essence Scheduler — Runs scheduled jobs declared in essence cron/jobs.json files.

Replaces per-essence crontab entries. A single cron entry runs this every minute:
    * * * * * python essence_scheduler.py

Each loaded essence can declare scheduled tasks in cron/jobs.json:
    [{"schedule": "0 */8 * * *", "script": "functions/run_briefing.py", "idle_only": true}]
"""

import json
import os
import subprocess
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import LOGS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [essence_scheduler] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(os.path.join(LOGS_DIR, "essence_scheduler.log"))],
)
logger = logging.getLogger("essence_scheduler")

TOOLS_DIR = os.environ.get("TOOLS_DIR",
                           os.environ.get("ESSENCES_DIR",
                                          os.path.join(os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient")), "tools")))
STATE_FILE = os.path.join(os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")), "data", "essence_scheduler_state.json")
PYTHON_BIN = os.environ.get("PYTHON_BIN", sys.executable)
IDLE_THRESHOLD_SECONDS = 900


def _load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    # Atomic write to prevent corruption if interrupted mid-write
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, STATE_FILE)


def _is_user_idle() -> bool:
    logs_dir = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
    indicators = [
        os.path.join(logs_dir, "logs", "jane_request_timing.log"),
        os.path.join(logs_dir, "logs", "jane_web.log"),
    ]
    now = time.time()
    for path in indicators:
        if os.path.exists(path):
            if now - os.path.getmtime(path) < IDLE_THRESHOLD_SECONDS:
                return False
    return True


def _matches_schedule(schedule: str, now: datetime) -> bool:
    """Simple cron schedule matcher for: minute hour dom month dow."""
    parts = schedule.strip().split()
    if len(parts) != 5:
        return False

    fields = [now.minute, now.hour, now.day, now.month, now.weekday()]
    # weekday: cron uses 0=Sun, Python uses 0=Mon
    fields[4] = (fields[4] + 1) % 7  # Convert to cron format

    for field_val, pattern in zip(fields, parts):
        if pattern == "*":
            continue
        if "/" in pattern:
            base, step = pattern.split("/")
            base = 0 if base == "*" else int(base)
            if (field_val - base) % int(step) != 0:
                return False
        elif "," in pattern:
            if field_val not in [int(x) for x in pattern.split(",")]:
                return False
        elif "-" in pattern:
            lo, hi = pattern.split("-")
            if not (int(lo) <= field_val <= int(hi)):
                return False
        else:
            if field_val != int(pattern):
                return False
    return True


def run_scheduler():
    # Load gate: wait until CPU/memory is acceptable
    try:
        from agent_skills.system_load import wait_until_safe
        if not wait_until_safe(max_wait_minutes=5):
            return
    except Exception:
        pass

    if not os.path.isdir(TOOLS_DIR):
        return

    now = datetime.now(timezone.utc)
    state = _load_state()
    changed = False

    for essence_name in sorted(os.listdir(TOOLS_DIR)):
        jobs_file = os.path.join(TOOLS_DIR, essence_name, "cron", "jobs.json")
        if not os.path.isfile(jobs_file):
            continue

        try:
            with open(jobs_file) as f:
                jobs = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        for i, job in enumerate(jobs):
            schedule = job.get("schedule", "")
            script = job.get("script", "")
            idle_only = job.get("idle_only", False)
            job_key = f"{essence_name}:{i}:{script}"

            if not schedule or not script:
                continue

            if not _matches_schedule(schedule, now):
                continue

            # Check if already ran this minute
            last_run = state.get(job_key, "")
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            if last_run == current_minute:
                continue

            # Idle gate
            if idle_only and not _is_user_idle():
                logger.info(f"Skipping {job_key}: user is active (idle_only=true)")
                continue

            # Execute
            script_path = os.path.join(TOOLS_DIR, essence_name, script)
            if not os.path.isfile(script_path):
                logger.warning(f"Script not found: {script_path}")
                continue

            logger.info(f"Running: {job_key}")
            try:
                result = subprocess.run(
                    [PYTHON_BIN, script_path],
                    capture_output=True, text=True,
                    timeout=600,
                    cwd=os.path.dirname(script_path),
                )
                if result.returncode == 0:
                    logger.info(f"Completed: {job_key}")
                else:
                    logger.error(f"Failed: {job_key} (exit {result.returncode}): {result.stderr[:200]}")
            except subprocess.TimeoutExpired:
                logger.error(f"Timeout: {job_key}")
            except Exception as e:
                logger.error(f"Error: {job_key}: {e}")

            state[job_key] = current_minute
            changed = True

    if changed:
        _save_state(state)


if __name__ == "__main__":
    run_scheduler()
