from __future__ import annotations

import ast
import datetime as dt
import json
import re
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = (
    REPO_ROOT / "jane_web" / "jane_v2" / "classes" / "weather" / "handler.py"
)

from jane_web.jane_v2 import classes as class_registry
from jane_web.jane_v2.classes.weather import handler as weather_handler
from jane_web.jane_v2.classes.weather import metadata as weather_metadata


ALLOWED_SLICE_TOPICS = {
    "air_quality": {"air_quality"},
    "current": {"current"},
    "forecast": {"day_forecast", "weekly_forecast"},
    "overview": {"overview"},
    "pollen": {"pollen"},
    "precipitation": {"precipitation"},
    "wind": {"wind"},
}


@pytest.fixture
def module_source() -> str:
    return MODULE_PATH.read_text()


@pytest.fixture
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


@pytest.fixture
def fixed_today(monkeypatch) -> dt.date:
    today = dt.date(2025, 1, 6)

    class FixedDate(dt.date):
        @classmethod
        def today(cls) -> dt.date:
            return today

    monkeypatch.setattr(weather_handler, "date", FixedDate)
    return today


@pytest.fixture
def sample_weather_data(fixed_today: dt.date) -> dict:
    conditions = [
        "clear",
        "light rain",
        "partly cloudy",
        "overcast",
        "sunny",
        "showers",
        "cloudy",
    ]
    forecast = []
    for offset, condition in enumerate(conditions):
        day = fixed_today + dt.timedelta(days=offset)
        forecast.append(
            {
                "date": day.isoformat(),
                "weekday": day.strftime("%A"),
                "high": 50 + offset,
                "low": 34 + offset,
                "condition": condition,
                "precipitation": {
                    "chance": offset * 10,
                    "amount": round(offset * 0.05, 2),
                },
                "wind": {"speed": 5 + offset, "gust": 12 + offset},
                "humidity": {"min": 40 + offset, "max": 70 + offset},
                "uv_index": offset,
            }
        )
    return {
        "current": {
            "temperature": 41.2,
            "feels_like": 36.7,
            "condition": "clear",
            "humidity": 55,
            "wind": {"speed": 8, "gust": 14},
        },
        "forecast": forecast,
        "air_quality": {"us_aqi": 35, "pm25": 4.2, "pm10": 8.4},
        "pollen": {"tree": "low", "grass": "moderate", "weed": "none"},
    }


@pytest.fixture
def weather_cache(tmp_path, monkeypatch, sample_weather_data: dict) -> Path:
    path = tmp_path / "weather.json"
    path.write_text(json.dumps(sample_weather_data))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path)
    return path


