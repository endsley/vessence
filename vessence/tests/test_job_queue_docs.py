from agent_skills import job_queue_runner
from agent_skills import check_continuation, run_queue_next
from agent_skills.job_queue_docs import (
    PRIORITY_MAP,
    PROMPT_SECTIONS,
    SELF_CONTINUATION_INSTRUCTION,
    build_prompt,
    job_num_from_filename,
    pending_job_summaries_from_dir,
    pending_job_summary,
    parse_job_content,
    set_status_content,
    sort_pending_job_summaries,
)


def test_job_queue_runner_uses_extracted_doc_helpers() -> None:
    assert job_queue_runner.PRIORITY_MAP is PRIORITY_MAP
    assert job_queue_runner.SELF_CONTINUATION_INSTRUCTION is SELF_CONTINUATION_INSTRUCTION
    assert job_queue_runner._parse_job_content is parse_job_content
    assert job_queue_runner._set_status_content is set_status_content
    assert job_queue_runner._build_prompt_doc is build_prompt
    assert run_queue_next.PRIORITY_MAP is PRIORITY_MAP
    assert run_queue_next._pending_job_summaries_from_dir is pending_job_summaries_from_dir
    assert run_queue_next._pending_job_summary is pending_job_summary
    assert run_queue_next._sort_pending_job_summaries is sort_pending_job_summaries
    assert check_continuation.PRIORITY_MAP is PRIORITY_MAP
    assert check_continuation._pending_job_summaries_from_dir is pending_job_summaries_from_dir
    assert check_continuation._pending_job_summary is pending_job_summary
    assert check_continuation._sort_pending_job_summaries is sort_pending_job_summaries


def test_parse_job_content_reads_title_status_priority_and_falls_back_to_filename() -> None:
    content = "# Job: Refactor Thing\nStatus: pending (queued)\nPriority: high\n"
    assert parse_job_content(content, "/tmp/job_one.md") == {
        "file": "/tmp/job_one.md",
        "title": "Refactor Thing",
        "status": "pending",
        "priority": 1,
        "content": content,
    }

    missing = "No metadata"
    assert parse_job_content(missing, "/tmp/job_two.md") == {
        "file": "/tmp/job_two.md",
        "title": "job_two",
        "status": "unknown",
        "priority": 3,
        "content": missing,
    }


def test_pending_job_summary_extracts_queue_entry_and_preserves_legacy_title_fallback() -> None:
    content = "# Job: Refactor Thing\nStatus: pending (queued)\nPriority: medium\n"
    assert pending_job_summary(content, "/tmp/07_job.md") == {
        "num": 7,
        "title": "Refactor Thing",
        "priority": 2,
        "file": "/tmp/07_job.md",
    }

    missing_title = "Status: pending\nPriority: high\n"
    assert pending_job_summary(missing_title, "/tmp/08_missing.md", missing_title="08_missing.md") == {
        "num": 8,
        "title": "08_missing.md",
        "priority": 1,
        "file": "/tmp/08_missing.md",
    }
    assert pending_job_summary("Status: completed\nPriority: high\n", "/tmp/01_done.md") is None
    assert job_num_from_filename("/tmp/not_numbered.md") == 999


def test_sort_pending_job_summaries_orders_by_priority_then_job_number() -> None:
    jobs = [
        {"num": 20, "priority": 2, "title": "B"},
        {"num": 7, "priority": 1, "title": "A"},
        {"num": 3, "priority": 2, "title": "C"},
    ]
    assert [job["title"] for job in sort_pending_job_summaries(jobs)] == ["A", "C", "B"]


def test_pending_job_summaries_from_dir_reads_markdown_jobs_and_sorts(tmp_path) -> None:
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    (jobs_dir / "README.md").write_text("Status: pending\n", encoding="utf-8")
    (jobs_dir / "03_medium.md").write_text(
        "# Job: Medium\nStatus: pending\nPriority: medium\n",
        encoding="utf-8",
    )
    (jobs_dir / "02_done.md").write_text(
        "# Job: Done\nStatus: completed\nPriority: high\n",
        encoding="utf-8",
    )
    (jobs_dir / "01_high.md").write_text(
        "# Job: High\nStatus: pending\nPriority: high\n",
        encoding="utf-8",
    )
    (jobs_dir / "04_missing_title.md").write_text(
        "Status: pending\nPriority: low\n",
        encoding="utf-8",
    )
    (jobs_dir / "notes.txt").write_text("Status: pending\n", encoding="utf-8")

    assert pending_job_summaries_from_dir(jobs_dir) == [
        {"num": 1, "title": "High", "priority": 1, "file": str(jobs_dir / "01_high.md")},
        {"num": 3, "title": "Medium", "priority": 2, "file": str(jobs_dir / "03_medium.md")},
        {
            "num": 4,
            "title": "04_missing_title.md",
            "priority": 3,
            "file": str(jobs_dir / "04_missing_title.md"),
        },
    ]
    assert pending_job_summaries_from_dir(jobs_dir / "missing") == []


def test_set_status_content_replaces_status_and_adds_or_replaces_result_section() -> None:
    base = "# Job: Demo\nStatus: pending\nBody"
    assert set_status_content(base, "completed") == "# Job: Demo\nStatus: completed\nBody"
    assert set_status_content(base, "completed", "Done") == (
        "# Job: Demo\nStatus: completed\nBody\n\n## Result\nDone\n"
    )
    existing = "# Job: Demo\nStatus: pending\n\n## Result\nOld\nTrailing"
    assert set_status_content(existing, "incomplete", "New") == (
        "# Job: Demo\nStatus: incomplete\n\n## Result\nNew"
    )


def test_build_prompt_extracts_known_sections_and_appends_self_continuation() -> None:
    content = """
# Job: Demo
Status: pending
Priority: medium

## Objective
Ship it.

## Context
Existing system.

## Empty
Ignore this.

## Steps
1. Test

## Notes

""".strip()
    job = {"title": "Demo", "content": content}

    prompt = build_prompt(job)

    assert PROMPT_SECTIONS[:3] == ["Objective", "Context", "Steps"]
    assert prompt.startswith("# Task: Demo\n\n## Objective\nShip it.")
    assert "## Context\nExisting system." in prompt
    assert "## Steps\n1. Test" in prompt
    assert "## Empty" not in prompt
    assert prompt.endswith(SELF_CONTINUATION_INSTRUCTION)
