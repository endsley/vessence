from agent_skills import job_queue_runner
from agent_skills.job_queue_memory import job_completion_fact, job_number_from_file


def test_job_queue_runner_uses_memory_helpers():
    assert job_queue_runner._job_completion_fact is job_completion_fact
    assert job_queue_runner._job_number_from_file is job_number_from_file


def test_job_number_from_file_preserves_existing_prefix_rule():
    assert job_number_from_file("/tmp/012_refactor.md") == "012"
    assert job_number_from_file("/tmp/no_underscore.md") == "no"


def test_job_completion_fact_preserves_existing_fact_shape():
    assert job_completion_fact(
        "012",
        "Refactor queue",
        "r" * 301,
        "2026-07-02 12:34 UTC",
    ) == (
        "Job #012 completed autonomously on 2026-07-02 12:34 UTC. "
        "Title: Refactor queue. "
        f"Result: {'r' * 300}..."
    )
