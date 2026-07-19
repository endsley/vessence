from agent_skills import job_queue_runner


def test_generic_runner_excludes_pending_self_healing_markdown(tmp_path, monkeypatch):
    """Dedicated repair incidents stay pending for self_healing_repair.py."""
    self_healing = tmp_path / "01_self_healing.md"
    self_healing.write_text(
        """# Job: Repair a captured incident
Status: pending
Priority: high
Source: jane_self_healing

## Objective
Repair the incident through the dedicated provider handoff.
""",
        encoding="utf-8",
    )
    ordinary = tmp_path / "02_ordinary.md"
    ordinary.write_text(
        """# Job: Ordinary queued work
Status: pending
Priority: low
Source: user_request

## Objective
Complete ordinary queue work.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(job_queue_runner, "JOBS_DIR", str(tmp_path))

    pending = job_queue_runner.load_pending_jobs()

    assert [job["title"] for job in pending] == ["Ordinary queued work"]
    assert "Status: pending" in self_healing.read_text(encoding="utf-8")
    assert job_queue_runner.get_next_pending_job()["file"] == str(ordinary)


def test_self_healing_source_marker_is_whitespace_and_case_tolerant():
    assert job_queue_runner._is_dedicated_self_healing_job(
        "# Job: repair\nSource: JANE_SELF_HEALING   \n"
    )
    assert not job_queue_runner._is_dedicated_self_healing_job(
        "# Job: ordinary\nSource: user_request\n"
    )
