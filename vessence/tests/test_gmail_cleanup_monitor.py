import base64
import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skills import nutricost_deal_monitor as monitor  # noqa: E402


NY = ZoneInfo("America/New_York")


class _Request:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class _Messages:
    def __init__(self, service):
        self.service = service

    def get(self, userId, id, format):  # noqa: N803
        return _Request(self.service.messages[id])

    def trash(self, userId, id):  # noqa: N803
        self.service.trashed.append(id)
        return _Request({})


class _Users:
    def __init__(self, service):
        self.service = service

    def messages(self):
        return _Messages(self.service)


class _Service:
    def __init__(self, messages):
        self.messages = messages
        self.trashed = []

    def users(self):
        return _Users(self)


def _message(message_dt, sender, subject, *, labels=None, calendar_text=""):
    payload = {
        "headers": [
            {"name": "From", "value": sender},
            {"name": "Subject", "value": subject},
        ],
        "parts": [],
    }
    if calendar_text:
        payload["parts"].append({
            "mimeType": "text/calendar",
            "body": {
                "data": base64.urlsafe_b64encode(calendar_text.encode()).decode(),
            },
        })
    return {
        "internalDate": str(int(message_dt.timestamp() * 1000)),
        "labelIds": labels or [],
        "payload": payload,
    }


def test_crunchlabs_messages_are_trashed_for_daily_window():
    day = dt.date(2026, 6, 29)
    service = _Service({
        "msg-1": _message(
            dt.datetime(2026, 6, 29, 9, 0, tzinfo=NY),
            "CrunchLabs <hello@crunchlabs.com>",
            "New box",
        )
    })

    outcome = monitor.process_crunchlabs_message(service, "msg-1", day, dry_run=False)

    assert outcome == "crunchlabs_trashed"
    assert service.trashed == ["msg-1"]
    assert "from:crunchlabs" in monitor.build_crunchlabs_query(day, include_trash=False)


def test_sender_cleanup_respects_age_and_sender_header():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    service = _Service({
        "old-redfin": _message(
            now - dt.timedelta(days=4),
            "Redfin <updates@redfin.com>",
            "Homes near you",
        ),
        "young-redfin": _message(
            now - dt.timedelta(days=1),
            "Redfin <updates@redfin.com>",
            "New listing",
        ),
        "wrong-sender": _message(
            now - dt.timedelta(days=4),
            "Someone Else <hello@example.com>",
            "Not redfin",
        ),
    })

    assert monitor.process_sender_cleanup_message(
        service,
        "old-redfin",
        label="Redfin",
        sender_fragments=monitor.REDFIN_SENDER_FRAGMENTS,
        older_than_days=3,
        dry_run=False,
        now=now,
    ) == "redfin_trashed"
    assert monitor.process_sender_cleanup_message(
        service,
        "young-redfin",
        label="Redfin",
        sender_fragments=monitor.REDFIN_SENDER_FRAGMENTS,
        older_than_days=3,
        dry_run=False,
        now=now,
    ) == "redfin_too_recent"
    assert monitor.process_sender_cleanup_message(
        service,
        "wrong-sender",
        label="Redfin",
        sender_fragments=monitor.REDFIN_SENDER_FRAGMENTS,
        older_than_days=3,
        dry_run=False,
        now=now,
    ) == "redfin_skipped"
    assert service.trashed == ["old-redfin"]
    assert "older_than:3d" in monitor.build_older_sender_query("redfin", 3, include_trash=False)


def test_sender_cleanup_can_require_category_and_subject():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    service = _Service({
        "missed-discord": _message(
            now - dt.timedelta(days=4),
            "Discord <noreply@discord.com>",
            "You missed messages in Chieh's server",
            labels=["CATEGORY_UPDATES"],
        ),
        "security-discord": _message(
            now - dt.timedelta(days=4),
            "Discord <noreply@discord.com>",
            "Your Discord login code",
            labels=["CATEGORY_UPDATES"],
        ),
        "uncategorized-discord": _message(
            now - dt.timedelta(days=4),
            "Discord <noreply@discord.com>",
            "You missed messages in Chieh's server",
            labels=[],
        ),
    })

    assert monitor.process_sender_cleanup_message(
        service,
        "missed-discord",
        label="Discord Missed Messages",
        sender_fragments=("noreply@discord.com",),
        older_than_days=3,
        dry_run=False,
        subject_fragments=("you missed messages",),
        required_label_ids=("CATEGORY_UPDATES",),
        now=now,
    ) == "discord_missed_messages_trashed"
    assert monitor.process_sender_cleanup_message(
        service,
        "security-discord",
        label="Discord Missed Messages",
        sender_fragments=("noreply@discord.com",),
        older_than_days=3,
        dry_run=False,
        subject_fragments=("you missed messages",),
        required_label_ids=("CATEGORY_UPDATES",),
        now=now,
    ) == "discord_missed_messages_skipped_subject"
    assert monitor.process_sender_cleanup_message(
        service,
        "uncategorized-discord",
        label="Discord Missed Messages",
        sender_fragments=("noreply@discord.com",),
        older_than_days=3,
        dry_run=False,
        subject_fragments=("you missed messages",),
        required_label_ids=("CATEGORY_UPDATES",),
        now=now,
    ) == "discord_missed_messages_skipped_labels"
    assert service.trashed == ["missed-discord"]


