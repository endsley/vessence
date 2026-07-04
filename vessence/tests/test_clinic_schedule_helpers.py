from datetime import datetime
import re

from agent_skills.private_handler_utils import pending_continuation

from jane_web.jane_v2.classes.clinic_schedules_info import handler
from jane_web.jane_v2.classes.clinic_schedules_info.prompting import (
    SYSTEM_PROMPT,
    conversation_context_block,
    phrase_prompt,
    phrase_request_payload,
)
from jane_web.jane_v2.classes.clinic_schedules_info.responses import (
    build_clinic_pending,
    build_clinic_response,
    clinic_response_structured,
)
from jane_web.jane_v2.ollama_client import post_local_llm_response
from jane_web.jane_v2.classes.clinic_schedules_info.schedule_helpers import (
    WEEK_DAYS,
    active_patient_briefs,
    compute_next_patient,
    fmt_time,
    normalize_day,
    normalize_params,
    now_meta,
    parse_time,
    split_active_cancelled,
)


def test_handler_uses_extracted_schedule_helpers() -> None:
    assert handler._parse_time is parse_time
    assert handler._fmt_time is fmt_time
    assert handler._normalize_day is normalize_day
    assert handler._now_meta is now_meta
    assert handler._split_active_cancelled is split_active_cancelled
    assert handler._active_patient_briefs is active_patient_briefs
    assert handler._compute_next_patient is compute_next_patient
    assert handler._normalize_params is normalize_params
    assert handler._WEEK_DAYS is WEEK_DAYS
    assert handler._SYSTEM_PROMPT is SYSTEM_PROMPT
    assert handler._conversation_context_block is conversation_context_block
    assert handler._phrase_prompt is phrase_prompt
    assert handler._phrase_request_payload is phrase_request_payload
    assert handler._post_local_llm_response is post_local_llm_response
    assert handler._pending is build_clinic_pending
    assert handler._build_clinic_response is build_clinic_response


def test_clinic_pending_uses_shared_continuation_shape() -> None:
    assert build_clinic_pending.__globals__["_pending_continuation"] is pending_continuation
    pending = build_clinic_pending("clinic_followup")

    assert pending["type"] == "STAGE2_FOLLOWUP"
    assert pending["handler_class"] == "clinic schedules info"
    assert pending["awaiting"] == "clinic_followup"
    assert pending["question"] == "(awaiting:clinic_followup)"
    assert pending["data"] == {"awaiting": "clinic_followup"}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", pending["expires_at"])


def test_clinic_response_preserves_pending_shape() -> None:
    structured = clinic_response_structured()
    assert structured["intent"] == "clinic schedules info"
    assert structured["pending_action"]["awaiting"] == "clinic_followup"

    response = build_clinic_response("Grace is next.")

    assert response["text"] == "Grace is next."
    assert response["structured"]["intent"] == "clinic schedules info"
    assert response["structured"]["pending_action"]["awaiting"] == "clinic_followup"


def test_clinic_phrase_prompt_includes_context_facts_and_pending_state() -> None:
    structured = {
        "user_said": "who is next",
        "facts": {"loader": "next_patient", "next_patient": {"name": "Ava"}},
        "pending_state": {"awaiting": "clinic_followup"},
    }

    prompt = phrase_prompt(structured, "Jane: earlier")

    assert conversation_context_block(" Jane: earlier ") == "Recent conversation:\nJane: earlier\n\n"
    assert conversation_context_block(" ") == ""
    assert "Recent conversation:\nJane: earlier\n\nThe user just said: \"who is next\"" in prompt
    assert '"loader": "next_patient"' in prompt
    assert "Pending state from prior turn:" in prompt
    assert prompt.endswith("Reply (spoken text only):")


def test_clinic_phrase_request_payload_preserves_ollama_options() -> None:
    payload = phrase_request_payload(
        {"user_said": "weekly", "facts": {"loader": "weekly"}},
        "",
        model="qwen",
        num_ctx=4096,
        keep_alive="5m",
    )

    assert payload["model"] == "qwen"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"] == {"temperature": 0.2, "num_predict": 600, "num_ctx": 4096}
    assert payload["keep_alive"] == "5m"
    assert payload["prompt"].endswith("Reply (spoken text only):")


