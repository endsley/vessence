from agent_skills import job_queue_runner
from agent_skills.job_queue_creation import (
    JobCreationDraft,
    build_job_creation_draft,
    job_safe_name,
    minimal_job_content,
    next_job_number,
)


def test_job_queue_runner_uses_extracted_creation_helpers():
    assert job_queue_runner._build_job_creation_draft is build_job_creation_draft
    assert job_queue_runner._job_safe_name is job_safe_name
    assert job_queue_runner._minimal_job_content is minimal_job_content
    assert job_queue_runner._next_job_number is next_job_number


def test_job_safe_name_preserves_slug_rules_and_fallback():
    assert job_safe_name("Fix Jane Web/API!") == "fix_jane_web_api"
    assert job_safe_name("x" * 50) == "x" * 40
    assert job_safe_name("!!!") == "task"


def test_next_job_number_reads_numeric_prefixes_only():
    assert next_job_number(["01_first.md", "job_002_old.md", "12_task.md", "README.md"]) == 13
    assert next_job_number(["README.md"]) == 1


def test_build_job_creation_draft_preserves_title_and_filename_shape():
    draft = build_job_creation_draft(
        "  Fix Jane Web/API!\nMore detail",
        ["01_old.md"],
    )

    assert draft == JobCreationDraft(
        number=2,
        filename="02_fix_jane_web_api.md",
        first_line="Fix Jane Web/API!",
        text="Fix Jane Web/API!\nMore detail",
    )


def test_minimal_job_content_preserves_template():
    assert minimal_job_content("Fix thing", "Fix thing\nMore", "2026-07-02") == """# Job: Fix thing
Status: pending
Priority: medium
Created: 2026-07-02

## Objective
Fix thing
More

## Context
Added via `prompt:` / `add job:` command.

## Steps
1. Complete the task described in the Objective.

## Verification
Verify the objective is met.
"""