@pytest.fixture
def phrase_recorder(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    async def fake_phrase(slice_obj: dict, prompt: str) -> str:
        calls.append({"slice": slice_obj, "prompt": prompt})
        return "Mock weather answer."

    monkeypatch.setattr(weather_handler, "_phrase", fake_phrase)
    return calls


def _assert_text_result(result: dict | None) -> None:
    assert isinstance(result, dict)
    assert isinstance(result.get("text"), str)
    assert result["text"]


def _function_def(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name}() was not found")


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _walk_calls_with_conditions(
    node: ast.AST, conditions: tuple[ast.AST, ...] = ()
) -> list[tuple[ast.Call, tuple[ast.AST, ...]]]:
    if isinstance(node, ast.If):
        calls: list[tuple[ast.Call, tuple[ast.AST, ...]]] = []
        for test_node in ast.walk(node.test):
            if isinstance(test_node, ast.Call):
                calls.append((test_node, conditions))
        for child in node.body:
            calls.extend(_walk_calls_with_conditions(child, conditions + (node.test,)))
        for child in node.orelse:
            calls.extend(_walk_calls_with_conditions(child, conditions))
        return calls
    calls = []
    if isinstance(node, ast.Call):
        calls.append((node, conditions))
    for child in ast.iter_child_nodes(node):
        calls.extend(_walk_calls_with_conditions(child, conditions))
    return calls


def _condition_mentions_end_phrase_is_end(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if not isinstance(func, ast.Attribute) or func.attr != "is_end":
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "end_phrase":
            return True
    return False


def _schema_topic_values() -> set[str]:
    schema_text = weather_metadata.PARAMS_SCHEMA["topic"]
    enum_part = schema_text.split("one of:", 1)[1].split(".", 1)[0]
    return {part.strip() for part in enum_part.split("|") if part.strip()}


def _topic_comparison_literals(tree: ast.Module) -> set[str]:
    func = _function_def(tree, "_slice_for")
    literals = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "topic":
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
            literals.add(comparator.value)
    return literals


def test_valid_topic_lookup_matches_param_schema_and_slice_branches(module_ast):
    assert weather_handler._VALID_TOPICS == _schema_topic_values()
    assert _topic_comparison_literals(module_ast) | {"overview"} == weather_handler._VALID_TOPICS
    assert set(ALLOWED_SLICE_TOPICS) == weather_handler._VALID_TOPICS


@pytest.mark.parametrize("topic", sorted(weather_handler._VALID_TOPICS))
def test_each_valid_topic_reaches_non_contradictory_slice(
    topic: str, sample_weather_data: dict
):
    day = "today" if topic in {"forecast", "precipitation", "wind"} else None
    slice_obj = weather_handler._slice_for(topic, day, sample_weather_data)

    assert slice_obj is not None
    assert slice_obj["topic"] in ALLOWED_SLICE_TOPICS[topic]


@pytest.mark.asyncio
@pytest.mark.parametrize("topic", sorted(weather_handler._VALID_TOPICS))
async def test_each_valid_topic_is_reachable_from_public_params(
    topic: str, weather_cache: Path, phrase_recorder: list[dict]
):
    result = await weather_handler.handle(
        f"weather request for {topic}",
        params={"topic": topic, "location": "Medford"},
    )

    _assert_text_result(result)
    assert phrase_recorder
    assert phrase_recorder[-1]["slice"]["topic"] in ALLOWED_SLICE_TOPICS[topic]


def test_day_phrase_lookup_is_unique_complete_and_longest_first():
    phrases = [phrase for phrase, _ in weather_handler._DAY_PHRASE_MAP]

    assert len(phrases) == len(set(phrases))
    assert set(weather_handler._WEEKDAYS).issubset(phrases)
    for earlier_idx, phrase in enumerate(phrases):
        for later_idx, other in enumerate(phrases):
            if phrase == other:
                continue
            if phrase in other:
                assert later_idx < earlier_idx


def test_day_phrase_lookup_values_are_supported_day_specs(
    sample_weather_data: dict,
):
    valid_single_day_specs = {"today", "tomorrow", *weather_handler._WEEKDAYS}
    valid_multi_day_specs = {"this_week", "weekend"}

    for phrase, mapped in weather_handler._DAY_PHRASE_MAP:
        result = weather_handler._day_from_followup(f"and {phrase}?")
        if phrase == "day after tomorrow":
            assert mapped is None
            assert dt.date.fromisoformat(result) == dt.date.today() + dt.timedelta(days=2)
            continue
        assert result == mapped
        assert mapped in valid_single_day_specs | valid_multi_day_specs
        if mapped in valid_single_day_specs:
            assert weather_handler._normalize_day(mapped, sample_weather_data["forecast"])
        else:
            assert weather_handler._normalize_day(mapped, sample_weather_data["forecast"]) is None


def test_force_escalate_phrase_table_is_unique_and_nonempty():
    phrases = weather_handler._FORCE_ESCALATE_PHRASES

    assert phrases
    assert len(phrases) == len(set(phrases))
    assert all(phrase.strip() for phrase in phrases)


@pytest.mark.asyncio
@pytest.mark.parametrize("phrase", weather_handler._FORCE_ESCALATE_PHRASES)
async def test_every_force_escalate_phrase_declines_before_cache_or_llm(
    phrase: str, monkeypatch
):
    async def fail_answer_for(*args, **kwargs):
        raise AssertionError("_answer_for should not be called for research phrases")

    monkeypatch.setattr(weather_handler, "_answer_for", fail_answer_for)

    result = await weather_handler.handle(f"please {phrase} for the weather")

    assert result is None


def test_weather_handler_has_no_database_queries(module_ast):
    imported_modules = set()
    call_names = set()
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name:
                call_names.add(name)

    assert "sqlite3" not in imported_modules
    assert "database" not in imported_modules
    assert "vault_web.database" not in imported_modules
    assert "get_db" not in call_names


def test_destructive_calls_are_limited_to_pending_conversation_close(module_ast):
    destructive_names = {
        "delete",
        "end_conversation",
        "send_message",
        "sms_send_direct",
        "sms_send",
        "unlink",
        "remove",
        "rmtree",
    }
    calls = {
        name
        for node in ast.walk(module_ast)
        if isinstance(node, ast.Call)
        for name in [_call_name(node)]
        if name
    }

    assert calls & destructive_names == {"end_conversation"}


def test_end_conversation_calls_are_inside_strict_end_phrase_gate(module_ast):
    handle_func = _function_def(module_ast, "handle")
    calls = [
        (call, conditions)
        for call, conditions in _walk_calls_with_conditions(handle_func)
        if _call_name(call) == "end_conversation"
    ]

    assert calls
    for _, conditions in calls:
        assert any(_condition_mentions_end_phrase_is_end(cond) for cond in conditions)


def test_weather_class_registry_has_dispatch_handler():
    registry = class_registry.get_registry(refresh=True)
    meta = registry["weather"]

    assert meta["name"] == "weather"
    assert meta["handler"] is weather_handler.handle
    assert meta["params_schema"] is weather_metadata.PARAMS_SCHEMA


def test_normalize_day_accepts_documented_day_specs(
    fixed_today: dt.date, sample_weather_data: dict
):
    forecast = sample_weather_data["forecast"]

    assert weather_handler._normalize_day("today", forecast)["date"] == fixed_today.isoformat()
    assert weather_handler._normalize_day("tomorrow", forecast)["date"] == (
        fixed_today + dt.timedelta(days=1)
    ).isoformat()
    assert weather_handler._normalize_day("Monday", forecast)["date"] == fixed_today.isoformat()
    assert weather_handler._normalize_day("Sunday", forecast)["date"] == (
        fixed_today + dt.timedelta(days=6)
    ).isoformat()
    assert weather_handler._normalize_day("2025-01-09", forecast)["weekday"] == "Thursday"


@pytest.mark.parametrize(
    "day",
    [None, "", "   ", "this_week", "weekend", "week", "notaday", "2025-02-31"],
)
def test_normalize_day_declines_empty_multi_day_and_invalid_values(
    day: str | None, sample_weather_data: dict
):
    assert weather_handler._normalize_day(day, sample_weather_data["forecast"]) is None


def test_normalize_day_declines_dates_outside_forecast(sample_weather_data: dict):
    assert weather_handler._normalize_day("2030-01-01", sample_weather_data["forecast"]) is None


@pytest.mark.parametrize("prompt", [None, "", "   ", "how about sometime"])
def test_day_from_followup_declines_empty_or_dayless_input(prompt: str | None):
    assert weather_handler._day_from_followup(prompt) is None


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("and tomorrow?", "tomorrow"),
        ("tonight please", "today"),
        ("this week", "this_week"),
        ("the week ahead", "this_week"),
        ("weekend?", "weekend"),
        ("monday", "monday"),
    ],
)
def test_day_from_followup_maps_documented_reply_phrases(prompt: str, expected: str):
    assert weather_handler._day_from_followup(prompt) == expected


