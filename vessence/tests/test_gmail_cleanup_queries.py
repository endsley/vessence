import datetime as dt
from zoneinfo import ZoneInfo

from agent_skills import nutricost_deal_monitor as monitor
from agent_skills.gmail_cleanup_queries import (
    build_google_calendar_query,
    build_older_sender_query,
    build_sender_query,
    build_unread_cleanup_query,
    gmail_date,
    previous_local_day,
    sender_cleanup_prefix,
)


def test_monitor_reexports_date_query_helpers():
    assert monitor.previous_local_day is previous_local_day
    assert monitor.gmail_date is gmail_date
    assert monitor._sender_cleanup_prefix is sender_cleanup_prefix


def test_previous_local_day_handles_naive_and_aware_datetimes():
    ny = ZoneInfo("America/New_York")

    assert previous_local_day(dt.datetime(2026, 7, 2, 8, 0, tzinfo=ny)) == dt.date(2026, 7, 1)
    assert previous_local_day(dt.datetime(2026, 7, 2, 8, 0)) == dt.date(2026, 7, 1)


def test_sender_cleanup_prefix_and_gmail_date():
    assert gmail_date(dt.date(2026, 7, 2)) == "2026/07/02"
    assert sender_cleanup_prefix("Discord Missed Messages") == "discord_missed_messages"
    assert sender_cleanup_prefix("!!!") == "sender_cleanup"


def test_sender_query_uses_wide_local_day_window_and_trash_flag():
    query = build_sender_query(
        recipient="user@example.com",
        day=dt.date(2026, 7, 2),
        from_query="sender",
        include_trash=False,
    )

    assert query == (
        "to:user@example.com from:sender after:2026/07/01 "
        "before:2026/07/04 -in:spam -in:trash"
    )
    assert build_sender_query(
        recipient="user@example.com",
        day=dt.date(2026, 7, 2),
        from_query="sender",
        include_trash=True,
    ).startswith("in:anywhere ")


def test_older_calendar_and_unread_queries_preserve_terms():
    assert build_older_sender_query(
        recipient="user@example.com",
        from_query="redfin",
        older_than_days=3,
        include_trash=False,
        extra_terms=("category:promotions",),
    ) == (
        "to:user@example.com from:redfin category:promotions "
        "older_than:3d -in:spam -in:trash"
    )
    assert build_google_calendar_query(
        recipient="user@example.com",
        from_query="calendar",
        include_trash=False,
    ) == "to:user@example.com from:calendar -in:spam -in:trash"
    assert build_unread_cleanup_query(
        older_than_days=21,
        include_trash=True,
    ) == "in:anywhere is:unread older_than:21d -in:spam"
