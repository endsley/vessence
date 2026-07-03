from agent_skills import iterative_refactor_scheduler as scheduler
from agent_skills.iterative_refactor_helpers import (
    default_scheduler_state,
    disabled_cron_text,
    extract_job_number,
    job_filename,
    next_job_number,
    normalize_scheduler_state,
)


PROJECTS = (
    {"slug": "alpha"},
    {"slug": "beta"},
)


def test_scheduler_exposes_helpers():
    assert scheduler._default_scheduler_state is default_scheduler_state
    assert scheduler._disabled_cron_text is disabled_cron_text
    assert scheduler._extract_job_number is extract_job_number
    assert scheduler._job_filename is job_filename
    assert scheduler._next_job_number is next_job_number
    assert scheduler._normalize_scheduler_state is normalize_scheduler_state


def test_default_and_normalized_state_shapes():
    assert default_scheduler_state(now="NOW", max_iterations=5, projects=PROJECTS) == {
        "version": 1,
        "created_at": "NOW",
        "max_iterations": 5,
        "iterations_enqueued": 0,
        "projects": {"alpha": {"jobs": []}, "beta": {"jobs": []}},
    }

    state = {"projects": {"alpha": {}}}
    normalized = normalize_scheduler_state(
        state,
        now="NOW",
        max_iterations=5,
        projects=PROJECTS,
    )
    assert normalized["created_at"] == "NOW"
    assert normalized["projects"]["alpha"]["jobs"] == []
    assert normalized["projects"]["beta"]["jobs"] == []


def test_job_number_helpers_preserve_filename_rules_and_mutate_used_set():
    assert extract_job_number("job_007_vessence_refactor_iter_01.md") == 7
    assert extract_job_number("42_manual.md") == 42
    assert extract_job_number("README.md") is None

    used = {1, 2, 4}
    assert next_job_number(used) == 5
    assert 5 in used
    assert job_filename("vessence", 3, 12) == "job_012_vessence_refactor_iter_03.md"


def test_disabled_cron_text_comments_only_active_marker_lines():
    crontab = "\n".join(
        [
            "# existing comment JANE_ITERATIVE_PROJECT_REFACTOR_CRON",
            "0 * * * * run-it # JANE_ITERATIVE_PROJECT_REFACTOR_CRON",
            "5 * * * * other",
        ]
    )
    updated, changed = disabled_cron_text(
        crontab,
        marker="JANE_ITERATIVE_PROJECT_REFACTOR_CRON",
        today="2026-07-02",
    )
    assert changed
    assert updated == (
        "# existing comment JANE_ITERATIVE_PROJECT_REFACTOR_CRON\n"
        "# COMPLETED 2026-07-02: 0 * * * * run-it # JANE_ITERATIVE_PROJECT_REFACTOR_CRON\n"
        "5 * * * * other\n"
    )

    unchanged, changed = disabled_cron_text("5 * * * * other", marker="MARK", today="2026-07-02")
    assert not changed
    assert unchanged == "5 * * * * other"