def test_slice_for_current_uses_current_conditions_and_today(sample_weather_data: dict):
    result = weather_handler._slice_for("current", "today", sample_weather_data)

    assert result == {
        "topic": "current",
        "current": sample_weather_data["current"],
        "today": sample_weather_data["forecast"][0],
    }


def test_slice_for_forecast_defaults_to_today_and_handles_specific_day(
    sample_weather_data: dict,
):
    default = weather_handler._slice_for("forecast", None, sample_weather_data)
    tomorrow = weather_handler._slice_for("forecast", "tomorrow", sample_weather_data)

    assert default == {
        "topic": "day_forecast",
        "day": sample_weather_data["forecast"][0],
    }
    assert tomorrow == {
        "topic": "day_forecast",
        "day": sample_weather_data["forecast"][1],
    }


def test_slice_for_forecast_week_is_seven_slim_days(sample_weather_data: dict):
    result = weather_handler._slice_for("forecast", "this_week", sample_weather_data)

    assert result["topic"] == "weekly_forecast"
    assert len(result["days"]) == 7
    assert all(set(day) == {"weekday", "high", "low", "condition"} for day in result["days"])


def test_slice_for_precipitation_defaults_to_three_days_and_respects_day(
    sample_weather_data: dict,
):
    default = weather_handler._slice_for("precipitation", None, sample_weather_data)
    tomorrow = weather_handler._slice_for("precipitation", "tomorrow", sample_weather_data)

    assert default["topic"] == "precipitation"
    assert len(default["days"]) == 3
    assert tomorrow["days"] == [
        {
            "weekday": sample_weather_data["forecast"][1]["weekday"],
            "date": sample_weather_data["forecast"][1]["date"],
            "precipitation": sample_weather_data["forecast"][1]["precipitation"],
            "condition": sample_weather_data["forecast"][1]["condition"],
        }
    ]


