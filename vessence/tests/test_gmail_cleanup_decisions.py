import base64
import datetime as dt
from zoneinfo import ZoneInfo

from agent_skills.gmail_cleanup_decisions import (
    evaluate_google_calendar_cleanup_message,
    evaluate_sender_cleanup_message,
    evaluate_unread_cleanup_message,
)


NY = ZoneInfo("America/New_York")


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


def test_sender_cleanup_decision_applies_sender_subject_label_age_and_dry_run():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)

    old_matching = _message(
        now - dt.timedelta(days=4),
        "Discord <noreply@discord.com>",
        "You missed messages in Chieh's server",
        labels=["CATEGORY_UPDATES"],
    )
    decision = evaluate_sender_cleanup_message(
        old_matching,
        label="Discord Missed Messages",
        sender_fragments=("noreply@discord.com",),
        older_than_days=3,
        dry_run=True,
        subject_fragments=("you missed messages",),
        required_label_ids=("CATEGORY_UPDATES",),
        now=now,
    )
    assert decision.outcome == "discord_missed_messages_would_trash"
    assert decision.should_trash
    assert decision.subject == "You missed messages in Chieh's server"

    wrong_sender = _message(now - dt.timedelta(days=4), "Sender <x@example.com>", "You missed messages")
    assert evaluate_sender_cleanup_message(
        wrong_sender,
        label="Discord Missed Messages",
        sender_fragments=("noreply@discord.com",),
        older_than_days=3,
        dry_run=False,
        now=now,
    ).outcome == "discord_missed_messages_skipped"

    missing_label = _message(
        now - dt.timedelta(days=4),
        "Discord <noreply@discord.com>",
        "You missed messages",
    )
    assert evaluate_sender_cleanup_message(
        missing_label,
        label="Discord Missed Messages",
        sender_fragments=("noreply@discord.com",),
        older_than_days=3,
        dry_run=False,
        required_label_ids=("CATEGORY_UPDATES",),
        now=now,
    ).outcome == "discord_missed_messages_skipped_labels"

    wrong_subject = _message(
        now - dt.timedelta(days=4),
        "Discord <noreply@discord.com>",
        "Your login code",
        labels=["CATEGORY_UPDATES"],
    )
    assert evaluate_sender_cleanup_message(
        wrong_subject,
        label="Discord Missed Messages",
        sender_fragments=("noreply@discord.com",),
        older_than_days=3,
        dry_run=False,
        subject_fragments=("you missed messages",),
        required_label_ids=("CATEGORY_UPDATES",),
        now=now,
    ).outcome == "discord_missed_messages_skipped_subject"

    recent = _message(now - dt.timedelta(days=1), "Discord <noreply@discord.com>", "You missed messages")
    assert evaluate_sender_cleanup_message(
        recent,
        label="Discord Missed Messages",
        sender_fragments=("noreply@discord.com",),
        older_than_days=3,
        dry_run=False,
        now=now,
    ).outcome == "discord_missed_messages_too_recent"


def test_google_calendar_cleanup_decision_classifies_sender_event_date_and_dry_run():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)
    past_ics = "\n".join([
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

    past = _message(now - dt.timedelta(days=5), "Google Calendar <calendar-notification@google.com>", "Past", calendar_text=past_ics)
    decision = evaluate_google_calendar_cleanup_message(
        past,
        sender_fragments=("calendar-notification",),
        dry_run=True,
        now=now,
    )
    assert decision.outcome == "google_calendar_would_trash"
    assert decision.should_trash

    future = _message(now - dt.timedelta(days=5), "Google Calendar <calendar-notification@google.com>", "Future", calendar_text=future_ics)
    assert evaluate_google_calendar_cleanup_message(
        future,
        sender_fragments=("calendar-notification",),
        dry_run=False,
        now=now,
    ).outcome == "google_calendar_future_event"

    no_date = _message(now - dt.timedelta(days=5), "Google Calendar <calendar-notification@google.com>", "No date")
    assert evaluate_google_calendar_cleanup_message(
        no_date,
        sender_fragments=("calendar-notification",),
        dry_run=False,
        now=now,
    ).outcome == "google_calendar_no_event_date"

    wrong_sender = _message(now - dt.timedelta(days=5), "Sender <x@example.com>", "Past", calendar_text=past_ics)
    assert evaluate_google_calendar_cleanup_message(
        wrong_sender,
        sender_fragments=("calendar-notification",),
        dry_run=False,
        now=now,
    ).outcome == "google_calendar_skipped"


def test_unread_cleanup_decision_requires_unread_label_and_age():
    now = dt.datetime(2026, 6, 29, 12, 0, tzinfo=NY)

    old_unread = _message(now - dt.timedelta(days=30), "Sender <x@example.com>", "Old", labels=["UNREAD"])
    decision = evaluate_unread_cleanup_message(old_unread, older_than_days=21, dry_run=True, now=now)
    assert decision.outcome == "old_unread_would_trash"
    assert decision.should_trash

    old_read = _message(now - dt.timedelta(days=30), "Sender <x@example.com>", "Old read")
    assert evaluate_unread_cleanup_message(
        old_read,
        older_than_days=21,
        dry_run=False,
        now=now,
    ).outcome == "old_unread_skipped_read"

    young_unread = _message(now - dt.timedelta(days=5), "Sender <x@example.com>", "Young", labels=["UNREAD"])
    assert evaluate_unread_cleanup_message(
        young_unread,
        older_than_days=21,
        dry_run=False,
        now=now,
    ).outcome == "old_unread_too_recent"
