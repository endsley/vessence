#!/usr/bin/env python3
"""
Enqueue bounded, hourly refactor jobs for Chieh's active codebases.

This script does not run a coding CLI directly. It writes project-specific job
specs into Vessence's existing job queue so the normal queue runner handles
idle checks, provider selection, locking discipline, and result logging.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

from agent_skills.iterative_refactor_helpers import (
    default_scheduler_state as _default_scheduler_state,
    disabled_cron_text as _disabled_cron_text,
    extract_job_number as _extract_job_number,
    job_filename as _job_filename,
    next_job_number as _next_job_number,
    normalize_scheduler_state as _normalize_scheduler_state,
)


VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", "/home/chieh/ambient/vessence"))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data"))
JOBS_DIR = VESSENCE_HOME / "configs" / "job_queue"
COMPLETED_DIR = JOBS_DIR / "completed"
STATE_PATH = VESSENCE_DATA_HOME / "state" / "iterative_refactor_scheduler.json"
LOCK_PATH = VESSENCE_DATA_HOME / "locks" / "iterative_refactor_scheduler.lock"
LOG_PATH = VESSENCE_DATA_HOME / "logs" / "iterative_refactor_scheduler.log"

MAX_ITERATIONS = 5
CRON_MARKER = "JANE_ITERATIVE_PROJECT_REFACTOR_CRON"

PROJECTS = (
    {
        "slug": "waterlily",
        "label": "Waterlily",
        "root": "/home/chieh/code/waterlily",
        "focus": (
            "Waterlily accounting, admin UI, report generation, cache load speed, "
            "route/service boundaries, and readability."
        ),
    },
    {
        "slug": "education",
        "label": "Education / teaching app",
        "root": "/home/chieh/code/chieh_class_v2",
        "focus": (
            "teaching app page load speed, FastAPI/HTMX route structure, data access, "
            "template organization, tests, and readability."
        ),
    },
    {
        "slug": "vessence",
        "label": "Vessence",
        "root": "/home/chieh/ambient/vessence",
        "focus": (
            "Jane/Vessence runtime speed, cron/job infrastructure, memory/context "
            "loading, web routes, agents, tests, and readability."
        ),
    },
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f"{utc_now()} {message}"
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load_state() -> dict:
    if not STATE_PATH.exists():
        return _default_scheduler_state(
            now=utc_now(),
            max_iterations=MAX_ITERATIONS,
            projects=PROJECTS,
        )
    try:
        with STATE_PATH.open(encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, json.JSONDecodeError):
        state = {}
    return _normalize_scheduler_state(
        state,
        now=utc_now(),
        max_iterations=MAX_ITERATIONS,
        projects=PROJECTS,
    )


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(STATE_PATH)


def existing_job_numbers() -> set[int]:
    numbers: set[int] = set()
    for directory in (JOBS_DIR, COMPLETED_DIR):
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            number = _extract_job_number(path.name)
            if number is not None:
                numbers.add(number)
    return numbers


def next_job_number(used: set[int]) -> int:
    return _next_job_number(used)


def job_content(project: dict, iteration: int, job_number: int) -> str:
    today = dt.date.today().isoformat()
    root = project["root"]
    label = project["label"]
    focus = project["focus"]
    return f"""# Job: {label} iterative refactor {iteration}/{MAX_ITERATIONS}
Status: pending
Priority: medium
Created: {today}
Tags: scheduled-refactor, {project["slug"]}, iteration-{iteration}

## Objective
Use the refactoring skill/workflow to answer: what other refactoring can we do to further speed up this codebase and enhance readability? Then implement exactly one small, behavior-preserving refactor slice in `{root}`.

This is iteration {iteration} of {MAX_ITERATIONS} for `{project["slug"]}`. The goal is to build on whatever previous iterations already refactored, not repeat them.

## Context
- Project: {label}
- Project root: `{root}`
- Refactor focus: {focus}
- Chieh requested an hourly, bounded, iterative refactor loop across Waterlily, the education project, and Vessence.
- Read the project's local instructions and `REFACTORING.md` first when present.
- Check `git status --short` before editing. Treat existing unrelated dirty files as Chieh's work; do not revert or stage them.
- Before source edits, read the shared code coordination board, post this
  refactor slice, and claim only its intended files with
  `agent_skills/code_coordination.py`. If claims overlap, choose another safe
  slice rather than waiting for the whole repository.