def test_slice_for_precipitation_week_is_seven_slim_days(sample_weather_data: dict):
    result = weather_handler._slice_for("precipitation", "weekend", sample_weather_data)

    assert result["topic"] == "precipitation"
    assert len(result["days"]) == 7
    assert all(
        set(day) == {"weekday", "date", "precipitation", "condition"}
        for day in result["days"]
    )


def test_slice_for_wind_uses_day_wind_when_day_exists(sample_weather_data: dict):
    result = weather_handler._slice_for("wind", "tomorrow", sample_weather_data)

    assert result == {
        "topic": "wind",
        "day": sample_weather_data["forecast"][1]["weekday"],
        "wind": sample_weather_data["forecast"][1]["wind"],
    }


def test_slice_for_wind_defaults_to_current_wind_without_day(sample_weather_data: dict):
    result = weather_handler._slice_for("wind", None, sample_weather_data)

    assert result == {
        "topic": "wind",
        "current_wind": sample_weather_data["current"]["wind"],
    }


def test_slice_for_air_quality_and_pollen(sample_weather_data: dict):
    assert weather_handler._slice_for("air_quality", None, sample_weather_data) == {
        "topic": "air_quality",
        "air_quality": sample_weather_data["air_quality"],
    }
    assert weather_handler._slice_for("pollen", None, sample_weather_data) == {
        "topic": "pollen",
        "pollen": sample_weather_data["pollen"],
    }


def test_slice_for_missing_pollen_escalates(sample_weather_data: dict):
    data = dict(sample_weather_data)
    data.pop("pollen")

    assert weather_handler._slice_for("pollen", None, data) is None


def test_slice_for_overview_uses_current_today_and_air_quality(sample_weather_data: dict):
    result = weather_handler._slice_for("overview", None, sample_weather_data)

    assert result == {
        "topic": "overview",
        "current": sample_weather_data["current"],
        "today": sample_weather_data["forecast"][0],
        "air_quality_aqi": sample_weather_data["air_quality"]["us_aqi"],
    }


def test_slice_for_unknown_topic_falls_back_to_overview_slice(sample_weather_data: dict):
    result = weather_handler._slice_for("bad_topic", None, sample_weather_data)

    assert result["topic"] == "overview"


def test_day_reference_identifies_today_tomorrow_weekday_and_multi_day(
    sample_weather_data: dict,
):
    today_slice = {"topic": "day_forecast", "day": sample_weather_data["forecast"][0]}
    tomorrow_slice = {"topic": "day_forecast", "day": sample_weather_data["forecast"][1]}
    friday_slice = {"topic": "day_forecast", "day": sample_weather_data["forecast"][4]}
    multi_slice = {"topic": "weekly_forecast", "days": sample_weather_data["forecast"][:7]}

    assert weather_handler._day_reference(today_slice) == "today"
    assert weather_handler._day_reference(tomorrow_slice) == "tomorrow"
    assert weather_handler._day_reference(friday_slice) == "Friday"
    assert weather_handler._day_reference(multi_slice) == "the next several days"


