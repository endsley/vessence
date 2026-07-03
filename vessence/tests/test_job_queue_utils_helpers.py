from agent_skills import job_queue_utils
from agent_skills.job_queue_utils_helpers import (
    completed_jobs_to_archive,
    parse_job_listing,
)


def test_job_queue_utils_uses_extracted_helpers():
    assert job_queue_utils._parse_job_listing is parse_job_listing
    assert job_queue_utils._completed_jobs_to_archive is completed_jobs_to_archive


def test_parse_job_listing_preserves_status_title_priority_rules():
    content = "# Job: Demo\nStatus: completed (done)\nPriority: 2 urgent\n"

    assert parse_job_listing(content, "001_demo.md", "/tmp/001_demo.md") == {
        "file": "001_demo.md",
        "path": "/tmp/001_demo.md",
        "title": "Demo",
        "status": "completed",
        "priority": 2,
    }


def test_parse_job_listing_preserves_fallbacks_and_bad_priority_behavior():
    assert parse_job_listing("Priority: high\n", "job.md", "/tmp/job.md") == {
        "file": "job.md",
        "path": "/tmp/job.md",
        "title": "job.md",
        "status": "unknown",
        "priority": 5,
    }


def test_completed_jobs_to_archive_uses_prefix_and_threshold_boundary():
    jobs = [
        {"status": "complete", "file": "1.md"},
        {"status": "completed", "file": "2.md"},
        {"status": "pending", "file": "3.md"},
    ]

    assert completed_jobs_to_archive(jobs, threshold=2) == []
    assert completed_jobs_to_archive(jobs, threshold=1) == jobs[:2]
