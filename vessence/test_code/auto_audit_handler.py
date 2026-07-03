"""Auto-audit tests for jane_web.jane_v2.classes.weather.handler."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest


VESSENCE_ROOT = Path(__file__).resolve().parents[1]
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

MODULE_NAME = "jane_web.jane_v2.classes.weather.handler"
METADATA_MODULE_NAME = "jane_web.jane_v2.classes.weather.metadata"
SLICES_MODULE_NAME = "jane_web.jane_v2.classes.weather.slices"
CLASSES_MODULE_NAME = "jane_web.jane_v2.classes"
MODULE_PATH = VESSENCE_ROOT / "jane_web/jane_v2/classes/weather/handler.py"
SLICES_PATH = VESSENCE_ROOT / "jane_web/jane_v2/classes/weather/slices.py"
WEATHER_CLASS_DIR = VESSENCE_ROOT / "jane_web/jane_v2/classes/weather"


@pytest.fixture
def weather_handler():
    return importlib.import_module(MODULE_NAME)


@pytest.fixture
def weather_metadata():
    return importlib.import_module(METADATA_MODULE_NAME)


@pytest.fixture
def weather_slices():
    return importlib.import_module(SLICES_MODULE_NAME)


def _source(path: Path = MODULE_PATH) -> str:
    return path.read_text()


def _module_ast(path: Path = MODULE_PATH) -> ast.Module:
    return ast.parse(_source(path))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _weather_data(start: date | None = None) -> dict:
    start = start or date.today()
    forecast = []
    for offset in range(8):
        current = start + timedelta(days=offset)
        forecast.append(
            {
                "date": current.isoformat(),
                "weekday": current.strftime("%A"),
                "high": 70 + offset,
                "low": 50 + offset,
                "condition": "clear" if offset < 2 else "partly cloudy",
                "precipitation": {"chance": offset * 10},
                "wind": {"speed": 5 + offset},
                "debug_provider_payload": {"raw": True},
            }
        )
    return {
        "forecast": forecast,
        "current": {
            "temperature": 69,
            "feels_like": 68,
            "condition": "clear",
            "wind": {"speed": 4},
            "debug_station": "drop me",
        },
        "air_quality": {"us_aqi": 35, "aqi": 40},
        "pollen": {"tree": "low", "grass": "moderate", "weed": "low"},
    }


def _write_weather_cache(tmp_path: Path, monkeypatch, weather_handler, data: dict) -> Path:
    path = tmp_path / "weather.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path)
    return path


def _install_llm(monkeypatch, weather_handler, answer: str | None = "It is clear."):
    calls: list[dict] = []

    async def fake_llm(prompt, payload_builder):
        payload = payload_builder(
            prompt,
            model="test-weather-model",
            num_ctx=1234,
            keep_alive="1m",
        )
        calls.append({"prompt": prompt, "payload": payload})
        return answer

    monkeypatch.setattr(weather_handler, "_post_local_llm_response", fake_llm)
    return calls


def _assert_text_response(result: dict | None) -> None:
    assert isinstance(result, dict)
    assert isinstance(result.get("text"), str)
    assert result["text"]


def _assert_weather_followup_shape(result: dict | None, topic: str, location: str) -> None:
    _assert_text_response(result)
    assert "Want the weather for another day?" in result["text"]
    pending = result["structured"]["pending_action"]
    assert pending["type"] == "STAGE2_FOLLOWUP"
    assert pending["handler_class"] == "weather"
    assert pending["awaiting"] == "another_day_or_stop"
    assert pending["question"] == "Want the weather for another day?"
    assert pending["data"]["topic"] == topic
    assert pending["data"]["location"] == location
    assert pending["data"]["awaiting"] == "another_day_or_stop"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", pending["expires_at"])


def _schema_topics(weather_metadata) -> set[str]:
    topic_schema = weather_metadata.PARAMS_SCHEMA["topic"]
    match = re.search(r"one of:\s*([^.]*)\.", topic_schema)
    assert match is not None
    return {piece.strip() for piece in match.group(1).split("|")}


def _slice_topic_branch_literals() -> set[str]:
    topics: set[str] = set()
    for node in ast.walk(_module_ast(SLICES_PATH)):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "topic":
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if (
                isinstance(op, ast.Eq)
                and isinstance(comparator, ast.Constant)
                and isinstance(comparator.value, str)
            ):
                topics.add(comparator.value)
    return topics


def _string_literals(path: Path) -> set[str]:
    return {
        node.value
        for node in ast.walk(_module_ast(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_docstring_is_the_weather_stage2_spec(weather_handler):
    doc = inspect.getdoc(weather_handler)

    assert doc is not None
    assert "params-driven slice" in doc
    assert "Stage 1" in doc
    assert "{topic, day, location}" in doc
    assert "small fact slice" in doc
    assert '{"text": "<answer>"}' in doc
    assert "None" in doc
    assert "non-Medford" in doc
    assert "research/online questions" in doc


def test_public_handler_contract_is_async_and_stage2_shaped(weather_handler):
    signature = inspect.signature(weather_handler.handle)

    assert inspect.iscoroutinefunction(weather_handler.handle)
    assert list(signature.parameters) == ["prompt", "context", "pending", "params"]
    assert signature.parameters["context"].default == ""
    assert signature.parameters["pending"].default is None
    assert signature.parameters["params"].default is None


@pytest.mark.asyncio
async def test_success_uses_params_slice_cache_and_mocked_llm(
    weather_handler,
    monkeypatch,
    tmp_path,
):
    data = _weather_data()
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, data)
    llm_calls = _install_llm(monkeypatch, weather_handler, "High around 71 and clear.")

    result = await weather_handler.handle(
        "what is tomorrow's weather in Medford?",
        params={"topic": "forecast", "day": "tomorrow", "location": "Medford"},
    )

    _assert_weather_followup_shape(result, topic="forecast", location="medford")
    assert result["text"].startswith("Tomorrow: high around 71 and clear.")
    assert len(llm_calls) == 1
    payload = llm_calls[0]["payload"]
    assert payload["model"] == "test-weather-model"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"] == {
        "temperature": 0.2,
        "num_predict": 60,
        "num_ctx": 1234,
    }
    assert payload["keep_alive"] == "1m"
    assert '"topic": "day_forecast"' in payload["prompt"]
    assert '"debug_provider_payload"' not in payload["prompt"]
    assert "User question: what is tomorrow's weather in Medford?" in payload["prompt"]


@pytest.mark.asyncio
async def test_unknown_topic_falls_back_to_overview(
    weather_handler,
    monkeypatch,
    tmp_path,
):
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, _weather_data())
    llm_calls = _install_llm(monkeypatch, weather_handler, "It is mild.")

    result = await weather_handler.handle(
        "what's it like out?",
        params={"topic": "mystery", "day": None, "location": ""},
    )

    _assert_weather_followup_shape(result, topic="overview", location="")
    assert "It is mild." in result["text"]
    assert len(llm_calls) == 1
    assert '"topic": "overview"' in llm_calls[0]["payload"]["prompt"]


@pytest.mark.asyncio
async def test_params_none_defaults_to_overview(weather_handler, monkeypatch, tmp_path):
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, _weather_data())
    _install_llm(monkeypatch, weather_handler, "It is comfortable.")

    result = await weather_handler.handle("weather", params=None)

    _assert_weather_followup_shape(result, topic="overview", location="")
    assert "It is comfortable." in result["text"]


@pytest.mark.asyncio
async def test_non_medford_location_escalates_without_cache_or_llm(
    weather_handler,
    monkeypatch,
):
    path_spy = Mock()
    path_spy.read_text.side_effect = RuntimeError("cache should not be read")
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called"))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path_spy)
    monkeypatch.setattr(weather_handler, "_post_local_llm_response", llm_mock)

    result = await weather_handler.handle(
        "what's the weather in Tokyo?",
        params={"topic": "current", "day": "today", "location": "Tokyo"},
    )

    assert result is None
    path_spy.read_text.assert_not_called()
    llm_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        "can you look up the weather online?",
        "do a search for the latest on the storm",
        "what's causing the haze?",
        "why is the sky orange today?",
        "news about the storm",
    ],
)
async def test_research_or_online_phrases_escalate_before_cache_or_llm(
    weather_handler,
    monkeypatch,
    prompt,
):
    path_spy = Mock()
    path_spy.read_text.side_effect = RuntimeError("cache should not be read")
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called"))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path_spy)
    monkeypatch.setattr(weather_handler, "_post_local_llm_response", llm_mock)

    result = await weather_handler.handle(
        prompt,
        params={"topic": "overview", "day": None, "location": ""},
    )

    assert result is None
    path_spy.read_text.assert_not_called()
    llm_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("cache_text", ["", "{", "[]", "null"])
async def test_unreadable_or_malformed_cache_escalates_without_llm(
    weather_handler,
    monkeypatch,
    tmp_path,
    cache_text,
):
    path = tmp_path / "weather.json"
    path.write_text(cache_text)
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called"))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path)
    monkeypatch.setattr(weather_handler, "_post_local_llm_response", llm_mock)

    result = await weather_handler.handle(
        "weather",
        params={"topic": "overview", "day": None, "location": ""},
    )

    assert result is None
    llm_mock.assert_not_called()


@pytest.mark.asyncio
async def test_cache_miss_escalates_without_llm(weather_handler, monkeypatch, tmp_path):
    data = {**_weather_data(), "pollen": None}
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, data)
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called"))
    monkeypatch.setattr(weather_handler, "_post_local_llm_response", llm_mock)

    result = await weather_handler.handle(
        "how is the pollen?",
        params={"topic": "pollen", "day": None, "location": ""},
    )

    assert result is None
    llm_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("llm_answer", [None, ""])
async def test_empty_llm_response_escalates(
    weather_handler,
    monkeypatch,
    tmp_path,
    llm_answer,
):
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, _weather_data())
    _install_llm(monkeypatch, weather_handler, llm_answer)

    result = await weather_handler.handle(
        "weather",
        params={"topic": "overview", "day": None, "location": ""},
    )

    assert result is None


@pytest.mark.asyncio
async def test_llm_exception_escalates(weather_handler, monkeypatch, tmp_path):
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, _weather_data())

    async def boom(prompt, payload_builder):
        raise RuntimeError("ollama unavailable")

    monkeypatch.setattr(weather_handler, "_post_local_llm_response", boom)

    result = await weather_handler.handle(
        "weather",
        params={"topic": "overview", "day": None, "location": ""},
    )

    assert result is None


@pytest.mark.asyncio
async def test_phrase_builds_payload_and_enforces_day_reference(weather_handler, monkeypatch):
    captured: dict = {}

    async def fake_llm(prompt, payload_builder):
        captured["payload"] = payload_builder(
            prompt,
            model="qwen-test",
            num_ctx=4096,
            keep_alive=-1,
        )
        return "High near 70."

    monkeypatch.setattr(weather_handler, "_post_local_llm_response", fake_llm)
    monkeypatch.setattr(weather_handler, "_day_reference", lambda slice_obj: "Saturday")
    slice_obj = {
        "topic": "day_forecast",
        "day": {"date": "2026-07-04", "weekday": "Saturday", "high": 70},
    }

    result = await weather_handler._phrase(slice_obj, "how hot?")

    assert result == "Saturday: high near 70."
    payload = captured["payload"]
    assert payload["model"] == "qwen-test"
    assert payload["options"]["num_ctx"] == 4096
    assert payload["keep_alive"] == -1
    assert '"topic": "day_forecast"' in payload["prompt"]
    assert "User question: how hot?" in payload["prompt"]


@pytest.mark.asyncio
async def test_resume_followup_uses_pending_topic_and_followup_day(
    weather_handler,
    monkeypatch,
    tmp_path,
):
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, _weather_data())
    _install_llm(monkeypatch, weather_handler, "High around 71 and clear.")
    pending = {"data": {"topic": "forecast", "location": "medford"}}

    result = await weather_handler.handle("tomorrow", pending=pending)

    _assert_weather_followup_shape(result, topic="forecast", location="medford")
    assert result["text"].startswith("Tomorrow: high around 71 and clear.")


@pytest.mark.asyncio
async def test_resume_without_day_abandons_pending_and_forces_stage3(weather_handler):
    result = await weather_handler.handle(
        "maybe later",
        pending={"data": {"topic": "forecast", "location": "medford"}},
    )

    assert result == {"abandon_pending": True, "force_stage3": True}


@pytest.mark.asyncio
async def test_resume_cache_miss_abandons_pending_and_forces_stage3(
    weather_handler,
    monkeypatch,
    tmp_path,
):
    data = {**_weather_data(), "pollen": None}
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, data)
    pending = {"data": {"topic": "pollen", "location": "medford"}}

    result = await weather_handler.handle("tomorrow", pending=pending)

    assert result == {"abandon_pending": True, "force_stage3": True}


@pytest.mark.asyncio
async def test_resume_end_phrase_returns_conversation_end_without_cache_or_llm(
    weather_handler,
    monkeypatch,
):
    path_spy = Mock()
    path_spy.read_text.side_effect = RuntimeError("cache should not be read")
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called"))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path_spy)
    monkeypatch.setattr(weather_handler, "_post_local_llm_response", llm_mock)

    result = await weather_handler.handle(
        "no",
        pending={"data": {"topic": "forecast", "location": "medford"}},
    )

    assert result == {
        "text": "Ok.",
        "conversation_end": True,
        "structured": {"intent": "weather"},
    }
    path_spy.read_text.assert_not_called()
    llm_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    ["no, tomorrow", "maybe tomorrow", "stop by Friday", "cancel tomorrow"],
)
async def test_borderline_end_like_followups_do_not_end_conversation(
    weather_handler,
    monkeypatch,
    prompt,
):
    from agent_skills import private_handler_utils

    end_mock = Mock(side_effect=AssertionError("ambiguous input must not end"))
    calls: list[tuple] = []

    async def fake_answer(prompt_arg, topic, day, location):
        calls.append((prompt_arg, topic, day, location))
        return {"text": "followup answer"}

    monkeypatch.setattr(private_handler_utils, "end_conversation", end_mock)
    monkeypatch.setattr(weather_handler, "_answer_for", fake_answer)

    result = await weather_handler.handle(
        prompt,
        pending={"data": {"topic": "forecast", "location": "medford"}},
    )

    assert result == {"text": "followup answer"}
    assert calls
    end_mock.assert_not_called()


@pytest.mark.asyncio
async def test_resume_with_non_medford_pending_location_escalates_without_medford_cache_answer(
    weather_handler,
    monkeypatch,
):
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called"))
    path_spy = Mock()
    path_spy.read_text.return_value = json.dumps(_weather_data())
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path_spy)
    monkeypatch.setattr(weather_handler, "_post_local_llm_response", llm_mock)

    result = await weather_handler.handle(
        "tomorrow",
        pending={"data": {"topic": "forecast", "location": "tokyo"}},
    )

    assert result == {"abandon_pending": True, "force_stage3": True}
    llm_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", ["", None])
async def test_empty_and_none_prompt_still_use_valid_params(
    weather_handler,
    monkeypatch,
    tmp_path,
    prompt,
):
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, _weather_data())
    llm_calls = _install_llm(monkeypatch, weather_handler, "It is clear.")

    result = await weather_handler.handle(
        prompt,
        params={"topic": "current", "day": "today", "location": ""},
    )

    _assert_weather_followup_shape(result, topic="current", location="")
    assert "It is clear." in result["text"]
    assert len(llm_calls) == 1
    assert llm_calls[0]["prompt"] is prompt


@pytest.mark.asyncio
async def test_very_long_prompt_is_passed_to_single_llm_call(
    weather_handler,
    monkeypatch,
    tmp_path,
):
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, _weather_data())
    llm_calls = _install_llm(monkeypatch, weather_handler, "It is clear.")
    long_prompt = "what is the weather " * 20_000

    result = await weather_handler.handle(
        long_prompt,
        params={"topic": "overview", "day": None, "location": ""},
    )

    _assert_weather_followup_shape(result, topic="overview", location="")
    assert len(llm_calls) == 1
    assert llm_calls[0]["prompt"] == long_prompt
    assert long_prompt in llm_calls[0]["payload"]["prompt"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        "not a dict",
        ["forecast"],
        123,
        {"topic": object(), "day": None, "location": ""},
        {"topic": "overview", "day": None, "location": object()},
    ],
)
async def test_malformed_params_escalate_without_cache_or_llm(
    weather_handler,
    monkeypatch,
    params,
):
    path_spy = Mock()
    path_spy.read_text.side_effect = RuntimeError("cache should not be read")
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called"))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path_spy)
    monkeypatch.setattr(weather_handler, "_post_local_llm_response", llm_mock)

    result = await weather_handler.handle("weather", params=params)

    assert result is None
    path_spy.read_text.assert_not_called()
    llm_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pending",
    ["not a dict", ["forecast"], 123, {"data": "not a dict"}],
)
async def test_malformed_pending_escalates_without_cache_or_llm(
    weather_handler,
    monkeypatch,
    pending,
):
    path_spy = Mock()
    path_spy.read_text.side_effect = RuntimeError("cache should not be read")
    llm_mock = AsyncMock(side_effect=AssertionError("LLM should not be called"))
    monkeypatch.setattr(weather_handler, "WEATHER_PATH", path_spy)
    monkeypatch.setattr(weather_handler, "_post_local_llm_response", llm_mock)

    result = await weather_handler.handle("tomorrow", pending=pending)

    assert result == {"abandon_pending": True, "force_stage3": True}
    path_spy.read_text.assert_not_called()
    llm_mock.assert_not_called()


def test_no_database_query_integration_points_in_handler_source():
    tree = _module_ast()
    imported_roots: set[str] = set()
    call_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            call_names.add(_call_name(node.func).lower())

    assert imported_roots.isdisjoint(
        {"sqlite3", "pymysql", "psycopg2", "sqlalchemy", "mysql", "duckdb"}
    )
    assert not any(
        token in call_name
        for call_name in call_names
        for token in (".execute", ".executemany", ".query", ".delete", ".commit")
    )


def test_valid_topic_registry_matches_metadata_schema_and_slice_branches(
    weather_handler,
    weather_metadata,
):
    assert weather_handler._VALID_TOPICS == _schema_topics(weather_metadata)
    assert _slice_topic_branch_literals() <= weather_handler._VALID_TOPICS
    assert "overview" in weather_handler._VALID_TOPICS


def test_topic_registry_has_no_fallback_confidence_or_boolean_contradictions(weather_handler):
    contradictory_values = {
        "other",
        "others",
        "fallback",
        "unknown",
        "high",
        "medium",
        "low",
        "true",
        "false",
        "none",
    }

    assert weather_handler._VALID_TOPICS.isdisjoint(contradictory_values)
    assert all(topic == topic.strip().lower() for topic in weather_handler._VALID_TOPICS)
    assert all(" " not in topic for topic in weather_handler._VALID_TOPICS)


@pytest.mark.parametrize(
    ("topic", "day"),
    [
        ("current", "today"),
        ("forecast", "tomorrow"),
        ("precipitation", "this_week"),
        ("wind", "today"),
        ("air_quality", None),
        ("pollen", None),
        ("overview", None),
    ],
)
def test_every_registered_topic_is_reachable_from_one_input(weather_slices, topic, day):
    result = weather_slices.slice_for(topic, day, _weather_data())

    assert isinstance(result, dict)
    assert isinstance(result.get("topic"), str)
    assert result["topic"]
    assert "debug_provider_payload" not in json.dumps(result)
    assert "debug_station" not in json.dumps(result)


def test_day_phrase_map_has_unique_specific_and_noncontradictory_entries(
    weather_handler,
):
    day_map = weather_handler._DAY_PHRASE_MAP
    phrases = [phrase for phrase, _mapped in day_map]
    allowed_mapped = {
        None,
        "today",
        "tomorrow",
        "this_week",
        "weekend",
        *weather_handler._WEEKDAYS,
    }

    assert len(phrases) == len(set(phrases))
    assert all(phrase and phrase == phrase.lower().strip() for phrase in phrases)
    assert {mapped for _phrase, mapped in day_map} <= allowed_mapped
    assert not ({mapped for _phrase, mapped in day_map if mapped} & {"others", "high", "low"})

    for earlier_index, earlier in enumerate(phrases):
        for later in phrases[earlier_index + 1 :]:
            if later in earlier:
                continue
            assert earlier not in later


@pytest.mark.parametrize("phrase,mapped", importlib.import_module(SLICES_MODULE_NAME).DAY_PHRASE_MAP)
def test_every_day_phrase_mapping_is_reachable(weather_slices, phrase, mapped):
    fixed_today = date(2026, 7, 3)

    result = weather_slices.day_from_followup(f"please show {phrase}", today=fixed_today)

    if phrase == "day after tomorrow":
        assert result == "2026-07-05"
    else:
        assert result == mapped


def test_force_escalate_phrases_are_unique_lowercase_and_not_overbroad(weather_handler):
    phrases = weather_handler._FORCE_ESCALATE_PHRASES

    assert len(phrases) == len(set(phrases))
    assert all(phrase and phrase == phrase.lower() and phrase.strip() for phrase in phrases)
    assert all(not phrase.startswith(" ") for phrase in phrases)
    assert all("  " not in phrase for phrase in phrases)
    assert not any(phrase in {"weather", "forecast", "rain", "snow"} for phrase in phrases)
    assert any("search" in phrase for phrase in phrases)
    assert any("why" in phrase or "cause" in phrase for phrase in phrases)


def test_end_conversation_call_is_limited_to_strict_resume_phrase_gate():
    source = _source()

    assert "end_conversation(" in source
    assert "end_phrase.is_end(prompt)" in source
    assert source.index("if pending:") < source.index("end_phrase.is_end(prompt)")
    assert source.index("end_phrase.is_end(prompt)") < source.index("end_conversation(")


def test_non_end_destructive_operations_would_require_numeric_confidence_threshold():
    destructive_names = {
        "delete",
        "delete_message",
        "delete_email",
        "send_message",
        "sms_send_direct",
        "sms_send",
        "email.send",
        "unlink",
        "rmtree",
    }
    calls = {
        _call_name(node.func)
        for node in ast.walk(_module_ast())
        if isinstance(node, ast.Call)
    }
    destructive_calls = {
        call_name
        for call_name in calls
        if call_name.split(".")[-1] in destructive_names or call_name in destructive_names
    }

    assert destructive_calls == set()


def test_weather_class_registry_entry_has_handler_or_documented_escalation():
    classes_mod = importlib.import_module(CLASSES_MODULE_NAME)

    meta = classes_mod._load_one(WEATHER_CLASS_DIR)

    assert meta is not None
    assert meta["name"] == "weather"
    assert meta["handler"] is importlib.import_module(MODULE_NAME).handle


@pytest.mark.asyncio
async def test_registered_weather_handler_returns_documented_text_shape(
    weather_handler,
    monkeypatch,
    tmp_path,
):
    classes_mod = importlib.import_module(CLASSES_MODULE_NAME)
    meta = classes_mod._load_one(WEATHER_CLASS_DIR)
    _write_weather_cache(tmp_path, monkeypatch, weather_handler, _weather_data())
    _install_llm(monkeypatch, weather_handler, "It is clear.")

    result = await meta["handler"](
        "weather",
        params={"topic": "overview", "day": None, "location": ""},
    )

    _assert_weather_followup_shape(result, topic="overview", location="")


def test_handler_source_references_only_registered_day_and_topic_lookup_tables(
    weather_handler,
):
    literals = _string_literals(MODULE_PATH)
    literal_topics = literals & weather_handler._VALID_TOPICS
    literal_day_tokens = literals & (
        set(weather_handler._WEEKDAYS) | {"today", "tomorrow", "this_week", "weekend"}
    )

    assert literal_topics <= weather_handler._VALID_TOPICS
    assert literal_day_tokens <= (
        set(weather_handler._WEEKDAYS) | {"today", "tomorrow", "this_week", "weekend"}
    )
    assert "medford" in literals
    assert "medford ma" in literals
    assert "medford, ma" in literals
