import asyncio
import json
import re
import sys
import types
from datetime import timedelta
from pathlib import Path

import pytest

from jane_web.jane_v2 import classes as class_registry
from jane_web.jane_v2.classes.weather import handler as weather_handler
from jane_web.jane_v2.classes.weather import metadata as weather_metadata


MODULE_PATH = Path("/home/chieh/ambient/vessence/jane_web/jane_v2/classes/weather/handler.py")
CLASSES_DIR = Path("/home/chieh/ambient/vessence/jane_web/jane_v2/classes")
PIPELINE_PATH = Path("/home/chieh/ambient/vessence/jane_web/jane_v2/pipeline.py")


def _run(coro):
    return asyncio.run(coro)


def _weather_data(days=7, include_pollen=True):
    today = weather_handler.date.today()
    forecast = []
    for offset in range(days):
        day = today + timedelta(days=offset)
        forecast.append(
            {
                "date": day.isoformat(),
                "weekday": day.strftime("%A"),
                "high": 70 + offset,
                "low": 50 + offset,
                "condition": "partly cloudy" if offset else "clear",
                "precipitation": {
                    "chance": 10 + offset,
                    "amount": round(0.01 * offset, 2),
                },
                "wind": {"speed_mph": 8 + offset, "gust_mph": 12 + offset},
                "humidity": {"min": 40, "max": 70},
                "uv_index": 4,
                "debug_full_cache_marker": f"forecast-marker-{offset}",
            }
        )

    data = {
        "current": {
            "temperature": 61.4,
            "feels_like": 58.9,
            "humidity": 54,
            "wind": {"speed_mph": 9, "gust_mph": 15},
            "condition": "clear",
            "debug_full_cache_marker": "current-marker",
        },
        "forecast": forecast,
        "air_quality": {"us_aqi": 35, "pm25": 7.5, "pm10": 12.2},
    }
    if include_pollen:
        data["pollen"] = {"tree": "low", "grass": "moderate", "weed": "low"}
    return data


@pytest.fixture
def weather_cache(tmp_path, monkeypatch):
    path = tmp_path / "weather.json"
    path.write_text(json.dumps(_weather_data()))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path)
    return path


@pytest.fixture
def phrase_stub(monkeypatch):
    calls = []

    async def fake_phrase(slice_obj, prompt):
        calls.append({"slice": slice_obj, "prompt": prompt})
        return "Mock weather answer."

    monkeypatch.setattr(weather_handler, "_phrase", fake_phrase)
    return calls


def test_handle_success_returns_text_and_stage2_followup(weather_cache, phrase_stub):
    result = _run(
        weather_handler.handle(
            "what's the weather",
            params={"topic": "overview", "day": None, "location": "Medford, MA"},
        )
    )

    assert isinstance(result, dict)
    assert result["text"] == "Mock weather answer. Want the weather for another day?"
    pending = result["structured"]["pending_action"]
    assert pending["type"] == "STAGE2_FOLLOWUP"
    assert pending["handler_class"] == "weather"
    assert pending["awaiting"] == "another_day_or_stop"
    assert pending["data"] == {
        "awaiting": "another_day_or_stop",
        "topic": "overview",
        "location": "medford, ma",
    }
    assert pending["expires_at"].endswith("Z")
    assert phrase_stub[0]["slice"]["topic"] == "overview"


@pytest.mark.parametrize(
    "prompt",
    [
        "can you look it up online",
        "what's causing this rain",
        "latest on the storm",
        "search the web for the forecast",
    ],
)
def test_research_or_online_questions_escalate_without_cache_or_llm(monkeypatch, prompt):
    async def answer_for_should_not_run(*args, **kwargs):
        raise AssertionError("_answer_for should not run for forced escalation")

    monkeypatch.setattr(weather_handler, "_answer_for", answer_for_should_not_run)

    assert _run(weather_handler.handle(prompt, params={"topic": "overview"})) is None