def test_low_priority_cleanup_specs_use_three_day_targeted_queries():
    specs = {spec.label: spec for spec in monitor.SENDER_CLEANUP_SPECS}

    assert specs["LinkedIn"].retention_days == 3
    assert specs["LinkedIn"].query_terms == ("category:social",)
    assert specs["The Covery Promotions"].retention_days == 3
    assert specs["Museum of Science Promotions"].retention_days == 3
    assert specs["Spotify Promotions"].retention_days == 3
    assert specs["Discord Missed Messages"].query_terms == ('subject:"You missed messages"',)
    assert specs["Discord Missed Messages"].subject_fragments == ("you missed messages",)
    assert specs["LifespanIO Newsletters"].query_terms == ('subject:"Weekly News"',)
    assert specs["LifespanIO Newsletters"].subject_fragments == ("weekly news",)
    assert specs["Glassdoor Updates"].query_terms == ('subject:"employee reviews"',)
    assert specs["Glassdoor Updates"].subject_fragments == ("employee reviews",)

    query = monitor.build_older_sender_query(
        specs["The Covery Promotions"].from_query,
        specs["The Covery Promotions"].retention_days,
        include_trash=False,
        extra_terms=specs["The Covery Promotions"].query_terms,
    )
    assert "from:woburn@thecovery.com" in query
    assert "category:promotions" in query
    assert "older_than:3d" in query


def test_amazon_cleanup_uses_two_day_retention():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    service = _Service({
        "old-amazon": _message(
            now - dt.timedelta(days=3),
            "Amazon.com <store-news@amazon.com>",
            "Deals for you",
        ),
        "young-amazon": _message(
            now - dt.timedelta(hours=36),
            "Amazon.com <store-news@amazon.com>",
            "Recent order update",
        ),
    })

    assert monitor.process_sender_cleanup_message(
        service,
        "old-amazon",
        label="Amazon",
        sender_fragments=monitor.AMAZON_SENDER_FRAGMENTS,
        sender_domains=monitor.AMAZON_SENDER_DOMAINS,
        older_than_days=monitor.SENDER_CLEANUP_RETENTION_DAYS,
        dry_run=False,
        now=now,
    ) == "amazon_trashed"
    assert monitor.process_sender_cleanup_message(
        service,
        "young-amazon",
        label="Amazon",
        sender_fragments=monitor.AMAZON_SENDER_FRAGMENTS,
        sender_domains=monitor.AMAZON_SENDER_DOMAINS,
        older_than_days=monitor.SENDER_CLEANUP_RETENTION_DAYS,
        dry_run=False,
        now=now,
    ) == "amazon_too_recent"

    query = monitor.build_older_sender_query(
        monitor.AMAZON_FROM_QUERY,
        monitor.SENDER_CLEANUP_RETENTION_DAYS,
        include_trash=False,
    )
    assert service.trashed == ["old-amazon"]
    assert "amazon.com" in query
    assert "amazonaws.com" in query
    assert "older_than:2d" in query


def test_amazon_cleanup_skips_amazon_ses_infrastructure_senders():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    service = _Service({
        "merchant": _message(
            now - dt.timedelta(days=3),
            "Merchant <bounce@amazonses.com>",
            "Your merchant order shipped",
        )
    })

    assert monitor.process_sender_cleanup_message(
        service,
        "merchant",
        label="Amazon",
        sender_fragments=monitor.AMAZON_SENDER_FRAGMENTS,
        sender_domains=monitor.AMAZON_SENDER_DOMAINS,
        older_than_days=monitor.SENDER_CLEANUP_RETENTION_DAYS,
        dry_run=False,
        now=now,
    ) == "amazon_skipped"
    assert service.trashed == []


