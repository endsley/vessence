import base64
import datetime as dt
from zoneinfo import ZoneInfo

from agent_skills import nutricost_deal_monitor
from agent_skills.gmail_message_utils import (
    google_calendar_event_end_from_subject,
    header_map,
    message_is_older_than_days,
    message_text,
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


def test_google_calendar_subject_parser_uses_end_time_and_period_fallback():
    subject = (
        "Notification: Appointment @ Tue Jun 23, 2026 "
        "7 - 8pm (EDT) (chieh.t.wu@gmail.com)"
    )

    assert google_calendar_event_end_from_subject(subject) == dt.datetime(
        2026, 6, 23, 20, 0, tzinfo=NY,
    )