@pytest.mark.parametrize("location", ["Tokyo", "Somerville", "San Francisco, CA"])
def test_non_medford_locations_escalate_without_cache_or_llm(monkeypatch, location):
    async def answer_for_should_not_run(*args, **kwargs):
        raise AssertionError("_answer_for should not run for non-Medford locations")

    monkeypatch.setattr(weather_handler, "_answer_for", answer_for_should_not_run)

    result = _run(
        weather_handler.handle(
            "what's the weather there",
            params={"topic": "current", "location": location},
        )
    )
    assert result is None


@pytest.mark.parametrize("prompt", ["", None, "weather " + ("very " * 5000)])
def test_empty_none_and_very_long_prompts_are_handled_when_weather_was_routed(
    weather_cache, phrase_stub, prompt
):
    result = _run(weather_handler.handle(prompt, params={"topic": "overview"}))

    assert isinstance(result, dict)
    assert "text" in result
    assert result["text"].startswith("Mock weather answer.")
    assert phrase_stub[0]["prompt"] == prompt


def test_malformed_topic_falls_back_to_overview(weather_cache, phrase_stub):
    result = _run(
        weather_handler.handle(
            "weather please",
            params={"topic": "not-a-real-topic", "day": "%%%"},
        )
    )

    assert isinstance(result, dict)
    assert phrase_stub[0]["slice"]["topic"] == "overview"


def test_unreadable_cache_escalates_before_llm(tmp_path, monkeypatch):
    missing = tmp_path / "missing-weather.json"
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", missing)

    async def phrase_should_not_run(*args, **kwargs):
        raise AssertionError("_phrase should not run when the cache is missing")

    monkeypatch.setattr(weather_handler, "_phrase", phrase_should_not_run)

    assert _run(weather_handler._answer_for("weather", "overview", None, None)) is None


def test_malformed_cache_escalates_before_llm(tmp_path, monkeypatch):
    path = tmp_path / "weather.json"
    path.write_text("{not valid json")
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path)

    async def phrase_should_not_run(*args, **kwargs):
        raise AssertionError("_phrase should not run when the cache is malformed")

    monkeypatch.setattr(weather_handler, "_phrase", phrase_should_not_run)

    assert _run(weather_handler._answer_for("weather", "overview", None, None)) is None


def test_pollen_cache_miss_escalates(weather_cache, monkeypatch):
    weather_cache.write_text(json.dumps(_weather_data(include_pollen=False)))

    async def phrase_should_not_run(*args, **kwargs):
        raise AssertionError("_phrase should not run when pollen is missing")

    monkeypatch.setattr(weather_handler, "_phrase", phrase_should_not_run)

    assert _run(weather_handler._answer_for("pollen?", "pollen", None, None)) is None


def test_empty_llm_answer_escalates(weather_cache, monkeypatch):
    async def empty_phrase(*args, **kwargs):
        return ""

    monkeypatch.setattr(weather_handler, "_phrase", empty_phrase)

    assert _run(weather_handler._answer_for("weather", "overview", None, None)) is None


@pytest.mark.parametrize(
    "day_spec,expected_offset",
    [
        ("today", 0),
        ("tomorrow", 1),
    ],
)
def test_normalize_day_today_and_tomorrow(day_spec, expected_offset):
    data = _weather_data()
    expected = (
        weather_handler.date.today() + timedelta(days=expected_offset)
    ).isoformat()

    assert weather_handler._normalize_day(day_spec, data["forecast"])["date"] == expected


def test_normalize_day_accepts_weekday_and_iso_date():
    data = _weather_data()
    target_entry = data["forecast"][3]
    weekday = target_entry["weekday"].lower()

    assert weather_handler._normalize_day(weekday, data["forecast"]) == target_entry
    assert weather_handler._normalize_day(target_entry["date"], data["forecast"]) == target_entry