def test_time_formatting_and_parsing_accept_scrape_and_spoken_suffixes() -> None:
    assert fmt_time(" 9:15A ") == "9:15am"
    assert fmt_time("2:00p") == "2:00pm"
    assert parse_time("9:15a").strftime("%I:%M %p") == "09:15 AM"
    assert parse_time("9:15am").strftime("%I:%M %p") == "09:15 AM"
    assert parse_time("2:00 PM").strftime("%I:%M %p") == "02:00 PM"
    assert parse_time("not a time") == datetime.min


def test_day_normalization_and_now_meta_with_injected_clock() -> None:
    now = datetime(2026, 7, 2, 13, 5)
    assert normalize_day("today", now=now) == "Thursday"
    assert normalize_day("tomorrow", now=now) == "Friday"
    assert normalize_day(" monday ", now=now) == "Monday"
    assert normalize_day("next week", now=now) is None
    assert normalize_day(None, now=now) is None
    assert now_meta(now) == {"today": "Thursday", "current_time": "1:05 PM"}


def test_split_active_cancelled_assigns_visible_indexes_to_active_patients() -> None:
    rows = [
        {
            "name": "Ava",
            "time": "9:00am",
            "status": "active",
            "health_concerns": "neck",
            "recommendations": "stretch",
            "visit_summary": "first visit",
        },
        {
            "name": "Ben",
            "time": "10:00am",
            "status": "cancelled-out",
            "health_concerns": "shoulder",
            "recommendations": "rest",
            "visit_summary": "cancelled",
        },
        {
            "name": "Cam",
            "time": "11:00am",
            "status": "active",
            "health_concerns": None,
            "recommendations": None,
            "visit_summary": None,
        },
    ]

    active, cancelled = split_active_cancelled(rows)

    assert active == [
        {
            "index": 1,
            "name": "Ava",
            "time": "9:00am",
            "health_concerns": "neck",
            "recommendations": "stretch",
            "visit_summary": "first visit",
        },
        {
            "index": 2,
            "name": "Cam",
            "time": "11:00am",
            "health_concerns": None,
            "recommendations": None,
            "visit_summary": None,
        },
    ]
    assert cancelled == [{"name": "Ben", "time": "10:00am"}]


def test_active_patient_briefs_keeps_only_index_name_and_time() -> None:
    assert active_patient_briefs([
        {
            "index": 1,
            "name": "Ava",
            "time": "9:00am",
            "health_concerns": "neck",
        },
        {
            "index": 2,
            "name": "Cam",
            "time": "11:00am",
            "visit_summary": "follow-up",
        },
    ]) == [
        {"index": 1, "name": "Ava", "time": "9:00am"},
        {"index": 2, "name": "Cam", "time": "11:00am"},
    ]


def test_compute_next_patient_keeps_the_15_minute_late_buffer() -> None:
    now = datetime(2026, 7, 2, 10, 0)
    active = [
        {"name": "Too Late", "time": "9:44am"},
        {"name": "Grace", "time": "9:45am"},
        {"name": "Hiro", "time": "10:30am"},
        {"name": "Invalid", "time": "unknown"},
    ]

    assert compute_next_patient(active, now=now) == {
        "name": "Grace",
        "time": "9:45am",
        "minutes_from_now": -15,
    }
    assert compute_next_patient(active, now=now, late_buffer_minutes=0) == {
        "name": "Hiro",
        "time": "10:30am",
        "minutes_from_now": 30,
    }


def test_normalize_params_defaults_unknown_loaders_and_prioritizes_patient_detail() -> None:
    assert normalize_params(None) == {"loader": "today_overview"}
    assert normalize_params({"loader": "bogus"}) == {"loader": "today_overview"}
    assert normalize_params({"loader": "weekly"}) == {"loader": "weekly"}
    assert normalize_params({"loader": "day", "patient_index": 2}) == {
        "loader": "patient_detail",
        "patient_index": 2,
    }
    assert normalize_params({"loader": "next_patient", "patient_name": "Ava"}) == {
        "loader": "patient_detail",
        "patient_name": "Ava",
    }
