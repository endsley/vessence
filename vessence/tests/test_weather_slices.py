import asyncio
from datetime import date
import re

from agent_skills.private_handler_utils import pending_continuation

from jane_web.jane_v2.classes.weather import handler
from jane_web.jane_v2.classes.weather.phrasing import (
    ANSWER_TEMPLATE,
    weather_answer_prompt,
    weather_phrase_payload,
)
from jane_web.jane_v2.classes.weather.responses import (
    WEATHER_FOLLOWUP_QUESTION,
    build_weather_followup_response,
)
from jane_web.jane_v2.classes.weather.slices import (
    DAY_PHRASE_MAP,
    MULTI_DAY_SPECS,
    NEUTRAL_DAY_REFS,
    VALID_TOPICS,
    WEEKDAYS,
    air_quality_slice,
    current_weather_slice,
    day_from_followup,
    day_reference,
    ensure_day_reference,
    forecast_slice,
    is_multi_day_spec,
    normalize_day,
    precipitation_day_payload,
    precipitation_entries,
    precipitation_slice,
    pollen_slice,
    slice_for,
    overview_weather_slice,
    weekly_forecast_day_payload,
    without_debug_fields,
    wind_slice,
)
from jane_web.jane_v2.ollama_client import post_local_llm_response


def _forecast() -> list[dict]:
    return [
        {
            "date": f"2026-07-{day:02d}",
            "weekday": weekday,
            "high": 80 + index,
            "low": 60 + index,
            "condition": f"{weekday} clear",
            "precipitation": {"chance": index * 10},
            "wind": {"speed": index + 5},
            "debug_raw": "drop me",
        }
        for index, (day, weekday) in enumerate(
            [
                (2, "Thursday"),
                (3, "Friday"),
                (4, "Saturday"),
                (5, "Sunday"),
                (6, "Monday"),
                (7, "Tuesday"),
                (8, "Wednesday"),
                (9, "Thursday"),
            ]
        )
    ]


def _weather_data() -> dict:
    return {
        "forecast": _forecast(),
        "current": {"temperature": 75, "condition": "clear", "debug_station": "drop"},
        "air_quality": {"us_aqi": 35, "aqi": 40},
        "pollen": {"tree": "low"},
    }


def test_handler_uses_extracted_weather_slice_helpers() -> None:
    assert handler._DAY_PHRASE_MAP is DAY_PHRASE_MAP
    assert handler._NEUTRAL_DAY_REFS is NEUTRAL_DAY_REFS
    assert handler._VALID_TOPICS is VALID_TOPICS
    assert handler._WEEKDAYS is WEEKDAYS
    assert handler._day_from_followup is day_from_followup
    assert handler._normalize_day is normalize_day
    assert handler._without_debug_fields is without_debug_fields
    assert handler._slice_for is slice_for
    assert handler._day_reference is day_reference
    assert handler._ensure_day_reference is ensure_day_reference
    assert handler._ANSWER_TEMPLATE is ANSWER_TEMPLATE
    assert handler._weather_answer_prompt is weather_answer_prompt
    assert handler._weather_phrase_payload is weather_phrase_payload
    assert handler._wrap_with_followup is build_weather_followup_response
    assert handler._post_local_llm_response is post_local_llm_response


def test_weather_followup_uses_shared_pending_continuation_shape() -> None:
    assert build_weather_followup_response.__globals__["_pending_continuation"] is pending_continuation
    result = build_weather_followup_response("It's clear.", "overview", None)

    assert result["text"] == f"It's clear. {WEATHER_FOLLOWUP_QUESTION}"
    pending = result["structured"]["pending_action"]
    assert pending["type"] == "STAGE2_FOLLOWUP"
    assert pending["handler_class"] == "weather"
    assert pending["awaiting"] == "another_day_or_stop"
    assert pending["question"] == WEATHER_FOLLOWUP_QUESTION
    assert pending["data"] == {
        "topic": "overview",
        "location": "",
        "awaiting": "another_day_or_stop",
    }
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", pending["expires_at"])