@pytest.mark.parametrize("day_spec", [None, "", "not-a-day", "2026-99-99", "this_week", "weekend"])
def test_normalize_day_returns_none_for_missing_multi_day_or_invalid_specs(day_spec):
    assert weather_handler._normalize_day(day_spec, _weather_data()["forecast"]) is None


@pytest.mark.parametrize(
    "topic,day_spec,expected_shape",
    [
        ("pollen", None, {"topic", "pollen"}),
        ("air_quality", None, {"topic", "air_quality"}),
        ("wind", "tomorrow", {"topic", "day", "wind"}),
        ("wind", None, {"topic", "current_wind"}),
        ("precipitation", "tomorrow", {"topic", "days"}),
        ("precipitation", "this_week", {"topic", "days"}),
        ("forecast", "tomorrow", {"topic", "day"}),
        ("forecast", "this_week", {"topic", "days"}),
        ("current", None, {"topic", "current", "today"}),
        ("overview", None, {"topic", "current", "today", "air_quality_aqi"}),
    ],
)
def test_slice_for_builds_small_documented_fact_slices(topic, day_spec, expected_shape):
    slice_obj = weather_handler._slice_for(topic, day_spec, _weather_data())

    assert isinstance(slice_obj, dict)
    assert set(slice_obj) == expected_shape
    assert "debug_full_cache_marker" not in json.dumps(slice_obj)


def test_precipitation_default_slice_is_today_plus_next_two_days():
    data = _weather_data()

    slice_obj = weather_handler._slice_for("precipitation", None, data)

    assert slice_obj["topic"] == "precipitation"
    assert len(slice_obj["days"]) == 3
    assert [day["date"] for day in slice_obj["days"]] == [
        data["forecast"][0]["date"],
        data["forecast"][1]["date"],
        data["forecast"][2]["date"],
    ]
    assert set(slice_obj["days"][0]) == {
        "weekday",
        "date",
        "precipitation",
        "condition",
    }


def test_day_reference_and_safety_net_for_non_today_answers():
    data = _weather_data()
    tomorrow_entry = data["forecast"][1]
    future_entry = data["forecast"][3]

    assert weather_handler._day_reference({"day": data["forecast"][0]}) == "today"
    assert weather_handler._day_reference({"day": tomorrow_entry}) == "tomorrow"
    assert weather_handler._day_reference({"day": future_entry}) == future_entry["weekday"]
    assert weather_handler._day_reference({"days": data["forecast"][:3]}) == "the next several days"
    assert (
        weather_handler._ensure_day_reference("High around 70.", "tomorrow")
        == "Tomorrow: high around 70."
    )
    assert (
        weather_handler._ensure_day_reference("High around 70 tomorrow.", "tomorrow")
        == "High around 70 tomorrow."
    )


def test_resume_followup_with_day_reuses_pending_topic(weather_cache, phrase_stub):
    pending = {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "weather",
        "data": {"topic": "forecast", "location": "medford"},
    }

    result = _run(weather_handler.handle("how about tomorrow", pending=pending))

    assert isinstance(result, dict)
    assert phrase_stub[0]["slice"]["topic"] == "day_forecast"
    assert result["structured"]["pending_action"]["data"]["topic"] == "forecast"


def test_resume_followup_without_day_abandons_for_stage3(weather_cache, phrase_stub):
    pending = {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "weather",
        "data": {"topic": "forecast", "location": "medford"},
    }

    result = _run(weather_handler.handle("actually something else", pending=pending))

    assert result == {"abandon_pending": True, "force_stage3": True}
    assert phrase_stub == []


