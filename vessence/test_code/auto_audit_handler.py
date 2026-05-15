"""Comprehensive audit tests for jane_web.jane_v2.classes.weather.handler.

Covers: behavioral specs from docstring, edge cases, integration mocks,
and structural invariants on lookup tables and return shapes.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: patch heavy deps so the module loads without Ollama / jane_web
# ---------------------------------------------------------------------------

_VESSENCE = Path(__file__).resolve().parents[1]
for p in [str(_VESSENCE), str(_VESSENCE / "agent_skills")]:
    if p not in sys.path:
        sys.path.insert(0, p)

_fake_models = MagicMock()
_fake_models.LOCAL_LLM = "test-model"
_fake_models.LOCAL_LLM_NUM_CTX = 4096
_fake_models.LOCAL_LLM_TIMEOUT = 10.0
_fake_models.OLLAMA_URL = "http://localhost:11434/api/generate"
_fake_models.record_ollama_activity = MagicMock()
sys.modules["jane_web.jane_v2.models"] = _fake_models

from jane_web.jane_v2.classes.weather.handler import (  # noqa: E402
    _ANSWER_TEMPLATE,
    _DAY_PHRASE_MAP,
    _FORCE_ESCALATE_PHRASES,
    _NEUTRAL_DAY_REFS,
    _VALID_TOPICS,
    _WEEKDAYS,
    _day_from_followup,
    _day_reference,
    _ensure_day_reference,
    _normalize_day,
    _phrase,
    _slice_for,
    _wrap_with_followup,
    handle,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _today_iso():
    return date.today().isoformat()


def _tomorrow_iso():
    return (date.today() + timedelta(days=1)).isoformat()


def _weekday_name(days_ahead: int):
    return _WEEKDAYS[(date.today() + timedelta(days=days_ahead)).weekday()]


@pytest.fixture
def sample_forecast():
    days = []
    for i in range(7):
        d = date.today() + timedelta(days=i)
        days.append({
            "date": d.isoformat(),
            "weekday": _WEEKDAYS[d.weekday()],
            "high": 70 + i,
            "low": 50 + i,
            "condition": "Partly cloudy",
            "wind": {"speed": 10 + i, "direction": "NW"},
            "precipitation": {"chance": 10 * i, "amount": 0.0},
        })
    return days


@pytest.fixture
def sample_data(sample_forecast):
    return {
        "forecast": sample_forecast,
        "current": {"temp": 65, "feels_like": 60, "wind": {"speed": 8, "direction": "N"}},
        "air_quality": {"us_aqi": 42, "aqi": 40},
        "pollen": {"tree": "moderate", "grass": "low"},
    }


@pytest.fixture
def minimal_data():
    return {"forecast": [], "current": {}, "air_quality": {}}


def _mock_phrase_and_cache(sample_data, phrase_text="It's 65 degrees."):
    """Context manager that patches WEATHER_PATH and _phrase for handle()."""
    wp = patch("jane_web.jane_v2.classes.weather.handler.WEATHER_PATH")
    ph = patch("jane_web.jane_v2.classes.weather.handler._phrase", new_callable=AsyncMock)

    class _Ctx:
        def __enter__(self):
            self.wp_mock = wp.__enter__()
            self.ph_mock = ph.__enter__()
            self.wp_mock.read_text.return_value = json.dumps(sample_data)
            self.ph_mock.return_value = phrase_text
            return self

        def __exit__(self, *a):
            ph.__exit__(*a)
            wp.__exit__(*a)

    return _Ctx()


def _patch_resume_deps(is_end=False):
    """Patch agent_skills imports used in the resume branch."""
    mock_end_phrase = MagicMock()
    mock_end_phrase.is_end.return_value = is_end
    mock_end_conv = MagicMock(return_value={"text": "Ok."})
    mock_utils = MagicMock(end_conversation=mock_end_conv)
    mock_agent_skills = MagicMock()
    mock_agent_skills.end_phrase = mock_end_phrase
    mock_agent_skills.private_handler_utils = mock_utils
    return patch.dict(sys.modules, {
        "agent_skills": mock_agent_skills,
        "agent_skills.end_phrase": mock_end_phrase,
        "agent_skills.private_handler_utils": mock_utils,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BEHAVIORAL TESTS — documented behavior from docstring
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocstringContract:
    """Docstring: returns {"text": ...} on success, None on escalate."""

    @pytest.mark.asyncio
    async def test_success_returns_dict_with_text(self, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("what's the weather?", params={"topic": "current"})
        assert result is not None
        assert "text" in result

    @pytest.mark.asyncio
    async def test_escalate_returns_none_on_force_phrase(self):
        result = await handle("can you search online for the forecast?")
        assert result is None

    @pytest.mark.asyncio
    async def test_escalate_returns_none_on_non_medford(self):
        result = await handle("weather in Boston", params={"topic": "current", "location": "Boston"})
        assert result is None

    @pytest.mark.asyncio
    async def test_escalate_returns_none_on_cache_miss(self):
        with patch("jane_web.jane_v2.classes.weather.handler.WEATHER_PATH") as wp:
            wp.read_text.side_effect = FileNotFoundError
            result = await handle("what's the weather?", params={"topic": "current"})
        assert result is None


class TestForceEscalatePhrases:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("phrase", _FORCE_ESCALATE_PHRASES)
    async def test_each_phrase_escalates(self, phrase):
        result = await handle(f"weather {phrase} please")
        assert result is None


class TestMedfordLocationGating:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("loc", ["medford", "medford ma", "medford, ma"])
    async def test_medford_variants_accepted(self, loc, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("weather", params={"topic": "current", "location": loc})
        assert result is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("loc", ["Boston", "New York", "Portland", "san francisco"])
    async def test_non_medford_escalates(self, loc):
        result = await handle("weather", params={"topic": "current", "location": loc})
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_location_treated_as_local(self, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("weather", params={"topic": "current", "location": ""})
        assert result is not None

    @pytest.mark.asyncio
    async def test_none_location_treated_as_local(self, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("weather", params={"topic": "current", "location": None})
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestDayFromFollowup:
    def test_none_input(self):
        assert _day_from_followup(None) is None

    def test_empty_string(self):
        assert _day_from_followup("") is None

    def test_whitespace_only(self):
        assert _day_from_followup("   ") is None

    def test_tomorrow(self):
        assert _day_from_followup("and tomorrow?") == "tomorrow"

    def test_today(self):
        assert _day_from_followup("today please") == "today"

    def test_tonight_maps_to_today(self):
        assert _day_from_followup("what about tonight?") == "today"

    def test_this_week(self):
        assert _day_from_followup("how about this week?") == "this_week"

    def test_the_week(self):
        assert _day_from_followup("tell me about the week") == "this_week"

    def test_weekend(self):
        assert _day_from_followup("weekend?") == "weekend"

    @pytest.mark.parametrize("day_name", _WEEKDAYS)
    def test_weekday_names(self, day_name):
        assert _day_from_followup(day_name) == day_name

    def test_day_after_tomorrow_returns_iso(self):
        result = _day_from_followup("day after tomorrow")
        expected = (date.today() + timedelta(days=2)).isoformat()
        assert result == expected

    def test_day_after_tomorrow_beats_tomorrow(self):
        result = _day_from_followup("day after tomorrow")
        assert result != "tomorrow"
        assert re.match(r"\d{4}-\d{2}-\d{2}", result)

    def test_no_day_detected_returns_none(self):
        assert _day_from_followup("what about pollen?") is None

    def test_very_long_input(self):
        assert _day_from_followup("a" * 10000 + " tomorrow " + "b" * 10000) == "tomorrow"

    def test_case_insensitive(self):
        assert _day_from_followup("TOMORROW") == "tomorrow"
        assert _day_from_followup("Monday") == "monday"


class TestNormalizeDay:
    def test_none_day(self, sample_forecast):
        assert _normalize_day(None, sample_forecast) is None

    def test_empty_forecast(self):
        assert _normalize_day("today", []) is None

    def test_none_forecast(self):
        assert _normalize_day("today", None) is None

    def test_today(self, sample_forecast):
        entry = _normalize_day("today", sample_forecast)
        assert entry is not None
        assert entry["date"] == _today_iso()

    def test_tomorrow(self, sample_forecast):
        entry = _normalize_day("tomorrow", sample_forecast)
        assert entry is not None
        assert entry["date"] == _tomorrow_iso()

    @pytest.mark.parametrize("multi", ["this_week", "weekend", "week"])
    def test_multi_day_specs_return_none(self, multi, sample_forecast):
        assert _normalize_day(multi, sample_forecast) is None

    @pytest.mark.parametrize("day_name", _WEEKDAYS)
    def test_weekday_name_resolves(self, day_name, sample_forecast):
        entry = _normalize_day(day_name, sample_forecast)
        if entry is not None:
            d = date.fromisoformat(entry["date"])
            assert _WEEKDAYS[d.weekday()] == day_name

    def test_iso_date(self, sample_forecast):
        entry = _normalize_day(_today_iso(), sample_forecast)
        assert entry is not None
        assert entry["date"] == _today_iso()

    def test_invalid_iso_date(self, sample_forecast):
        assert _normalize_day("2025-13-40", sample_forecast) is None

    def test_non_matching_iso_date(self, sample_forecast):
        assert _normalize_day("2099-01-01", sample_forecast) is None

    def test_garbage_string(self, sample_forecast):
        assert _normalize_day("xyzzy", sample_forecast) is None

    def test_whitespace_padding(self, sample_forecast):
        entry = _normalize_day("  today  ", sample_forecast)
        assert entry is not None
        assert entry["date"] == _today_iso()

    def test_case_insensitive(self, sample_forecast):
        assert _normalize_day("TODAY", sample_forecast) is not None

    def test_iso_with_trailing_text(self, sample_forecast):
        entry = _normalize_day(f"{_today_iso()}T12:00:00", sample_forecast)
        assert entry is not None
        assert entry["date"] == _today_iso()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. _slice_for — topic dispatch
# ═══════════════════════════════════════════════════════════════════════════════


class TestSliceFor:
    def test_pollen_with_data(self, sample_data):
        s = _slice_for("pollen", None, sample_data)
        assert s == {"topic": "pollen", "pollen": sample_data["pollen"]}

    def test_pollen_without_data_returns_none(self, minimal_data):
        assert _slice_for("pollen", None, minimal_data) is None

    def test_air_quality(self, sample_data):
        s = _slice_for("air_quality", None, sample_data)
        assert s["topic"] == "air_quality"
        assert "air_quality" in s

    def test_air_quality_empty_data(self, minimal_data):
        s = _slice_for("air_quality", None, minimal_data)
        assert s is not None
        assert s["topic"] == "air_quality"

    def test_wind_with_day_entry(self, sample_data):
        s = _slice_for("wind", "today", sample_data)
        assert s["topic"] == "wind"
        assert "wind" in s

    def test_wind_without_day(self, sample_data):
        s = _slice_for("wind", None, sample_data)
        assert s["topic"] == "wind"
        assert "current_wind" in s

    def test_precipitation_default_3_days(self, sample_data):
        s = _slice_for("precipitation", None, sample_data)
        assert s["topic"] == "precipitation"
        assert len(s["days"]) == 3

    def test_precipitation_this_week_7_days(self, sample_data):
        s = _slice_for("precipitation", "this_week", sample_data)
        assert len(s["days"]) == 7

    def test_precipitation_weekend_7_days(self, sample_data):
        s = _slice_for("precipitation", "weekend", sample_data)
        assert len(s["days"]) == 7

    def test_precipitation_single_day(self, sample_data):
        s = _slice_for("precipitation", "today", sample_data)
        assert len(s["days"]) == 1

    def test_precipitation_slim_shape(self, sample_data):
        s = _slice_for("precipitation", "today", sample_data)
        d = s["days"][0]
        assert set(d.keys()) == {"weekday", "date", "precipitation", "condition"}

    def test_forecast_weekly(self, sample_data):
        s = _slice_for("forecast", "this_week", sample_data)
        assert s["topic"] == "weekly_forecast"
        assert len(s["days"]) == 7
        for d in s["days"]:
            assert {"weekday", "high", "low", "condition"} <= set(d.keys())

    def test_forecast_single_day(self, sample_data):
        s = _slice_for("forecast", "today", sample_data)
        assert s["topic"] == "day_forecast"
        assert "day" in s

    def test_forecast_no_day_defaults_to_first(self, sample_data):
        s = _slice_for("forecast", None, sample_data)
        assert s["topic"] == "day_forecast"
        assert s["day"]["date"] == _today_iso()

    def test_forecast_empty_forecast_list(self, minimal_data):
        s = _slice_for("forecast", None, minimal_data)
        assert s["topic"] == "day_forecast"
        assert s["day"] == {}

    def test_current(self, sample_data):
        s = _slice_for("current", None, sample_data)
        assert s["topic"] == "current"
        assert "current" in s
        assert "today" in s

    def test_overview(self, sample_data):
        s = _slice_for("overview", None, sample_data)
        assert s["topic"] == "overview"
        assert "current" in s
        assert "today" in s
        assert "air_quality_aqi" in s

    def test_overview_aqi_prefers_us_aqi(self, sample_data):
        s = _slice_for("overview", None, sample_data)
        assert s["air_quality_aqi"] == 42

    def test_overview_aqi_falls_back_to_aqi(self):
        data = {"forecast": [{"date": _today_iso()}], "current": {}, "air_quality": {"aqi": 55}}
        s = _slice_for("overview", None, data)
        assert s["air_quality_aqi"] == 55

    def test_unknown_topic_falls_to_overview(self, sample_data):
        s = _slice_for("unknown_topic", None, sample_data)
        assert s["topic"] == "overview"

    def test_completely_empty_data(self):
        s = _slice_for("current", None, {})
        assert s is not None
        assert s["topic"] == "current"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. _day_reference
# ═══════════════════════════════════════════════════════════════════════════════


class TestDayReference:
    def test_today_slice(self):
        s = {"day": {"date": _today_iso(), "weekday": _weekday_name(0)}}
        assert _day_reference(s) == "today"

    def test_tomorrow_slice(self):
        s = {"day": {"date": _tomorrow_iso(), "weekday": _weekday_name(1)}}
        assert _day_reference(s) == "tomorrow"

    def test_future_weekday(self):
        for offset in range(2, 7):
            d = date.today() + timedelta(days=offset)
            s = {"day": {"date": d.isoformat(), "weekday": _WEEKDAYS[d.weekday()]}}
            assert _day_reference(s) == _WEEKDAYS[d.weekday()]

    def test_multi_day_returns_several_days(self):
        s = {"days": [{"date": _today_iso()}, {"date": _tomorrow_iso()}]}
        assert _day_reference(s) == "the next several days"

    def test_single_day_in_days_list(self):
        s = {"days": [{"date": _today_iso(), "weekday": _weekday_name(0)}]}
        assert _day_reference(s) == "today"

    def test_no_day_info_defaults_to_today(self):
        assert _day_reference({}) == "today"
        assert _day_reference({"topic": "air_quality"}) == "today"

    def test_non_dict_input(self):
        assert _day_reference("not a dict") == "today"

    def test_invalid_iso_in_day(self):
        s = {"day": {"date": "not-a-date"}}
        assert _day_reference(s) == "today"

    def test_today_key_used_as_candidate(self):
        s = {"today": {"date": _today_iso(), "weekday": _weekday_name(0)}}
        assert _day_reference(s) == "today"

    def test_far_future_uses_weekday(self):
        far = date.today() + timedelta(days=30)
        s = {"day": {"date": far.isoformat(), "weekday": _WEEKDAYS[far.weekday()]}}
        assert _day_reference(s) == _WEEKDAYS[far.weekday()]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. _ensure_day_reference
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnsureDayReference:
    def test_neutral_refs_pass_through(self):
        for ref in _NEUTRAL_DAY_REFS:
            assert _ensure_day_reference("Some text.", ref) == "Some text."

    def test_none_text(self):
        assert _ensure_day_reference(None, "tomorrow") is None

    def test_empty_text(self):
        assert _ensure_day_reference("", "tomorrow") == ""

    def test_none_day_ref(self):
        assert _ensure_day_reference("Some text.", None) == "Some text."

    def test_day_already_present(self):
        assert _ensure_day_reference("Tomorrow looks nice.", "tomorrow") == "Tomorrow looks nice."

    def test_day_missing_gets_prepended(self):
        result = _ensure_day_reference("Around 72 degrees with clear skies.", "Wednesday")
        assert result.startswith("Wednesday:")
        assert "around 72" in result

    def test_case_insensitive_detection(self):
        assert _ensure_day_reference("WEDNESDAY will be sunny.", "wednesday") == "WEDNESDAY will be sunny."

    def test_word_boundary_exact_match(self):
        text = "Sunday looks warm and breezy."
        assert _ensure_day_reference(text, "Sunday") == text

    def test_word_boundary_no_partial_match(self):
        text = "Sundays are nice."
        result = _ensure_day_reference(text, "Sunday")
        assert result.startswith("Sunday:")

    def test_lowercase_first_letter_on_prepend(self):
        result = _ensure_day_reference("High around 72.", "Friday")
        assert result == "Friday: high around 72."

    def test_empty_day_ref(self):
        assert _ensure_day_reference("Some text.", "") == "Some text."


# ═══════════════════════════════════════════════════════════════════════════════
# 6. _wrap_with_followup
# ═══════════════════════════════════════════════════════════════════════════════


class TestWrapWithFollowup:
    def test_returns_text_key(self):
        result = _wrap_with_followup("It's 65.", "current", None)
        assert "text" in result

    def test_text_contains_followup_question(self):
        result = _wrap_with_followup("It's 65.", "current", None)
        assert "Want the weather for another day?" in result["text"]

    def test_text_starts_with_spoken(self):
        result = _wrap_with_followup("It's 65.", "current", None)
        assert result["text"].startswith("It's 65.")

    def test_structured_pending_action_shape(self):
        result = _wrap_with_followup("Nice day.", "forecast", "medford")
        pa = result["structured"]["pending_action"]
        assert pa["type"] == "STAGE2_FOLLOWUP"
        assert pa["handler_class"] == "weather"
        assert pa["status"] == "awaiting_user"
        assert pa["awaiting"] == "another_day_or_stop"
        assert pa["data"]["topic"] == "forecast"
        assert pa["data"]["location"] == "medford"

    def test_none_location_becomes_empty_string(self):
        result = _wrap_with_followup("Nice.", "current", None)
        assert result["structured"]["pending_action"]["data"]["location"] == ""

    def test_expires_at_is_utc_iso(self):
        result = _wrap_with_followup("Nice.", "current", None)
        exp = result["structured"]["pending_action"]["expires_at"]
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", exp)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. handle() — resume branch (pending != None)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleResumeBranch:
    @pytest.mark.asyncio
    async def test_end_phrase_closes_conversation(self):
        with _patch_resume_deps(is_end=True):
            result = await handle("no thanks", pending={"data": {"topic": "current", "location": ""}})
        assert result is not None
        assert "text" in result

    @pytest.mark.asyncio
    async def test_no_day_in_followup_escalates(self):
        with _patch_resume_deps(is_end=False):
            result = await handle("what about pollen?", pending={"data": {"topic": "current"}})
        assert result == {"abandon_pending": True, "force_stage3": True}

    @pytest.mark.asyncio
    async def test_valid_day_followup_answers(self, sample_data):
        with _patch_resume_deps(is_end=False), _mock_phrase_and_cache(sample_data, "Tomorrow looks nice."):
            result = await handle("and tomorrow?", pending={"data": {"topic": "forecast", "location": "medford"}})
        assert result is not None
        assert "text" in result

    @pytest.mark.asyncio
    async def test_pending_without_data_key_uses_pending_itself(self):
        with _patch_resume_deps(is_end=False):
            result = await handle("what about pollen?", pending={"topic": "forecast", "location": "medford"})
        assert result == {"abandon_pending": True, "force_stage3": True}

    @pytest.mark.asyncio
    async def test_cache_fail_on_resume_escalates(self, sample_data):
        with _patch_resume_deps(is_end=False), \
             patch("jane_web.jane_v2.classes.weather.handler.WEATHER_PATH") as wp:
            wp.read_text.side_effect = FileNotFoundError
            result = await handle("tomorrow?", pending={"data": {"topic": "current"}})
        assert result == {"abandon_pending": True, "force_stage3": True}


# ═══════════════════════════════════════════════════════════════════════════════
# 8. handle() — params branch
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleParamsBranch:
    @pytest.mark.asyncio
    async def test_unknown_topic_falls_back_to_overview(self, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("weather", params={"topic": "nonexistent"})
        assert result is not None
        assert "text" in result

    @pytest.mark.asyncio
    async def test_no_params_defaults_to_overview(self, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("how's the weather?")
        assert result is not None

    @pytest.mark.asyncio
    async def test_phrase_failure_returns_none(self, sample_data):
        with _mock_phrase_and_cache(sample_data, phrase_text=None) as ctx:
            ctx.ph_mock.return_value = None
            result = await handle("weather", params={"topic": "current"})
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("topic", list(_VALID_TOPICS))
    async def test_every_valid_topic_handled(self, topic, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("weather?", params={"topic": topic})
        assert result is not None, f"Valid topic {topic!r} returned None with full data"
        assert "text" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Integration: _phrase (LLM call mock)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhraseIntegration:
    def _make_mock_client(self, response_text):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": response_text}
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    @pytest.mark.asyncio
    async def test_phrase_sends_correct_model(self):
        client = self._make_mock_client("It's 65 degrees.")
        with patch("jane_web.jane_v2.classes.weather.handler.httpx.AsyncClient", return_value=client):
            result = await _phrase({"topic": "current", "current": {"temp": 65}}, "weather?")
        assert result == "It's 65 degrees."
        body = client.post.call_args.kwargs.get("json") or client.post.call_args[1]["json"]
        assert body["model"] == "test-model"
        assert body["stream"] is False

    @pytest.mark.asyncio
    async def test_phrase_returns_none_on_exception(self):
        client = AsyncMock()
        client.post.side_effect = Exception("connection refused")
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        with patch("jane_web.jane_v2.classes.weather.handler.httpx.AsyncClient", return_value=client):
            assert await _phrase({"topic": "current"}, "weather?") is None

    @pytest.mark.asyncio
    async def test_phrase_returns_none_on_empty_response(self):
        client = self._make_mock_client("")
        with patch("jane_web.jane_v2.classes.weather.handler.httpx.AsyncClient", return_value=client):
            assert await _phrase({"topic": "current"}, "weather?") is None

    @pytest.mark.asyncio
    async def test_phrase_strips_whitespace(self):
        client = self._make_mock_client("  Nice day.  ")
        with patch("jane_web.jane_v2.classes.weather.handler.httpx.AsyncClient", return_value=client):
            result = await _phrase({"topic": "current"}, "weather?")
        assert result == "Nice day."

    @pytest.mark.asyncio
    async def test_phrase_applies_ensure_day_reference(self):
        client = self._make_mock_client("High of 72 with clouds.")
        slice_obj = {"day": {"date": _tomorrow_iso(), "weekday": _weekday_name(1)}}
        with patch("jane_web.jane_v2.classes.weather.handler.httpx.AsyncClient", return_value=client):
            result = await _phrase(slice_obj, "tomorrow?")
        assert "tomorrow" in result.lower() or "Tomorrow" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 10. STRUCTURAL INVARIANTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStructuralInvariants:
    """High-leverage: verify lookup tables, dispatch completeness, return shapes."""

    # -- _VALID_TOPICS vs _slice_for dispatch --

    def test_every_valid_topic_produces_non_none_slice(self, sample_data):
        for topic in _VALID_TOPICS:
            result = _slice_for(topic, None, sample_data)
            assert result is not None, f"_slice_for returned None for valid topic {topic!r}"

    def test_every_slice_has_topic_key(self, sample_data):
        for topic in _VALID_TOPICS:
            result = _slice_for(topic, None, sample_data)
            assert "topic" in result, f"Slice for {topic!r} missing 'topic' key"

    def test_slice_output_topics_are_known(self, sample_data):
        known = {"pollen", "air_quality", "wind", "precipitation",
                 "weekly_forecast", "day_forecast", "current", "overview"}
        for topic in _VALID_TOPICS:
            result = _slice_for(topic, None, sample_data)
            assert result["topic"] in known, \
                f"Unexpected output topic {result['topic']!r} for input {topic!r}"

    def test_multi_day_forecast_emits_weekly_forecast(self, sample_data):
        assert _slice_for("forecast", "this_week", sample_data)["topic"] == "weekly_forecast"

    def test_single_day_forecast_emits_day_forecast(self, sample_data):
        assert _slice_for("forecast", "today", sample_data)["topic"] == "day_forecast"

    # -- _WEEKDAYS correctness --

    def test_weekdays_complete_and_ordered(self):
        import calendar
        assert _WEEKDAYS == [d.lower() for d in calendar.day_name]
        assert len(_WEEKDAYS) == 7

    # -- _DAY_PHRASE_MAP invariants --

    def test_all_weekdays_in_phrase_map(self):
        phrase_keys = {phrase for phrase, _ in _DAY_PHRASE_MAP}
        for wd in _WEEKDAYS:
            assert wd in phrase_keys, f"Weekday {wd!r} missing from _DAY_PHRASE_MAP"

    def test_all_phrase_map_values_reachable(self):
        for phrase, mapped in _DAY_PHRASE_MAP:
            result = _day_from_followup(phrase)
            if phrase == "day after tomorrow":
                assert result == (date.today() + timedelta(days=2)).isoformat()
            else:
                assert result == mapped, f"{phrase!r} → expected {mapped!r}, got {result!r}"

    def test_day_after_tomorrow_precedes_tomorrow_in_map(self):
        phrases = [p for p, _ in _DAY_PHRASE_MAP]
        assert phrases.index("day after tomorrow") < phrases.index("tomorrow")

    def test_today_precedes_tonight_or_same_position(self):
        phrases = [p for p, _ in _DAY_PHRASE_MAP]
        assert phrases.index("today") <= phrases.index("tonight")

    # -- _FORCE_ESCALATE_PHRASES invariants --

    def test_escalate_phrases_all_lowercase(self):
        for phrase in _FORCE_ESCALATE_PHRASES:
            assert phrase == phrase.lower(), f"Not lowercase: {phrase!r}"

    def test_escalate_phrases_no_duplicates(self):
        assert len(_FORCE_ESCALATE_PHRASES) == len(set(_FORCE_ESCALATE_PHRASES))

    def test_escalate_phrases_nonempty(self):
        assert len(_FORCE_ESCALATE_PHRASES) > 0

    # -- _NEUTRAL_DAY_REFS --

    def test_neutral_refs_include_today(self):
        assert "today" in _NEUTRAL_DAY_REFS

    def test_neutral_refs_include_multi_day(self):
        assert "the next several days" in _NEUTRAL_DAY_REFS

    # -- Return shape: _wrap_with_followup --

    def test_wrap_followup_complete_shape(self):
        result = _wrap_with_followup("test", "current", "medford")
        assert isinstance(result, dict)
        assert isinstance(result["text"], str)
        assert "structured" in result
        pa = result["structured"]["pending_action"]
        required = {"type", "handler_class", "status", "awaiting", "data", "question", "expires_at"}
        assert required <= set(pa.keys()), f"Missing: {required - set(pa.keys())}"

    def test_wrap_followup_data_has_required_keys(self):
        result = _wrap_with_followup("test", "current", "medford")
        data = result["structured"]["pending_action"]["data"]
        assert {"awaiting", "topic", "location"} <= set(data.keys())

    # -- _ANSWER_TEMPLATE has required placeholders --

    def test_answer_template_placeholders(self):
        assert "{day_ref}" in _ANSWER_TEMPLATE
        assert "{slice}" in _ANSWER_TEMPLATE
        assert "{prompt}" in _ANSWER_TEMPLATE

    # -- handle() is async --

    def test_handle_is_coroutine_function(self):
        import asyncio
        assert asyncio.iscoroutinefunction(handle)


# ═══════════════════════════════════════════════════════════════════════════════
# 11. handle() edge cases — None/empty/malformed
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleEdgeCases:
    @pytest.mark.asyncio
    async def test_none_prompt_does_not_crash(self):
        result = await handle(None)
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_empty_prompt(self, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("")
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_malformed_cache_json(self):
        with patch("jane_web.jane_v2.classes.weather.handler.WEATHER_PATH") as wp:
            wp.read_text.return_value = "not valid json{{"
            result = await handle("weather", params={"topic": "current"})
        assert result is None

    @pytest.mark.asyncio
    async def test_google_with_trailing_space_matches(self):
        result = await handle("google the weather")
        assert result is None

    @pytest.mark.asyncio
    async def test_force_escalate_case_insensitive(self):
        result = await handle("Please SEARCH ONLINE for forecast")
        assert result is None

    @pytest.mark.asyncio
    async def test_location_with_whitespace_only(self, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("weather", params={"topic": "current", "location": "   "})
        assert result is not None

    @pytest.mark.asyncio
    async def test_topic_with_whitespace_padding(self, sample_data):
        with _mock_phrase_and_cache(sample_data):
            result = await handle("weather", params={"topic": "  current  "})
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