def test_weather_pending_helpers_accept_nested_payloads_and_medford_only() -> None:
    nested = {"data": {"topic": "Forecast", "location": "Medford, MA"}}

    assert handler._pending_payload(nested) == {"topic": "Forecast", "location": "Medford, MA"}
    assert handler._pending_weather_fields(nested) == ("forecast", "medford, ma")
    assert handler._pending_weather_fields({"topic": "wind", "location": ""}) == ("wind", "")
    assert handler._pending_weather_fields({"data": "bad"}) is None
    assert handler._pending_weather_fields({"data": {"topic": "wind", "location": "Boston"}}) is None
    assert handler._abandon_to_stage3() == {"abandon_pending": True, "force_stage3": True}


def test_weather_pending_handler_replays_answer_for_followup_day(monkeypatch) -> None:
    captured = {}

    async def fake_answer(prompt, topic, day, location):
        captured.update({"prompt": prompt, "topic": topic, "day": day, "location": location})
        return {"text": "Saturday looks clear."}

    monkeypatch.setattr(handler, "_day_from_followup", lambda prompt: "saturday")
    monkeypatch.setattr(handler, "_answer_for", fake_answer)

    result = asyncio.run(
        handler._handle_pending_weather(
            "Saturday",
            {"data": {"topic": "forecast", "location": "Medford"}},
        )
    )

    assert result == {"text": "Saturday looks clear."}
    assert captured == {
        "prompt": "Saturday",
        "topic": "forecast",
        "day": "saturday",
        "location": "medford",
    }


def test_weather_answer_prompt_and_payload_preserve_phrase_request_shape() -> None:
    slice_obj = {"topic": "day_forecast", "day": {"date": "2026-07-04", "weekday": "Saturday"}}

    prompt = weather_answer_prompt(slice_obj, "How hot?", today=date(2026, 7, 2))

    assert 'refer to this day as "Saturday"' in prompt
    assert '"topic": "day_forecast"' in prompt
    assert "User question: How hot?" in prompt
    assert prompt.endswith("Your 1-sentence spoken answer:")

    payload = weather_phrase_payload(
        slice_obj,
        "How hot?",
        model="qwen",
        num_ctx=4096,
        keep_alive="5m",
        today=date(2026, 7, 2),
    )
    assert payload["model"] == "qwen"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"] == {"temperature": 0.2, "num_predict": 60, "num_ctx": 4096}
    assert payload["keep_alive"] == "5m"


def test_day_from_followup_maps_common_short_replies() -> None:
    today = date(2026, 7, 2)
    assert day_from_followup("day after tomorrow", today=today) == "2026-07-04"
    assert day_from_followup("and tomorrow?", today=today) == "tomorrow"
    assert day_from_followup("tonight", today=today) == "today"
    assert day_from_followup("this week please", today=today) == "this_week"
    assert day_from_followup("never mind", today=today) is None


def test_normalize_day_matches_relative_weekday_and_iso_specs() -> None:
    today = date(2026, 7, 2)
    forecast = _forecast()

    assert normalize_day("today", forecast, today=today) is forecast[0]
    assert normalize_day("tomorrow", forecast, today=today) is forecast[1]
    assert normalize_day("friday", forecast, today=today) is forecast[1]
    assert normalize_day("2026-07-03 please", forecast, today=today) is forecast[1]
    assert normalize_day("weekend", forecast, today=today) is None
    assert normalize_day("nonsense", forecast, today=today) is None


def test_weather_multi_day_and_slim_day_payload_helpers() -> None:
    forecast = _forecast()

    assert MULTI_DAY_SPECS == {"this_week", "weekend", "week"}
    assert is_multi_day_spec("weekend")
    assert is_multi_day_spec("this_week")
    assert not is_multi_day_spec("tomorrow")
    assert not is_multi_day_spec(None)
    assert precipitation_entries(forecast[2], forecast, multi_day=False) == [forecast[2]]
    assert precipitation_entries(None, forecast, multi_day=False) == forecast[:3]
    assert precipitation_entries(forecast[2], forecast, multi_day=True) == forecast[:7]
    assert precipitation_day_payload(forecast[1]) == {
        "weekday": "Friday",
        "date": "2026-07-03",
        "precipitation": {"chance": 10},
        "condition": "Friday clear",
    }
    assert weekly_forecast_day_payload(forecast[1]) == {
        "weekday": "Friday",
        "high": 81,
        "low": 61,
        "condition": "Friday clear",
    }