def _install_end_conversation_stubs(monkeypatch, is_end):
    import agent_skills

    end_phrase_mod = types.ModuleType("agent_skills.end_phrase")
    end_phrase_mod.is_end = is_end

    utils_mod = types.ModuleType("agent_skills.private_handler_utils")
    calls = []

    def fake_end_conversation(text, structured=None):
        calls.append({"text": text, "structured": structured})
        return {"text": text, "structured": structured or {}, "ended": True}

    utils_mod.end_conversation = fake_end_conversation
    monkeypatch.setitem(sys.modules, "agent_skills.end_phrase", end_phrase_mod)
    monkeypatch.setitem(sys.modules, "agent_skills.private_handler_utils", utils_mod)
    monkeypatch.setattr(agent_skills, "end_phrase", end_phrase_mod, raising=False)
    return calls


def test_resume_end_conversation_requires_explicit_end_phrase(monkeypatch, weather_cache):
    calls = _install_end_conversation_stubs(
        monkeypatch, lambda prompt: prompt == "no thanks"
    )
    pending = {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "weather",
        "data": {"topic": "forecast", "location": "medford"},
    }

    ambiguous = _run(weather_handler.handle("maybe later", pending=pending))
    ended = _run(weather_handler.handle("no thanks", pending=pending))

    assert ambiguous == {"abandon_pending": True, "force_stage3": True}
    assert ended == {"text": "Ok.", "structured": {"intent": "weather"}, "ended": True}
    assert calls == [{"text": "Ok.", "structured": {"intent": "weather"}}]


def test_phrase_posts_minimal_slice_to_ollama_and_records_day_reference(monkeypatch):
    posts = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "High around 71 with partly cloudy skies."}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            posts.append({"url": url, "payload": json, "timeout": self.timeout})
            return FakeResponse()

    monkeypatch.setattr(weather_handler.httpx, "AsyncClient", FakeAsyncClient)

    slice_obj = {"topic": "day_forecast", "day": _weather_data()["forecast"][1]}
    result = _run(weather_handler._phrase(slice_obj, "what about tomorrow?"))

    assert result == "Tomorrow: high around 71 with partly cloudy skies."
    assert len(posts) == 1
    assert posts[0]["url"] == weather_handler.OLLAMA_URL
    payload = posts[0]["payload"]
    assert payload["model"] == weather_handler.MODEL
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["keep_alive"] == -1
    assert payload["options"]["num_predict"] == 60
    assert payload["options"]["num_ctx"] == weather_handler.LOCAL_LLM_NUM_CTX
    assert '"topic": "day_forecast"' in payload["prompt"]
    assert "current-marker" not in payload["prompt"]
    assert "pollen" not in payload["prompt"].lower()


def test_phrase_returns_none_when_ollama_call_fails(monkeypatch):
    class RaisingAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            raise RuntimeError("ollama unavailable")

    monkeypatch.setattr(weather_handler.httpx, "AsyncClient", RaisingAsyncClient)

    assert _run(weather_handler._phrase({"topic": "overview"}, "weather")) is None


def test_weather_handler_has_no_db_queries_or_sql_side_effects():
    source = MODULE_PATH.read_text()
    lowered = source.lower()

    assert "sqlite" not in lowered
    assert "sqlalchemy" not in lowered
    assert re.search(r"\b(select|insert|update|delete)\s+.+\bfrom\b", lowered) is None


def test_no_irreversible_client_actions_exist_and_end_conversation_is_guarded():
    source = MODULE_PATH.read_text()
    irreversible_markers = [
        "sms_send_direct",
        "contacts.sms_send",
        "email.send",
        "email.delete",
        ".unlink(",
        "os.remove(",
        "shutil.rmtree(",
        "DELETE FROM",
        "DROP TABLE",
    ]

    assert [marker for marker in irreversible_markers if marker in source] == []
    assert "end_conversation" in source
    assert "if end_phrase.is_end(prompt):" in source


def _topic_enum_from_schema(schema_text):
    match = re.search(r"one of:\s*(.+?)\.\s", schema_text)
    assert match, "topic schema must document its enum values"
    return {part.strip() for part in match.group(1).split("|")}


