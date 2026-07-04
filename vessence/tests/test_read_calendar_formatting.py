import asyncio
from datetime import date, datetime

from jane_web.jane_v2.classes.read_calendar import handler
from jane_web.jane_v2.classes.read_calendar.formatting import (
    RANGE_PATTERNS,
    format_event_detail,
    format_time,
    match_event,
    resolve_range,
    simplify_events,
)
from jane_web.jane_v2.classes.read_calendar.responses import (
    ANOTHER_DAY_QUESTION,
    DAY_CHOICE_QUESTION,
    DETAIL_FOLLOWUP,
    build_another_day_response,
    build_calendar_pending,
    build_day_choice_response,
    build_event_choice_response,
    build_event_detail_response,
    build_range_followup_response,
    last_range_pending_data,
    range_events_pending_data,
    serialize_events_for_pending,
)


def run(coro):
    return asyncio.run(coro)


def test_handler_uses_extracted_calendar_formatting_helpers() -> None:
    assert handler._RANGE_PATTERNS is RANGE_PATTERNS
    assert handler._format_time is format_time
    assert handler._simplify_events is simplify_events
    assert handler._resolve_range is resolve_range
    assert handler._match_event is match_event
    assert handler._format_event_detail is format_event_detail
    assert handler._pending is build_calendar_pending
    assert handler._wrap_with_followup is build_range_followup_response
    assert handler._ask_another_day is build_another_day_response


def test_calendar_pending_helpers_preserve_nested_state_and_malformed_fallbacks() -> None:
    pending = {
        "data": {
            "awaiting": "event_detail_or_stop",
            "events": [{"id": "e1"}],
            "last_range": "tomorrow",
        }
    }

    assert handler._calendar_pending_data(pending) == pending["data"]
    assert handler._calendar_awaiting(pending) == "event_detail_or_stop"
    assert handler._calendar_events_and_last_range(pending) == ([{"id": "e1"}], "tomorrow")
    assert handler._calendar_awaiting({"awaiting": "another_day_or_stop"}) == (
        "another_day_or_stop"
    )
    assert handler._calendar_pending_data({"data": "bad"}) == {}
    assert handler._calendar_events_and_last_range({"data": {"events": "bad"}}) == ([], "today")
    assert handler._abandon_to_stage3() == {"abandon_pending": True, "force_stage3": True}


def test_calendar_resume_end_signal_helpers_preserve_terminal_shape() -> None:
    assert handler._is_calendar_end_signal("no")
    assert handler._is_calendar_end_signal("stop")
    assert not handler._is_calendar_end_signal("tomorrow")
    assert handler._end_calendar_conversation() == {
        "text": "Ok.",
        "conversation_end": True,
        "structured": {"intent": "read calendar"},
    }


def test_calendar_event_detail_resume_helper_routes_detail_choice_day_and_fallback(monkeypatch) -> None:
    async def fake_show_event_detail(event, last_range):
        return {"text": f"detail {event['id']} {last_range}"}

    async def fake_answer_for_range(prompt, range_hint):
        return {"text": f"range {range_hint}", "prompt": prompt}

    monkeypatch.setattr(handler, "_show_event_detail", fake_show_event_detail)
    monkeypatch.setattr(handler, "_answer_for_range", fake_answer_for_range)

    events = [
        {"id": "e1", "summary": "Doctor Appointment"},
        {"id": "e2", "summary": "Dinner with Lee"},
    ]

    assert run(handler._handle_event_detail_or_stop("yes", [events[0]], "today")) == {
        "text": "detail e1 today"
    }

    choice = run(handler._handle_event_detail_or_stop("yes", events, "today"))
    assert choice["text"] == "Which one?"
    assert choice["structured"]["pending_action"]["awaiting"] == "awaiting_event_choice"

    assert run(handler._handle_event_detail_or_stop("tell me about 2", events, "today")) == {
        "text": "detail e2 today"
    }
    assert run(handler._handle_event_detail_or_stop("tomorrow", events, "today")) == {
        "text": "range tomorrow",
        "prompt": "tomorrow",
    }

    fallback = run(handler._handle_event_detail_or_stop("something else", events, "today"))
    assert fallback["text"] == ANOTHER_DAY_QUESTION
    assert fallback["structured"]["pending_action"]["awaiting"] == "another_day_or_stop"


def test_calendar_choice_and_day_resume_helpers_route_or_escalate(monkeypatch) -> None:
    async def fake_show_event_detail(event, last_range):
        return {"text": f"detail {event['id']} {last_range}"}

    async def fake_answer_for_range(prompt, range_hint):
        return {"text": f"range {range_hint}", "prompt": prompt}

    monkeypatch.setattr(handler, "_show_event_detail", fake_show_event_detail)
    monkeypatch.setattr(handler, "_answer_for_range", fake_answer_for_range)

    events = [{"id": "e1", "summary": "Dentist"}]

    assert run(handler._handle_event_choice_reply("dentist details", events, "today")) == {
        "text": "detail e1 today"
    }
    event_fallback = run(handler._handle_event_choice_reply("wrong one", events, "today"))
    assert event_fallback["text"] == ANOTHER_DAY_QUESTION

    assert run(handler._handle_another_day_or_stop("next week")) == {
        "text": "range next week",
        "prompt": "next week",
    }
    assert run(handler._handle_another_day_or_stop("yes"))["text"] == DAY_CHOICE_QUESTION
    assert run(handler._handle_another_day_or_stop("maybe")) == {
        "abandon_pending": True,
        "force_stage3": True,
    }

    assert run(handler._handle_day_choice_reply("friday")) == {
        "text": "range friday",
        "prompt": "friday",
    }
    assert run(handler._handle_day_choice_reply("maybe")) == {
        "abandon_pending": True,
        "force_stage3": True,
    }