@pytest.mark.parametrize(
    ("text", "day_ref", "expected"),
    [
        ("High around 55 with clouds.", "tomorrow", "Tomorrow: high around 55 with clouds."),
        ("Tomorrow looks cloudy.", "tomorrow", "Tomorrow looks cloudy."),
        ("It's clear.", "today", "It's clear."),
        ("Rain is likely.", "the next several days", "Rain is likely."),
        ("", "Friday", ""),
    ],
)
def test_ensure_day_reference_only_prepends_when_needed(
    text: str, day_ref: str, expected: str
):
    assert weather_handler._ensure_day_reference(text, day_ref) == expected


def test_wrap_with_followup_returns_documented_stage2_pending_shape():
    result = weather_handler._wrap_with_followup("It is clear.", "forecast", "medford")

    assert result["text"] == "It is clear. Want the weather for another day?"
    pending = result["structured"]["pending_action"]
    assert result["structured"]["intent"] == "weather"
    assert pending["type"] == "STAGE2_FOLLOWUP"
    assert pending["handler_class"] == "weather"
    assert pending["status"] == "awaiting_user"
    assert pending["awaiting"] == "another_day_or_stop"
    assert pending["data"] == {
        "awaiting": "another_day_or_stop",
        "topic": "forecast",
        "location": "medford",
    }
    assert pending["question"] == "Want the weather for another day?"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", pending["expires_at"])


@pytest.mark.asyncio
async def test_answer_for_reads_cache_slices_and_wraps_llm_phrase(
    weather_cache: Path, phrase_recorder: list[dict], sample_weather_data: dict
):
    result = await weather_handler._answer_for(
        "what is tomorrow's forecast?",
        "forecast",
        "tomorrow",
        "medford",
    )

    _assert_text_result(result)
    assert result["text"] == "Mock weather answer. Want the weather for another day?"
    assert phrase_recorder == [
        {
            "slice": {
                "topic": "day_forecast",
                "day": sample_weather_data["forecast"][1],
            },
            "prompt": "what is tomorrow's forecast?",
        }
    ]


@pytest.mark.asyncio
async def test_answer_for_cache_miss_escalates(tmp_path, monkeypatch):
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", tmp_path / "missing.json")

    async def fail_phrase(*args, **kwargs):
        raise AssertionError("_phrase should not be called when the cache is missing")

    monkeypatch.setattr(weather_handler, "_phrase", fail_phrase)

    assert await weather_handler._answer_for("weather?", "overview", None, None) is None


@pytest.mark.asyncio
async def test_answer_for_malformed_cache_escalates(tmp_path, monkeypatch):
    path = tmp_path / "weather.json"
    path.write_text("{not-json")
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path)

    async def fail_phrase(*args, **kwargs):
        raise AssertionError("_phrase should not be called for malformed cache JSON")

    monkeypatch.setattr(weather_handler, "_phrase", fail_phrase)

    assert await weather_handler._answer_for("weather?", "overview", None, None) is None


@pytest.mark.asyncio
async def test_answer_for_llm_decline_escalates(weather_cache: Path, monkeypatch):
    async def no_phrase(slice_obj: dict, prompt: str) -> None:
        return None

    monkeypatch.setattr(weather_handler, "_phrase", no_phrase)

    assert await weather_handler._answer_for("weather?", "overview", None, None) is None


