from datetime import datetime

from agent_skills import essence_scheduler
from agent_skills.cron_schedule import matches_schedule


def test_essence_scheduler_uses_extracted_cron_matcher() -> None:
    assert essence_scheduler._matches_schedule is matches_schedule


def test_matches_schedule_supports_wildcard_exact_list_range_and_step_fields() -> None:
    now = datetime(2026, 7, 5, 8, 15)  # Sunday; cron weekday 0

    assert matches_schedule("* * * * *", now)
    assert matches_schedule("15 8 5 7 0", now)
    assert not matches_schedule("15 8 5 7 6", now)
    assert matches_schedule("14,15 8 * * *", now)
    assert not matches_schedule("13,14 8 * * *", now)
    assert matches_schedule("10-20 8 * * *", now)
    assert not matches_schedule("16-20 8 * * *", now)
    assert matches_schedule("*/15 * * * *", now)
    assert not matches_schedule("*/20 * * * *", now)
    assert matches_schedule("5/10 * * * *", now)


def test_matches_schedule_rejects_invalid_specs_without_raising() -> None:
    now = datetime(2026, 7, 5, 8, 15)

    assert not matches_schedule("", now)
    assert not matches_schedule("* * * *", now)
    assert not matches_schedule("bad * * * *", now)
    assert not matches_schedule("*/0 * * * *", now)