def test_slice_for_builds_minimal_forecast_precipitation_and_overview_payloads() -> None:
    data = _weather_data()

    assert pollen_slice(data["pollen"]) == {"topic": "pollen", "pollen": {"tree": "low"}}
    assert pollen_slice(None) is None
    assert air_quality_slice(data["air_quality"]) == {
        "topic": "air_quality",
        "air_quality": {"us_aqi": 35, "aqi": 40},
    }
    assert wind_slice(data["forecast"][1], data["current"]) == {
        "topic": "wind",
        "day": "Friday",
        "wind": {"speed": 6},
    }
    assert wind_slice(None, {"wind": {"speed": 5}}) == {
        "topic": "wind",
        "current_wind": {"speed": 5},
    }
    assert slice_for("forecast", "2026-07-03", data) == {
        "topic": "day_forecast",
        "day": {
            "date": "2026-07-03",
            "weekday": "Friday",
            "high": 81,
            "low": 61,
            "condition": "Friday clear",
            "precipitation": {"chance": 10},
            "wind": {"speed": 6},
        },
    }
    assert forecast_slice(data["forecast"][1], data["forecast"], multi_day=False) == {
        "topic": "day_forecast",
        "day": {
            "date": "2026-07-03",
            "weekday": "Friday",
            "high": 81,
            "low": 61,
            "condition": "Friday clear",
            "precipitation": {"chance": 10},
            "wind": {"speed": 6},
        },
    }
    assert slice_for("forecast", "this_week", data) == {
        "topic": "weekly_forecast",
        "days": [
            {"weekday": entry["weekday"], "high": entry["high"], "low": entry["low"], "condition": entry["condition"]}
            for entry in data["forecast"][:7]
        ],
    }
    assert forecast_slice(None, data["forecast"], multi_day=True) == slice_for("forecast", "this_week", data)
    assert slice_for("precipitation", None, data) == {
        "topic": "precipitation",
        "days": [
            {
                "weekday": entry["weekday"],
                "date": entry["date"],
                "precipitation": entry["precipitation"],
                "condition": entry["condition"],
            }
            for entry in data["forecast"][:3]
        ],
    }
    assert precipitation_slice(None, data["forecast"], multi_day=False) == slice_for("precipitation", None, data)
    assert slice_for("overview", None, data) == {
        "topic": "overview",
        "current": {"temperature": 75, "condition": "clear"},
        "today": {
            "date": "2026-07-02",
            "weekday": "Thursday",
            "high": 80,
            "low": 60,
            "condition": "Thursday clear",
            "precipitation": {"chance": 0},
            "wind": {"speed": 5},
        },
        "air_quality_aqi": 35,
    }
    assert current_weather_slice(data["current"], data["forecast"]) == {
        "topic": "current",
        "current": {"temperature": 75, "condition": "clear"},
        "today": {
            "date": "2026-07-02",
            "weekday": "Thursday",
            "high": 80,
            "low": 60,
            "condition": "Thursday clear",
            "precipitation": {"chance": 0},
            "wind": {"speed": 5},
        },
    }
    assert overview_weather_slice(data["current"], data["forecast"], data["air_quality"]) == (
        slice_for("overview", None, data)
    )
    assert slice_for("pollen", None, {**data, "pollen": None}) is None


def test_day_reference_uses_injected_today_for_single_and_multi_day_slices() -> None:
    today = date(2026, 7, 2)
    assert day_reference({"day": {"date": "2026-07-02", "weekday": "Thursday"}}, today=today) == "today"
    assert day_reference({"day": {"date": "2026-07-03", "weekday": "Friday"}}, today=today) == "tomorrow"
    assert day_reference({"day": {"date": "2026-07-04", "weekday": "Saturday"}}, today=today) == "Saturday"
    assert day_reference({"days": [{"date": "2026-07-03", "weekday": "Friday"}]}, today=today) == "tomorrow"
    assert day_reference({"days": [{"date": "2026-07-03"}, {"date": "2026-07-04"}]}, today=today) == (
        "the next several days"
    )
    assert day_reference({"topic": "air_quality"}, today=today) == "today"


def test_ensure_day_reference_prepends_non_neutral_missing_days() -> None:
    assert ensure_day_reference("High around 60.", "Saturday") == "Saturday: high around 60."
    assert ensure_day_reference("Saturday looks clear.", "Saturday") == "Saturday looks clear."
    assert ensure_day_reference("It's clear.", "today") == "It's clear."
    assert ensure_day_reference("A few rainy days.", "the next several days") == "A few rainy days."