@pytest.mark.asyncio
async def test_phrase_posts_small_slice_to_ollama_and_enforces_day_reference(
    monkeypatch, sample_weather_data: dict
):
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            captured["raise_for_status_called"] = True

        def json(self) -> dict:
            return {"response": "High around 51 with light rain."}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            captured["url"] = url
            captured["body"] = json
            return FakeResponse()

    monkeypatch.setattr(weather_handler.httpx, "AsyncClient", FakeAsyncClient)

    slice_obj = {"topic": "day_forecast", "day": sample_weather_data["forecast"][1]}
    result = await weather_handler._phrase(slice_obj, "what about tomorrow?")

    assert result == "Tomorrow: high around 51 with light rain."
    assert captured["url"] == weather_handler.OLLAMA_URL
    assert captured["timeout"] == weather_handler.LOCAL_LLM_TIMEOUT
    assert captured["raise_for_status_called"] is True
    body = captured["body"]
    assert body["model"] == weather_handler.MODEL
    assert body["stream"] is False
    assert body["think"] is False
    assert body["keep_alive"] == -1
    assert body["options"]["temperature"] == 0.2
    assert body["options"]["num_predict"] == 60
    assert body["options"]["num_ctx"] == weather_handler.LOCAL_LLM_NUM_CTX
    assert '"topic": "day_forecast"' in body["prompt"]
    assert "User question: what about tomorrow?" in body["prompt"]


@pytest.mark.asyncio
async def test_phrase_returns_none_on_http_failure(monkeypatch, sample_weather_data: dict):
    class RaisingAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            raise RuntimeError("network down")

    monkeypatch.setattr(weather_handler.httpx, "AsyncClient", RaisingAsyncClient)

    result = await weather_handler._phrase(
        {"topic": "day_forecast", "day": sample_weather_data["forecast"][1]},
        "weather?",
    )

    assert result is None


@pytest.mark.asyncio
async def test_phrase_returns_none_for_blank_llm_response(
    monkeypatch, sample_weather_data: dict
):
    class BlankResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"response": "   "}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            return BlankResponse()

    monkeypatch.setattr(weather_handler.httpx, "AsyncClient", FakeAsyncClient)

    result = await weather_handler._phrase(
        {"topic": "day_forecast", "day": sample_weather_data["forecast"][1]},
        "weather?",
    )

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("location", [None, "", "Medford", "medford ma", "Medford, MA"])
async def test_handle_accepts_default_and_medford_locations(
    location: str | None, weather_cache: Path, phrase_recorder: list[dict]
):
    result = await weather_handler.handle(
        "what is the weather?",
        params={"topic": "current", "location": location},
    )

    _assert_text_result(result)
    assert result["structured"]["pending_action"]["data"]["topic"] == "current"
    assert len(phrase_recorder) == 1


