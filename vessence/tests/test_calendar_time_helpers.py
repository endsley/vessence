import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from agent_skills import calendar_tools
from agent_skills.calendar_time_helpers import (
    dt_to_iso_utc,
    normalized_range_hint,
    reminder_overrides_body,
    resolve_range_for_now,
    to_local_naive_iso,
)


NY = ZoneInfo("America/New_York")


def test_calendar_tools_uses_extracted_time_helpers():
    assert calendar_tools._dt_to_iso_utc is dt_to_iso_utc
    assert calendar_tools._to_local_naive_iso is to_local_naive_iso
    assert calendar_tools._resolve_range_for_now is resolve_range_for_now
    assert calendar_tools._reminder_overrides_body is reminder_overrides_body


def test_normalized_range_hint_preserves_calendar_alias_rules() -> None:
    assert normalized_range_hint(None) == "today"
    assert normalized_range_hint(" This Week ") == "this_week"
    assert normalized_range_hint("next 90 days") == "next_90_days"


def test_resolve_range_for_now_preserves_day_week_and_next_ranges():
    now = dt.datetime(2026, 7, 2, 15, 30, tzinfo=NY)  # Thursday

    assert resolve_range_for_now("today", now) == (
        dt.datetime(2026, 7, 2, 0, 0, tzinfo=NY),
        dt.datetime(2026, 7, 3, 0, 0, tzinfo=NY),
    )
    assert resolve_range_for_now("tomorrow", now)[0] == dt.datetime(2026, 7, 3, 0, 0, tzinfo=NY)
    assert resolve_range_for_now("weekend", now) == (
        dt.datetime(2026, 7, 4, 0, 0, tzinfo=NY),
        dt.datetime(2026, 7, 6, 0, 0, tzinfo=NY),
    )
    assert resolve_range_for_now("this week", now) == (
        dt.datetime(2026, 6, 29, 0, 0, tzinfo=NY),
        dt.datetime(2026, 7, 6, 0, 0, tzinfo=NY),
    )
    assert resolve_range_for_now("next_week", now) == (
        dt.datetime(2026, 7, 6, 0, 0, tzinfo=NY),
        dt.datetime(2026, 7, 13, 0, 0, tzinfo=NY),
    )
    assert resolve_range_for_now("next_30", now) == (now, now + dt.timedelta(days=30))


def test_resolve_range_for_now_preserves_weekday_date_and_unknown_fallbacks():
    now = dt.datetime(2026, 7, 2, 15, 30, tzinfo=NY)  # Thursday

    assert resolve_range_for_now("thursday", now)[0] == dt.datetime(2026, 7, 2, 0, 0, tzinfo=NY)
    assert resolve_range_for_now("monday", now)[0] == dt.datetime(2026, 7, 6, 0, 0, tzinfo=NY)
    assert resolve_range_for_now("2026-08-01", now) == (
        dt.datetime(2026, 8, 1, 0, 0, tzinfo=NY),
        dt.datetime(2026, 8, 2, 0, 0, tzinfo=NY),
    )
    assert resolve_range_for_now("unknown", now)[0] == dt.datetime(2026, 7, 2, 0, 0, tzinfo=NY)


def test_iso_helpers_preserve_existing_calendar_serialization_rules():
    assert dt_to_iso_utc(dt.datetime(2026, 7, 2, 12, 0, tzinfo=dt.timezone.utc)) == (
        "2026-07-02T12:00:00Z"
    )
    assert to_local_naive_iso("2026-07-02T12:00:00-04:00") == "2026-07-02T12:00:00"
    assert to_local_naive_iso("not iso") == "not iso"


def test_reminder_overrides_body_validates_google_limits():
    assert reminder_overrides_body([10, 60]) == {
        "useDefault": False,
        "overrides": [
            {"method": "popup", "minutes": 10},
            {"method": "popup", "minutes": 60},
        ],
    }
    with pytest.raises(ValueError, match="at most 5"):
        reminder_overrides_body([1, 2, 3, 4, 5, 6])
    with pytest.raises(ValueError, match="got -1"):
        reminder_overrides_body([-1])
    with pytest.raises(ValueError, match="got '5'"):
        reminder_overrides_body(["5"])
