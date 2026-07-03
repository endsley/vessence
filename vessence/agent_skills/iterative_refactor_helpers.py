"""Pure helpers for iterative_refactor_scheduler.py."""
from __future__ import annotations

import re
from collections.abc import Iterable


def default_scheduler_state(*, now: str, max_iterations: int, projects: Iterable[dict]) -> dict:
    return {
        "version": 1,
        "created_at": now,
        "max_iterations": max_iterations,
        "iterations_enqueued": 0,
        "projects": {project["slug"]: {"jobs": []} for project in projects},
    }


def normalize_scheduler_state(
    state: dict,
    *,
    now: str,
    max_iterations: int,
    projects: Iterable[dict],
) -> dict:
    state.setdefault("version", 1)
    state.setdefault("created_at", now)
    state.setdefault("max_iterations", max_iterations)
    state.setdefault("iterations_enqueued", 0)
    project_state = state.setdefault("projects", {})
    for project in projects:
        project_state.setdefault(project["slug"], {"jobs": []})
        project_state[project["slug"]].setdefault("jobs", [])
    return state


def extract_job_number(filename: str) -> int | None:
    match = re.match(r"(?:job_)?(\d+)", filename)
    return int(match.group(1)) if match else None


def next_job_number(used: set[int]) -> int:
    value = max(used, default=0) + 1
    while value in used:
        value += 1
    used.add(value)
    return value


def job_filename(project_slug: str, iteration: int, job_number: int) -> str:
    return f"job_{job_number:03d}_{project_slug}_refactor_iter_{iteration:02d}.md"


def disabled_cron_text(crontab_text: str, *, marker: str, today: str) -> tuple[str, bool]:
    changed = False
    new_lines: list[str] = []
    for line in crontab_text.splitlines():
        stripped = line.lstrip()
        if marker in line and not stripped.startswith("#"):
            new_lines.append(f"# COMPLETED {today}: {line}")
            changed = True
        else:
            new_lines.append(line)
    if not changed:
        return crontab_text, False
    return "\n".join(new_lines).rstrip() + "\n", True
