"""Pure helpers for creating minimal job queue files."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class JobCreationDraft:
    number: int
    filename: str
    first_line: str
    text: str


def job_safe_name(first_line: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", first_line.lower())[:40].strip("_")
    return safe_name or "task"


def next_job_number(existing_filenames: list[str]) -> int:
    numbers = []
    for filename in existing_filenames:
        match = re.match(r"^(\d+)", filename)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def build_job_creation_draft(text: str, existing_filenames: list[str]) -> JobCreationDraft:
    stripped_text = text.strip()
    first_line = stripped_text.splitlines()[0][:60].strip()
    number = next_job_number(existing_filenames)
    filename = f"{number:02d}_{job_safe_name(first_line)}.md"
    return JobCreationDraft(
        number=number,
        filename=filename,
        first_line=first_line,
        text=stripped_text,
    )


def minimal_job_content(first_line: str, text: str, created_date: str) -> str:
    return f"""# Job: {first_line}
Status: pending
Priority: medium
Created: {created_date}

## Objective
{text}

## Context
Added via `prompt:` / `add job:` command.

## Steps
1. Complete the task described in the Objective.

## Verification
Verify the objective is met.
"""