@pytest.mark.asyncio
async def test_handle_escalates_non_medford_location_before_cache_or_llm(monkeypatch):
    async def fail_answer_for(*args, **kwargs):
        raise AssertionError("_answer_for should not be called for non-Medford locations")

    monkeypatch.setattr(weather_handler, "_answer_for", fail_answer_for)

    result = await weather_handler.handle(
        "what is the weather in Tokyo?",
        params={"topic": "current", "location": "Tokyo"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_handle_unknown_topic_falls_back_to_overview(
    weather_cache: Path, phrase_recorder: list[dict]
):
    result = await weather_handler.handle(
        "what is the temperature?",
        params={"topic": "temperature", "location": "Medford"},
    )

    _assert_text_result(result)
    assert phrase_recorder[0]["slice"]["topic"] == "overview"
    assert result["structured"]["pending_action"]["data"]["topic"] == "overview"


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", [None, "", "   "])
async def test_handle_empty_or_none_prompt_still_uses_default_overview(
    prompt: str | None, weather_cache: Path, phrase_recorder: list[dict]
):
    result = await weather_handler.handle(prompt, params=None)

    _assert_text_result(result)
    assert phrase_recorder[0]["slice"]["topic"] == "overview"
    assert phrase_recorder[0]["prompt"] == prompt


@pytest.mark.asyncio
async def test_handle_very_long_prompt_does_not_expand_cache_context(
    weather_cache: Path, phrase_recorder: list[dict]
):
    prompt = "what is the weather " + ("please " * 10_000)

    result = await weather_handler.handle(prompt, params={"topic": "forecast", "day": "today"})

    _assert_text_result(result)
    assert len(phrase_recorder) == 1
    assert phrase_recorder[0]["prompt"] == prompt
    assert phrase_recorder[0]["slice"]["topic"] == "day_forecast"


@pytest.mark.asyncio
async def test_handle_malformed_day_string_does_not_crash_and_defaults_forecast_today(
    weather_cache: Path, phrase_recorder: list[dict], sample_weather_data: dict
):
    result = await weather_handler.handle(
        "weather on blursday?",
        params={"topic": "forecast", "day": "blursday"},
    )

    _assert_text_result(result)
    assert phrase_recorder[0]["slice"] == {
        "topic": "day_forecast",
        "day": sample_weather_data["forecast"][0],
    }


@pytest.mark.asyncio
async def test_handle_resume_followup_maps_day_and_reuses_pending_topic(
    weather_cache: Path, phrase_recorder: list[dict], sample_weather_data: dict
):
    pending = {"data": {"topic": "forecast", "location": "Medford"}}

    result = await weather_handler.handle("and tomorrow?", pending=pending)

    _assert_text_result(result)
    assert phrase_recorder[0]["slice"] == {
        "topic": "day_forecast",
        "day": sample_weather_data["forecast"][1],
    }
    assert result["structured"]["pending_action"]["data"]["topic"] == "forecast"


@pytest.mark.asyncio
async def test_handle_resume_accepts_flat_pending_dict(
    weather_cache: Path, phrase_recorder: list[dict]
):
    pending = {"topic": "precipitation", "location": "Medford"}

    result = await weather_handler.handle("tomorrow", pending=pending)

    _assert_text_result(result)
    assert phrase_recorder[0]["slice"]["topic"] == "precipitation"
    assert len(phrase_recorder[0]["slice"]["days"]) == 1


@pytest.mark.asyncio
async def test_handle_resume_malformed_pending_data_container_still_answers(
    weather_cache: Path, phrase_recorder: list[dict]
):
    pending = {"data": "not a dict"}

    result = await weather_handler.handle("tomorrow", pending=pending)

    _assert_text_result(result)
    assert phrase_recorder[0]["slice"]["topic"] == "overview"


@pytest.mark.asyncio
async def test_handle_resume_dayless_reply_abandons_pending_without_llm(monkeypatch):
    async def fail_answer_for(*args, **kwargs):
        raise AssertionError("_answer_for should not be called without a follow-up day")

    monkeypatch.setattr(weather_handler, "_answer_for", fail_answer_for)

    result = await weather_handler.handle(
        "what about that?",
        pending={"data": {"topic": "forecast", "location": "Medford"}},
    )

    assert result == {"abandon_pending": True, "force_stage3": True}


@pytest.mark.asyncio
async def test_handle_resume_answer_failure_abandons_pending(monkeypatch):
    async def no_answer(*args, **kwargs):
        return None

    monkeypatch.setattr(weather_handler, "_answer_for", no_answer)

    result = await weather_handler.handle(
        "tomorrow",
        pending={"data": {"topic": "forecast", "location": "Medford"}},
    )

    assert result == {"abandon_pending": True, "force_stage3": True}


@pytest.mark.asyncio
async def test_handle_resume_end_phrase_returns_conversation_end(monkeypatch):
    async def fail_answer_for(*args, **kwargs):
        raise AssertionError("_answer_for should not run for strict end phrases")

    monkeypatch.setattr(weather_handler, "_answer_for", fail_answer_for)

    result = await weather_handler.handle(
        "no thanks",
        pending={"data": {"topic": "forecast", "location": "Medford"}},
    )

    assert result == {
        "text": "Ok.",
        "conversation_end": True,
        "structured": {"intent": "weather"},
    }


@pytest.mark.asyncio
async def test_handle_resume_borderline_no_with_day_cannot_end_conversation(
    monkeypatch, weather_cache: Path, phrase_recorder: list[dict]
):
    from agent_skills import private_handler_utils

    end_mock = Mock(side_effect=AssertionError("ambiguous input must not end conversation"))
    monkeypatch.setattr(private_handler_utils, "end_conversation", end_mock)

    result = await weather_handler.handle(
        "no, tomorrow",
        pending={"data": {"topic": "forecast", "location": "Medford"}},
    )

    _assert_text_result(result)
    assert end_mock.call_count == 0
    assert phrase_recorder[0]["slice"]["topic"] == "day_forecast"