def test_valid_topics_match_metadata_params_schema_and_handler_branches():
    source = MODULE_PATH.read_text()
    schema_topics = _topic_enum_from_schema(weather_metadata.PARAMS_SCHEMA["topic"])
    branch_topics = set(re.findall(r'if topic == "([^"]+)"', source))

    assert schema_topics == weather_handler._VALID_TOPICS
    assert branch_topics <= weather_handler._VALID_TOPICS
    assert weather_handler._VALID_TOPICS - branch_topics == {"overview"}


def test_all_valid_topics_are_reachable_from_at_least_one_input():
    data = _weather_data()
    observed = {}

    for topic in sorted(weather_handler._VALID_TOPICS):
        day = "this_week" if topic in {"forecast", "precipitation"} else "tomorrow"
        slice_obj = weather_handler._slice_for(topic, day, data)
        assert slice_obj is not None, f"{topic} did not produce a slice"
        observed[topic] = slice_obj["topic"]

    assert set(observed) == weather_handler._VALID_TOPICS
    assert observed["forecast"] in {"day_forecast", "weekly_forecast"}
    assert observed["overview"] == "overview"


def test_day_phrase_map_has_no_contradictory_or_unreachable_values():
    phrase_to_value = dict(weather_handler._DAY_PHRASE_MAP)
    phrases = [phrase for phrase, _ in weather_handler._DAY_PHRASE_MAP]
    allowed_values = {
        "today",
        "tomorrow",
        "this_week",
        "weekend",
        *weather_handler._WEEKDAYS,
    }

    assert len(phrases) == len(set(phrases))
    assert phrase_to_value["tonight"] == "today"
    assert phrase_to_value["day after tomorrow"] is None
    assert phrases.index("day after tomorrow") < phrases.index("tomorrow")
    for phrase, mapped in weather_handler._DAY_PHRASE_MAP:
        if phrase == "day after tomorrow":
            continue
        assert mapped in allowed_values
        assert weather_handler._day_from_followup(f"and {phrase}?") == mapped

    day_after = weather_handler._day_from_followup("what about the day after tomorrow?")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", day_after)


def test_weather_few_shot_mappings_do_not_mark_fallback_classes_high_confidence():
    registry = class_registry.get_registry(refresh=True)
    fallback_classes = {"others", "delegate opus", "unclear"}

    for prompt, label in weather_metadata.METADATA["few_shot"]:
        class_name, confidence = label.rsplit(":", 1)
        assert class_name in registry, f"{prompt!r} maps to unknown class {class_name!r}"
        if class_name in fallback_classes:
            assert confidence != "High", (
                f"{prompt!r} maps fallback class {class_name!r} with High confidence"
            )


def test_registered_classes_have_handlers_or_documented_no_handler_behavior():
    registry = class_registry.get_registry(refresh=True)
    pipeline_source = PIPELINE_PATH.read_text()
    missing = []

    for name, meta in registry.items():
        if meta.get("handler") is not None:
            continue
        metadata_path = CLASSES_DIR / meta["pkg_name"] / "metadata.py"
        text = metadata_path.read_text().lower()
        documented = any(
            phrase in text
            for phrase in (
                "no handler",
                "always escalates",
                "escalate to stage 3",
                "short-circuits",
                "fallback",
            )
        )
        pipeline_special = name == "end conversation" and 'cls == "end conversation"' in pipeline_source
        if not documented and not pipeline_special:
            missing.append(name)

    assert missing == []


def test_registered_weather_handler_returns_documented_shape(weather_cache, phrase_stub):
    registry = class_registry.get_registry(refresh=True)
    weather_meta = registry["weather"]

    assert weather_meta["handler"] is weather_handler.handle

    result = _run(
        weather_meta["handler"](
            "what's the weather",
            params={"topic": "current", "location": "medford"},
        )
    )

    assert isinstance(result, dict)
    assert isinstance(result.get("text"), str)
    assert result["text"]