- Prefer one coherent slice that improves speed, page/load time, developer reading speed, or module boundaries.
- Preserve behavior, public routes, data formats, report output, cache schemas, and UI text unless a proven bug requires a narrow fix.
- If no safe slice exists, document the blocker in the project refactor journal and stop cleanly.

## Steps
1. Read current project instructions, architecture/refactor notes, and the relevant modules.
2. Rank the next safe refactor candidates for this project.
3. Choose one small slice with low behavior risk and meaningful readability or speed impact.
4. Implement the slice behind compatibility wrappers when needed.
5. Run focused tests plus the strongest practical broader test command.
6. Update the project refactor journal with scope, files changed, behavior preserved, verification, and remaining follow-up.
7. If edits were made and tests passed, acquire the legacy exclusive project
   lock only for the shared-index commit step, commit only the intended project
   changes locally, then release it. Do not push unless credentials and project
   policy make that explicitly safe.
8. Close the coordination task so its claims are released.

## Verification
- Report the exact tests or checks run.
- If any test is unavailable or blocked, state the blocker and run the strongest focused substitute.
- Confirm unrelated dirty files were left untouched.

## Files Involved
- `{root}`
- Project refactor journal, usually `{root}/REFACTORING.md`
- Vessence job queue file `job_{job_number:03d}_{project["slug"]}_refactor_iter_{iteration:02d}.md`
"""


def write_job(project: dict, iteration: int, job_number: int) -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    filename = _job_filename(project["slug"], iteration, job_number)
    path = JOBS_DIR / filename
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(job_content(project, iteration, job_number))
    tmp.replace(path)
    return path


def disable_own_cron() -> bool:
    try:
        current = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        log(f"Could not read crontab for self-disable: {exc}")
        return False
    if current.returncode not in (0, 1):
        log(f"Could not read crontab for self-disable: exit {current.returncode}")
        return False

    today = dt.date.today().isoformat()
    installed, changed = _disabled_cron_text(current.stdout, marker=CRON_MARKER, today=today)
    if not changed:
        return False

    result = subprocess.run(["crontab", "-"], input=installed, text=True, check=False)
    if result.returncode == 0:
        log("Disabled iterative refactor scheduler cron entry after final enqueue.")
        return True
    log(f"Failed to disable iterative refactor scheduler cron entry: exit {result.returncode}")
    return False


def enqueue_iteration(state: dict, dry_run: bool = False) -> dict:
    current = int(state.get("iterations_enqueued", 0))
    if current >= MAX_ITERATIONS:
        state.setdefault("scheduler_completed_at", utc_now())
        if not dry_run:
            disable_own_cron()
            save_state(state)
        log(f"No enqueue needed; already scheduled {current}/{MAX_ITERATIONS} iterations.")
        return state

    iteration = current + 1
    used_numbers = existing_job_numbers()
    created_jobs: list[dict] = []
    for project in PROJECTS:
        job_number = next_job_number(used_numbers)
        if dry_run:
            path = JOBS_DIR / _job_filename(project["slug"], iteration, job_number)
        else:
            path = write_job(project, iteration, job_number)
        created_jobs.append({
            "project": project["slug"],
            "job_number": job_number,
            "path": str(path),
        })

    if dry_run:
        for job in created_jobs:
            log(f"DRY RUN would enqueue {job['path']}")
        return state

    state["iterations_enqueued"] = iteration
    state["last_enqueued_at"] = utc_now()
    state.setdefault("runs", []).append({
        "iteration": iteration,
        "enqueued_at": state["last_enqueued_at"],
        "jobs": created_jobs,
    })
    for job in created_jobs:
        state["projects"][job["project"]]["jobs"].append(job)
    if iteration >= MAX_ITERATIONS:
        state["scheduler_completed_at"] = utc_now()
    save_state(state)

    for job in created_jobs:
        log(f"Enqueued {job['path']}")

    if iteration >= MAX_ITERATIONS:
        disable_own_cron()
    return state


def print_status(state: dict) -> None:
    print(json.dumps(state, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show what would be enqueued without writing jobs/state.")
    parser.add_argument("--status", action="store_true", help="Print scheduler state and exit.")
    args = parser.parse_args()

    state = load_state()
    if args.status:
        print_status(state)
        return 0

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lock_fh:
        try:
            fcntl.lockf(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log("Another iterative refactor scheduler run is active; exiting.")
            return 0
        enqueue_iteration(state, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
