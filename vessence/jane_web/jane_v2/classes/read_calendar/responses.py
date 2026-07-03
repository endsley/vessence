"""Response builders for the read-calendar Stage 2 handler."""
from __future__ import annotations

from agent_skills.private_handler_utils import pending_continuation


INTENT = "read calendar"
DETAIL_FOLLOWUP = "Would you like to know the details of any particular event?"
ANOTHER_DAY_QUESTION = "Would you like to know about another day?"
DAY_CHOICE_QUESTION = "Which day?"
EVENT_CHOICE_QUESTION = "Which one?"
EVENT_PENDING_KEYS = ("id", "summary", "description", "start", "end", "html_link")


def build_calendar_pending(awaiting: str, question: str, data: dict | None = None) -> dict:
    return pending_continuation(
        handler_class=INTENT,
        awaiting=awaiting,
        question=question,
        data=data,
    )


def serialize_events_for_pending(events: list[dict]) -> list[dict]:
    return [{key: event.get(key, "") for key in EVENT_PENDING_KEYS} for event in events]


def build_range_followup_response(
    spoken: str,
    range_hint: str,
    events: list[dict] | None = None,
) -> dict:
    """After listing events, ask about details; if no events, ask about another day."""
    if events:
        question = DETAIL_FOLLOWUP
        awaiting = "event_detail_or_stop"
        data = {
            "last_range": range_hint,
            "events": serialize_events_for_pending(events),
        }
    else:
        question = ANOTHER_DAY_QUESTION
        awaiting = "another_day_or_stop"
        data = {"last_range": range_hint}

    return {
        "text": f"{spoken} {question}",
        "structured": {
            "intent": INTENT,
            "entities": {"range": range_hint},
            "pending_action": build_calendar_pending(awaiting, question, data),
        },
    }


def build_event_detail_response(text: str, event: dict, last_range: str) -> dict:
    return {
        "text": f"{text} {ANOTHER_DAY_QUESTION}",
        "structured": {
            "intent": INTENT,
            "entities": {"event_id": event.get("id")},
            "pending_action": build_calendar_pending(
                "another_day_or_stop",
                ANOTHER_DAY_QUESTION,
                {"last_range": last_range},
            ),
        },
    }


def build_another_day_response(last_range: str) -> dict:
    return {
        "text": ANOTHER_DAY_QUESTION,
        "structured": {
            "intent": INTENT,
            "pending_action": build_calendar_pending(
                "another_day_or_stop",
                ANOTHER_DAY_QUESTION,
                {"last_range": last_range},
            ),
        },
    }


def build_event_choice_response(last_range: str, events: list[dict]) -> dict:
    return {
        "text": EVENT_CHOICE_QUESTION,
        "structured": {
            "intent": INTENT,
            "pending_action": build_calendar_pending(
                "awaiting_event_choice",
                EVENT_CHOICE_QUESTION,
                {"last_range": last_range, "events": events},
            ),
        },
    }


def build_day_choice_response() -> dict:
    return {
        "text": DAY_CHOICE_QUESTION,
        "structured": {
            "intent": INTENT,
            "pending_action": build_calendar_pending(
                "awaiting_day_choice",
                DAY_CHOICE_QUESTION,
            ),
        },
    }
