from agent_skills import show_job_queue


def test_job_queue_defaults_include_expected_columns():
    columns = show_job_queue.load_job_queue_columns()
    assert columns == ["#", "Job", "Summary", "Status", "Result"]


def test_get_job_queue_data_returns_structured_data():
    data = show_job_queue.get_job_queue_data()
    assert "columns" in data
    assert "jobs" in data
    assert "count" in data
    assert isinstance(data["jobs"], list)
    assert data["count"] == len(data["jobs"])


def test_load_jobs_returns_expected_fields():
    jobs = show_job_queue.load_jobs()
    if jobs:
        job = jobs[0]
        for key in ("num", "file", "name", "status", "status_icon", "priority", "priority_label", "summary", "result"):
            assert key in job, f"Missing key: {key}"