def test_resolve_range_accepts_specific_days_and_weeks_only() -> None:
    assert resolve_range("what is on my calendar today") == "today"
    assert resolve_range("anything tonight?") == "today"
    assert resolve_range("what about next week") == "next week"
    assert resolve_range("show me Friday") == "friday"
    assert resolve_range("what is coming up") is None


def test_format_time_and_simplify_events_render_readable_summary() -> None:
    assert format_time(datetime(2026, 7, 2, 9, 0)) == "9am"
    assert format_time(datetime(2026, 7, 2, 10, 30)) == "10:30am"

    events = [
        {
            "summary": "Dentist",
            "start": "2026-07-02T09:00:00",
            "end": "2026-07-02T10:30:00",
        },
        {
            "summary": "",
            "start": "2026-07-03",
            "end": "",
        },
        {
            "start": "unknown",
            "end": "",
        },
    ]

    assert simplify_events(events, date(2026, 7, 2)) == (
        "Total: 3 events\n\n"
        "1. Dentist — Thursday July 2, 9am–10:30am\n"
        "2. Untitled — Friday July 3 (all day)\n"
        "3. Untitled — unknown (all day)"
    )
    assert simplify_events([], date(2026, 7, 2)) == "No events."


def test_match_event_uses_number_then_summary_keywords() -> None:
    events = [
        {"summary": "Doctor Appointment"},
        {"summary": "Dinner with Lee"},
    ]

    assert match_event("tell me about 2", events) is events[1]
    assert match_event("doctor details", events) is events[0]
    assert match_event("something else", events) is None


def test_format_event_detail_includes_time_and_description() -> None:
    description = "Bring insurance card. " * 30
    assert format_event_detail({
        "summary": "Dentist",
        "start": "2026-07-02T09:00:00",
        "end": "2026-07-02T10:30:00",
        "description": description,
    }) == "\n".join([
        "Name: Dentist",
        "Day: Thursday July 2",
        "Time: 9am",
        "End: 10:30am",
        f"Description: {description[:300]}",
    ])
    assert format_event_detail({"summary": "", "start": "2026-07-03"}) == "\n".join([
        "Name: Untitled",
        "Day: 2026-07-03 (all day)",
        "Description: none",
    ])


def test_calendar_range_followup_response_serializes_events_for_pending() -> None:
    events = [
        {
            "id": "e1",
            "summary": "Dentist",
            "description": "Bring card",
            "start": "2026-07-02T09:00:00",
            "end": "2026-07-02T10:00:00",
            "html_link": "https://example.test/event",
            "extra": "ignored",
        }
    ]

    response = build_range_followup_response("You have one thing.", "today", events)
    pending = response["structured"]["pending_action"]

    assert serialize_events_for_pending(events) == [
        {
            "id": "e1",
            "summary": "Dentist",
            "description": "Bring card",
            "start": "2026-07-02T09:00:00",
            "end": "2026-07-02T10:00:00",
            "html_link": "https://example.test/event",
        }
    ]
    assert last_range_pending_data("today") == {"last_range": "today"}
    assert range_events_pending_data("today", [{"id": "e1"}]) == {
        "last_range": "today",
        "events": [{"id": "e1"}],
    }
    assert response["text"] == f"You have one thing. {DETAIL_FOLLOWUP}"
    assert response["structured"]["entities"] == {"range": "today"}
    assert pending["handler_class"] == "read calendar"
    assert pending["awaiting"] == "event_detail_or_stop"
    assert pending["question"] == DETAIL_FOLLOWUP
    assert pending["data"] == {
        "last_range": "today",
        "events": serialize_events_for_pending(events),
        "awaiting": "event_detail_or_stop",
    }


def test_calendar_no_event_and_choice_followups_preserve_pending_shapes() -> None:
    no_events = build_range_followup_response("You're clear.", "tomorrow", [])
    pending = no_events["structured"]["pending_action"]
    assert no_events["text"] == f"You're clear. {ANOTHER_DAY_QUESTION}"
    assert pending["awaiting"] == "another_day_or_stop"
    assert pending["data"] == {"last_range": "tomorrow", "awaiting": "another_day_or_stop"}

    detail = build_event_detail_response("Dentist is at 9am.", {"id": "e1"}, "today")
    assert detail["text"] == f"Dentist is at 9am. {ANOTHER_DAY_QUESTION}"
    assert detail["structured"]["entities"] == {"event_id": "e1"}
    assert detail["structured"]["pending_action"]["data"] == {
        "last_range": "today",
        "awaiting": "another_day_or_stop",
    }

    another = build_another_day_response("today")
    assert another["text"] == ANOTHER_DAY_QUESTION
    assert another["structured"]["pending_action"]["data"] == {
        "last_range": "today",
        "awaiting": "another_day_or_stop",
    }


def test_calendar_event_and_day_choice_responses_preserve_questions() -> None:
    events = [{"id": "e1"}]
    event_choice = build_event_choice_response("today", events)
    assert event_choice["text"] == "Which one?"
    assert event_choice["structured"]["pending_action"]["data"] == {
        "last_range": "today",
        "events": events,
        "awaiting": "awaiting_event_choice",
    }

    day_choice = build_day_choice_response()
    assert day_choice["text"] == DAY_CHOICE_QUESTION
    assert day_choice["structured"]["pending_action"]["data"] == {
        "awaiting": "awaiting_day_choice",
    }
