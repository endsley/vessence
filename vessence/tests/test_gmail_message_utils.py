import base64
import datetime as dt
from zoneinfo import ZoneInfo

from agent_skills import nutricost_deal_monitor
from agent_skills.gmail_message_utils import (
    google_calendar_event_end_from_subject,
    google_calendar_subject_date,
    google_calendar_subject_match,
    google_calendar_subject_times,
    header_map,
    message_is_older_than_days,
    message_text,
    ny_aware_datetime,
    parse_subject_time,
    sender_matches_domains,
)


NY = ZoneInfo("America/New_York")


def _encoded(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_message_text_prefers_plain_parts_and_strips_html_fallback():
    message = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": _encoded("<p>HTML</p><script>skip()</script>")},
                },
                {
                    "mimeType": "text/plain",
                    "body": {"data": _encoded("Plain body")},
                },
            ],
        },
    }
    html_only = {
        "payload": {
            "mimeType": "text/html",
            "body": {"data": _encoded("<style>x</style><p>Visible text</p>")},
        },
    }

    assert message_text(message) == "Plain body"
    assert message_text(html_only) == "Visible text"


def test_header_map_and_age_helpers_are_reexported_from_monitor():
    assert nutricost_deal_monitor.header_map is header_map
    assert nutricost_deal_monitor.message_is_older_than_days is message_is_older_than_days

    headers = header_map({
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Hello"},
                {"name": "From", "value": "Sender <s@example.com>"},
            ],
        },
    })
    assert headers == {"subject": "Hello", "from": "Sender <s@example.com>"}


def test_sender_domain_matching_allows_subdomains_but_not_similar_domains():
    assert sender_matches_domains(
        "Deals <news@store.amazon.com>",
        ("amazon.com",),
    )
    assert not sender_matches_domains(
        "Merchant <bounce@amazonses.com>",
        ("amazon.com",),
    )


def test_message_is_older_than_days_uses_new_york_internal_date():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    old_message = {
        "internalDate": str(int((now - dt.timedelta(days=4)).timestamp() * 1000)),
    }
    young_message = {
        "internalDate": str(int((now - dt.timedelta(hours=12)).timestamp() * 1000)),
    }

    assert message_is_older_than_days(old_message, 3, now=now)
    assert not message_is_older_than_days(young_message, 3, now=now)
    assert not message_is_older_than_days({"internalDate": "bad"}, 3, now=now)


def test_ny_aware_datetime_normalizes_naive_and_aware_values():
    naive = dt.datetime(2026, 6, 29, 12, 0)
    utc = dt.datetime(2026, 6, 29, 16, 0, tzinfo=dt.timezone.utc)

    assert ny_aware_datetime(naive) == dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    assert ny_aware_datetime(utc) == dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    assert ny_aware_datetime().tzinfo == NY


def test_google_calendar_subject_parser_uses_end_time_and_period_fallback():
    subject = (
        "Notification: Appointment @ Tue Jun 23, 2026 "
        "7 - 8pm (EDT) (chieh.t.wu@gmail.com)"
    )
    match = google_calendar_subject_match(subject)

    assert parse_subject_time("12am") == dt.time(0, 0)
    assert parse_subject_time("7", fallback_period="pm") == dt.time(19, 0)
    assert parse_subject_time("24:00") is None
    assert match is not None
    assert google_calendar_subject_date(match) == dt.date(2026, 6, 23)
    assert google_calendar_subject_times(match) == (dt.time(7, 0), dt.time(20, 0))

    assert google_calendar_event_end_from_subject(subject) == dt.datetime(
        2026, 6, 23, 20, 0, tzinfo=NY,
    )
    assert google_calendar_event_end_from_subject("Notification @ Jun 23, 2026") == dt.datetime(
        2026, 6, 23, 23, 59, 59, 999999, tzinfo=NY,
    )
    assert google_calendar_subject_match("No calendar details") is None
