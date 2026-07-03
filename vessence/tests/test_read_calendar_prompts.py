from datetime import date

from jane_web.jane_v2.classes.read_calendar import handler
from jane_web.jane_v2.classes.read_calendar.prompts import (
    ANSWER_TEMPLATE,
    DETAIL_TEMPLATE,
    ESCALATE_RE,
    FORCE_ESCALATE_PHRASES,
    build_calendar_answer_prompt,
    build_event_detail_prompt,
    calendar_llm_payload,
    response_requests_escalation,
    should_force_calendar_escalate,
)
from jane_web.jane_v2.ollama_client import post_local_llm_response


def test_calendar_handler_uses_extracted_prompt_helpers() -> None:
    assert handler._ANSWER_TEMPLATE is ANSWER_TEMPLATE
    assert handler._DETAIL_TEMPLATE is DETAIL_TEMPLATE
    assert handler._ESCALATE_RE is ESCALATE_RE
    assert handler._FORCE_ESCALATE_PHRASES is FORCE_ESCALATE_PHRASES
    assert handler._build_calendar_answer_prompt is build_calendar_answer_prompt
    assert handler._build_event_detail_prompt is build_event_detail_prompt
    assert handler._calendar_llm_payload is calendar_llm_payload
    assert handler._response_requests_escalation is response_requests_escalation
    assert handler._should_force_calendar_escalate is should_force_calendar_escalate
    assert handler._post_local_llm_response is post_local_llm_response


def test_build_calendar_answer_prompt_preserves_template_slots() -> None:
    prompt = build_calendar_answer_prompt(
        "Total: 1 event\n\n1. Dentist - Thursday July 2, 9am",
        "what is on my calendar today",
        date(2026, 7, 2),
    )

    assert "Today is Thursday, July 02, 2026." in prompt
    assert "Calendar summary:\nTotal: 1 event" in prompt
    assert "User question: what is on my calendar today" in prompt
    assert "Only respond with the single word ESCALATE" in prompt


def test_event_detail_prompt_and_escalation_helpers() -> None:
    assert build_event_detail_prompt("Name: Dentist\nDescription: none").endswith(
        "Name: Dentist\nDescription: none\n\nYour spoken answer:"
    )

    assert response_requests_escalation("ESCALATE")
    assert response_requests_escalation("please escalate this")
    assert not response_requests_escalation("You're clear today.")

    assert should_force_calendar_escalate("Can you reschedule my dentist visit?")
    assert should_force_calendar_escalate("Please add a calendar event")
    assert not should_force_calendar_escalate("What's on my calendar today?")


def test_calendar_llm_payload_preserves_generation_options() -> None:
    assert calendar_llm_payload(
        "prompt",
        model="qwen",
        num_predict=100,
        num_ctx=4096,
        keep_alive="5m",
    ) == {
        "model": "qwen",
        "prompt": "prompt",
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 100, "num_ctx": 4096},
        "keep_alive": "5m",
    }