def test_google_calendar_messages_delete_only_after_event_passed():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    passed_ics = "\n".join([
        "BEGIN:VCALENDAR",
        "BEGIN:VEVENT",
        "DTSTART:20260620T090000",
        "DTEND:20260620T100000",
        "END:VEVENT",
        "END:VCALENDAR",
    ])
    future_ics = "\n".join([
        "BEGIN:VCALENDAR",
        "BEGIN:VEVENT",
        "DTSTART:20260720T090000",
        "DTEND:20260720T100000",
        "END:VEVENT",
        "END:VCALENDAR",
    ])
    service = _Service({
        "past": _message(
            now - dt.timedelta(days=10),
            "Google Calendar <calendar-notification@google.com>",
            "Past event",
            calendar_text=passed_ics,
        ),
        "future": _message(
            now - dt.timedelta(days=10),
            "Google Calendar <calendar-notification@google.com>",
            "Future event",
            calendar_text=future_ics,
        ),
    })

    assert monitor.process_google_calendar_message(service, "past", dry_run=False, now=now) == "google_calendar_trashed"
    assert monitor.process_google_calendar_message(service, "future", dry_run=False, now=now) == "google_calendar_future_event"
    assert service.trashed == ["past"]
    assert "calendar-notification" in monitor.build_google_calendar_query(include_trash=False)


def test_google_calendar_messages_fall_back_to_subject_date():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    service = _Service({
        "past-subject": _message(
            now - dt.timedelta(days=1),
            "Google Calendar <calendar-notification@google.com>",
            "Notification: Take out the trash @ Tue Jun 23, 2026 7pm - 8pm (EDT) (chieh.t.wu@gmail.com)",
        ),
        "future-subject": _message(
            now - dt.timedelta(days=1),
            "Google Calendar <calendar-notification@google.com>",
            "Notification: Dentist @ Thu Jul 23, 2026 7pm - 8pm (EDT) (chieh.t.wu@gmail.com)",
        ),
    })

    assert monitor.process_google_calendar_message(service, "past-subject", dry_run=False, now=now) == "google_calendar_trashed"
    assert monitor.process_google_calendar_message(service, "future-subject", dry_run=False, now=now) == "google_calendar_future_event"
    assert service.trashed == ["past-subject"]


def test_old_unread_cleanup_requires_unread_label_and_age():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    service = _Service({
        "old-unread": _message(now - dt.timedelta(days=30), "Sender <a@example.com>", "Old unread", labels=["UNREAD"]),
        "old-read": _message(now - dt.timedelta(days=30), "Sender <a@example.com>", "Old read", labels=[]),
        "young-unread": _message(now - dt.timedelta(days=5), "Sender <a@example.com>", "Young unread", labels=["UNREAD"]),
    })

    assert monitor.process_unread_cleanup_message(
        service,
        "old-unread",
        older_than_days=21,
        dry_run=False,
        now=now,
    ) == "old_unread_trashed"
    assert monitor.process_unread_cleanup_message(
        service,
        "old-read",
        older_than_days=21,
        dry_run=False,
        now=now,
    ) == "old_unread_skipped_read"
    assert monitor.process_unread_cleanup_message(
        service,
        "young-unread",
        older_than_days=21,
        dry_run=False,
        now=now,
    ) == "old_unread_too_recent"
    assert service.trashed == ["old-unread"]
    assert "is:unread" in monitor.build_unread_cleanup_query(21, include_trash=False)
    assert "older_than:21d" in monitor.build_unread_cleanup_query(21, include_trash=False)


def test_unread_cleanup_count_uses_message_policy_for_dry_run():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    service = _Service({
        "old-unread": _message(now - dt.timedelta(days=30), "Sender <a@example.com>", "Old unread", labels=["UNREAD"]),
        "old-read": _message(now - dt.timedelta(days=30), "Sender <a@example.com>", "Old read", labels=[]),
        "young-unread": _message(now - dt.timedelta(days=5), "Sender <a@example.com>", "Young unread", labels=["UNREAD"]),
    })

    assert monitor.count_unread_cleanup_messages(
        service,
        ["old-unread", "old-read", "young-unread"],
        older_than_days=21,
        dry_run=True,
        now=now,
    ) == {
        "old_unread_would_trash": 1,
        "old_unread_skipped_read": 1,
        "old_unread_too_recent": 1,
    }
    assert service.trashed == []
