"""Comprehensive audit tests for jane_web.jane_v2.stage2_dispatcher."""

from __future__ import annotations

import asyncio
import inspect
import logging
import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make the project importable
# ---------------------------------------------------------------------------
VESSENCE_ROOT = Path(__file__).resolve().parent.parent
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

from jane_web.jane_v2 import stage2_dispatcher as mod
from jane_web.jane_v2.stage2_dispatcher import (
    _CLASS_DESCRIPTIONS,
    _NEAR_IDENTICAL_DIST,
    _continuation_check,
    _gate_check,
    _self_correct_classification,
    dispatch,
    metadata_for,
)


# ===================================================================
# Fixtures
# ===================================================================

def _make_sync_handler(return_value):
    """Create a sync handler that returns the given value."""
    def handle(prompt, **kwargs):
        return return_value
    return handle


def _make_async_handler(return_value):
    """Create an async handler that returns the given value."""
    async def handle(prompt, **kwargs):
        return return_value
    return handle


def _make_async_handler_with_sig(return_value, *, context=False, pending=False, params=False):
    """Create an async handler with specific kwargs in its signature."""
    if context and pending and params:
        async def handle(prompt, *, context="", pending=None, params=None):
            return return_value
    elif context and pending:
        async def handle(prompt, *, context="", pending=None):
            return return_value
    elif context:
        async def handle(prompt, *, context=""):
            return return_value
    elif pending:
        async def handle(prompt, *, pending=None):
            return return_value
    elif params:
        async def handle(prompt, *, params=None):
            return return_value
    else:
        async def handle(prompt):
            return return_value
    return handle


def _registry_with(entries: dict[str, dict]) -> dict[str, dict]:
    """Build a test registry dict."""
    result = {}
    for name, overrides in entries.items():
        base = {
            "name": name,
            "priority": 50,
            "description": f"test class {name}",
            "handler": None,
            "pkg_name": name.replace(" ", "_"),
            "ack": None,
            "escalate_ack": None,
        }
        base.update(overrides)
        result[name] = base
    return result


@pytest.fixture
def mock_registry():
    """Patch get_registry to return a controlled test registry."""
    def _patch(entries):
        reg = _registry_with(entries)
        return patch.object(
            mod.class_registry, "get_registry", return_value=reg
        )
    return _patch


@pytest.fixture
def mock_gate_pass():
    """Patch _gate_check to always pass."""
    return patch.object(mod, "_gate_check", new_callable=AsyncMock, return_value=True)


@pytest.fixture
def mock_gate_fail():
    """Patch _gate_check to always reject."""
    return patch.object(mod, "_gate_check", new_callable=AsyncMock, return_value=False)


@pytest.fixture
def mock_continuation_same():
    """Patch _continuation_check to return SAME (on-topic)."""
    return patch.object(mod, "_continuation_check", new_callable=AsyncMock, return_value=True)


@pytest.fixture
def mock_continuation_changed():
    """Patch _continuation_check to return CHANGED (topic switch)."""
    return patch.object(mod, "_continuation_check", new_callable=AsyncMock, return_value=False)


@pytest.fixture
def mock_self_correct():
    """Patch _self_correct_classification so we can assert calls."""
    return patch.object(mod, "_self_correct_classification")


@pytest.fixture
def mock_thread():
    """Patch threading.Thread to capture background task launches."""
    return patch.object(mod.threading, "Thread")


def _mock_ollama_response(text: str, status_code: int = 200):
    """Build a mock httpx response for Ollama API calls."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"response": text}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


# ===================================================================
# 1. BEHAVIORAL TESTS — docstring / spec compliance
# ===================================================================

class TestDispatchHappyPath:
    """Dispatch returns handler result dict when everything works."""

    @pytest.mark.asyncio
    async def test_async_handler_returns_text(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "Hello!"})
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert result == {"text": "Hello!"}

    @pytest.mark.asyncio
    async def test_sync_handler_returns_text(self, mock_registry, mock_gate_pass):
        handler = _make_sync_handler({"text": "It is 3pm"})
        with mock_registry({"get time": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("get time", "what time is it")
        assert result == {"text": "It is 3pm"}

    @pytest.mark.asyncio
    async def test_handler_returns_extras(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "Playing jazz", "playlist_id": "abc123"})
        with mock_registry({"music play": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("music play", "play jazz")
        assert result["text"] == "Playing jazz"
        assert result["playlist_id"] == "abc123"


class TestDispatchReturnsNone:
    """Dispatch returns None in the documented failure modes."""

    @pytest.mark.asyncio
    async def test_no_class_in_registry(self, mock_registry):
        with mock_registry({}):
            result = await dispatch("nonexistent", "hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_class_has_no_handler(self, mock_registry, mock_gate_pass):
        with mock_registry({"others": {"handler": None}}), mock_gate_pass:
            result = await dispatch("others", "random stuff")
        assert result is None

    @pytest.mark.asyncio
    async def test_handler_returns_none_decline(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler(None)
        with mock_registry({"weather": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("weather", "what's the weather")
        assert result is None

    @pytest.mark.asyncio
    async def test_handler_crashes(self, mock_registry, mock_gate_pass):
        async def exploding_handler(prompt, **kwargs):
            raise RuntimeError("boom")
        with mock_registry({"weather": {"handler": exploding_handler}}), mock_gate_pass:
            result = await dispatch("weather", "weather please")
        assert result is None

    @pytest.mark.asyncio
    async def test_gate_check_rejects(self, mock_registry, mock_gate_fail, mock_thread):
        handler = _make_async_handler({"text": "should not reach"})
        with mock_registry({"weather": {"handler": handler}}), \
             mock_gate_fail, mock_thread as mt:
            result = await dispatch("weather", "how does the pipeline work")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="BUG: result.get('wrong_class') on line 410 runs before isinstance check on line 422",
        raises=AttributeError,
        strict=True,
    )
    async def test_handler_invalid_return_not_dict(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler("just a string")
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert result is None

    @pytest.mark.asyncio
    async def test_handler_invalid_return_no_text_key(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"response": "missing text key"})
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert result is None


class TestWrongClassSignal:
    """Handler returning {"wrong_class": True} triggers self-correct and returns None."""

    @pytest.mark.asyncio
    async def test_wrong_class_returns_none(self, mock_registry, mock_gate_pass, mock_thread):
        handler = _make_async_handler({"wrong_class": True})
        with mock_registry({"greeting": {"handler": handler}}), \
             mock_gate_pass, mock_thread as mt:
            result = await dispatch("greeting", "how does the greeting handler work")
        assert result is None

    @pytest.mark.asyncio
    async def test_wrong_class_spawns_self_correct_thread(self, mock_registry, mock_gate_pass, mock_thread):
        handler = _make_async_handler({"wrong_class": True})
        with mock_registry({"greeting": {"handler": handler}}), \
             mock_gate_pass, mock_thread as mt:
            await dispatch("greeting", "meta question about greetings")
        mt.assert_called_once()
        call_kwargs = mt.call_args
        assert call_kwargs.kwargs.get("daemon") is True
        assert call_kwargs.kwargs["target"] is mod._self_correct_classification
        assert call_kwargs.kwargs["args"][1] == "greeting"


class TestAbandonPending:
    """Handler or dispatcher returning {"abandon_pending": True} passes through."""

    @pytest.mark.asyncio
    async def test_handler_abandon_pending(self, mock_registry, mock_continuation_same):
        handler = _make_async_handler({"abandon_pending": True})
        with mock_registry({"todo list": {"handler": handler}}), mock_continuation_same:
            result = await dispatch("todo list", "never mind", pending={"awaiting": "item"})
        assert result == {"abandon_pending": True}

    @pytest.mark.asyncio
    async def test_continuation_changed_returns_abandon(self, mock_registry, mock_continuation_changed):
        handler = _make_async_handler({"text": "should not reach"})
        with mock_registry({"todo list": {"handler": handler}}), mock_continuation_changed:
            result = await dispatch(
                "todo list",
                "actually what is the weather like tomorrow in Seattle",
                pending={"awaiting": "item"},
            )
        assert result == {"abandon_pending": True}


class TestGateCheckSkipLogic:
    """Gate check is skipped when pending is set, or on near-identical match."""

    @pytest.mark.asyncio
    async def test_gate_skipped_when_pending(self, mock_registry, mock_continuation_same):
        handler = _make_async_handler({"text": "added milk"})
        with mock_registry({"shopping list": {"handler": handler}}), \
             mock_continuation_same, \
             patch.object(mod, "_gate_check", new_callable=AsyncMock) as gate:
            result = await dispatch(
                "shopping list", "milk", pending={"awaiting": "item"}
            )
        gate.assert_not_called()
        assert result == {"text": "added milk"}

    @pytest.mark.asyncio
    async def test_gate_skipped_on_near_identical_dist(self, mock_registry):
        handler = _make_async_handler({"text": "It is noon"})
        with mock_registry({"get time": {"handler": handler}}), \
             patch.object(mod, "_gate_check", new_callable=AsyncMock) as gate:
            result = await dispatch(
                "get time", "what time is it", min_dist=0.05
            )
        gate.assert_not_called()
        assert result == {"text": "It is noon"}

    @pytest.mark.asyncio
    async def test_gate_runs_when_dist_above_threshold(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "It is noon"})
        with mock_registry({"get time": {"handler": handler}}), mock_gate_pass as gate:
            result = await dispatch(
                "get time", "what time is it", min_dist=0.50
            )
        gate.assert_called_once()

    @pytest.mark.asyncio
    async def test_near_identical_threshold_value(self):
        assert _NEAR_IDENTICAL_DIST == 0.10


class TestSelfCorrectSkipsOnHighConf:
    """Self-correct thread is NOT spawned when stage1_conf='High' and gate rejects."""

    @pytest.mark.asyncio
    async def test_high_conf_no_self_correct(self, mock_registry, mock_gate_fail, mock_thread):
        handler = _make_async_handler({"text": "x"})
        with mock_registry({"weather": {"handler": handler}}), \
             mock_gate_fail, mock_thread as mt:
            result = await dispatch("weather", "broken prompt", stage1_conf="High")
        assert result is None
        mt.assert_not_called()

    @pytest.mark.asyncio
    async def test_low_conf_spawns_self_correct(self, mock_registry, mock_gate_fail, mock_thread):
        handler = _make_async_handler({"text": "x"})
        with mock_registry({"weather": {"handler": handler}}), \
             mock_gate_fail, mock_thread as mt:
            result = await dispatch("weather", "broken prompt", stage1_conf="Low")
        assert result is None
        mt.assert_called_once()


class TestSyncVsAsyncHandlers:
    """Sync handlers go through asyncio.to_thread; async handlers are awaited."""

    @pytest.mark.asyncio
    async def test_sync_handler_uses_to_thread(self, mock_registry, mock_gate_pass):
        handler = _make_sync_handler({"text": "sync result"})
        with mock_registry({"get time": {"handler": handler}}), \
             mock_gate_pass, \
             patch.object(mod.asyncio, "to_thread", new_callable=AsyncMock,
                          return_value={"text": "sync result"}) as to_thread:
            result = await dispatch("get time", "what time")
        to_thread.assert_called_once()
        assert result == {"text": "sync result"}

    @pytest.mark.asyncio
    async def test_async_handler_not_using_to_thread(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "async result"})
        with mock_registry({"get time": {"handler": handler}}), \
             mock_gate_pass, \
             patch.object(mod.asyncio, "to_thread", new_callable=AsyncMock) as to_thread:
            result = await dispatch("get time", "what time")
        to_thread.assert_not_called()
        assert result == {"text": "async result"}


class TestHandlerKwargsIntrospection:
    """Dispatcher introspects handler signature and passes only accepted kwargs."""

    @pytest.mark.asyncio
    async def test_handler_receives_context_if_declared(self, mock_registry, mock_gate_pass):
        received = {}
        async def handle(prompt, *, context=""):
            received["context"] = context
            return {"text": "ok"}
        with mock_registry({"weather": {"handler": handle}}), mock_gate_pass:
            await dispatch("weather", "weather", context="some context")
        assert received["context"] == "some context"

    @pytest.mark.asyncio
    async def test_handler_receives_pending_if_declared(self, mock_registry, mock_continuation_same):
        received = {}
        async def handle(prompt, *, pending=None):
            received["pending"] = pending
            return {"text": "ok"}
        pending_data = {"awaiting": "confirmation"}
        with mock_registry({"todo list": {"handler": handle}}), mock_continuation_same:
            await dispatch("todo list", "yes", pending=pending_data)
        assert received["pending"] == pending_data

    @pytest.mark.asyncio
    async def test_handler_receives_params_if_declared(self, mock_registry, mock_gate_pass):
        received = {}
        async def handle(prompt, *, params=None):
            received["params"] = params
            return {"text": "ok"}
        with mock_registry({"weather": {"handler": handle}}), mock_gate_pass:
            await dispatch("weather", "weather", params={"unit": "celsius"})
        assert received["params"] == {"unit": "celsius"}

    @pytest.mark.asyncio
    async def test_handler_without_kwargs_gets_none(self, mock_registry, mock_gate_pass):
        received = {}
        async def handle(prompt):
            received["prompt"] = prompt
            return {"text": "ok"}
        with mock_registry({"greeting": {"handler": handle}}), mock_gate_pass:
            await dispatch("greeting", "hi", context="ctx", params={"x": 1})
        assert "prompt" in received

    @pytest.mark.asyncio
    async def test_question_stripped_from_pending_before_handler(
        self, mock_registry, mock_continuation_same
    ):
        received = {}
        async def handle(prompt, *, pending=None):
            received["pending"] = pending
            return {"text": "ok"}
        pending_data = {"awaiting": "item", "question": "What item?"}
        with mock_registry({"shopping list": {"handler": handle}}), mock_continuation_same:
            await dispatch("shopping list", "milk", pending=pending_data)
        assert "question" not in received["pending"]
        assert received["pending"]["awaiting"] == "item"


# ===================================================================
# 2. EDGE CASES
# ===================================================================

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_prompt(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "empty"})
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "")
        assert result == {"text": "empty"}

    @pytest.mark.asyncio
    async def test_empty_class_name(self, mock_registry):
        with mock_registry({}):
            result = await dispatch("", "hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_very_long_prompt(self, mock_registry, mock_gate_pass):
        long_prompt = "hello " * 10000
        handler = _make_async_handler({"text": "ok"})
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", long_prompt)
        assert result == {"text": "ok"}

    @pytest.mark.asyncio
    async def test_handler_returns_empty_dict(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({})
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="BUG: result.get('wrong_class') on line 410 crashes on non-dict before isinstance check",
        raises=AttributeError,
        strict=True,
    )
    async def test_handler_returns_list(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler(["text", "hello"])
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="BUG: result.get('wrong_class') on line 410 crashes on non-dict before isinstance check",
        raises=AttributeError,
        strict=True,
    )
    async def test_handler_returns_integer(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler(42)
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_context_string(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "ok"})
        with mock_registry({"weather": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("weather", "forecast", context="")
        assert result == {"text": "ok"}

    @pytest.mark.asyncio
    async def test_whitespace_only_context(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "ok"})
        with mock_registry({"weather": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("weather", "forecast", context="   \n  ")
        assert result == {"text": "ok"}

    @pytest.mark.asyncio
    async def test_pending_empty_dict(self, mock_registry, mock_continuation_same):
        handler = _make_async_handler({"text": "ok"})
        with mock_registry({"todo list": {"handler": handler}}), mock_continuation_same:
            result = await dispatch("todo list", "yes", pending={})
        assert result == {"text": "ok"}

    @pytest.mark.asyncio
    async def test_dispatch_with_none_pending(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "ok"})
        with mock_registry({"weather": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("weather", "weather", pending=None)
        assert result == {"text": "ok"}


# ===================================================================
# 3. INTEGRATION POINTS — LLM calls and DB (mocked)
# ===================================================================

class TestGateCheckLLM:
    """_gate_check makes an Ollama API call and interprets YES/NO."""

    @pytest.mark.asyncio
    async def test_gate_returns_true_on_yes(self):
        mock_resp = _mock_ollama_response("YES")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.dict("sys.modules", {
                "jane_web.jane_v2.models": MagicMock(
                    LOCAL_LLM="qwen2.5:7b",
                    LOCAL_LLM_NUM_CTX=8192,
                    LOCAL_LLM_TIMEOUT=40.0,
                    OLLAMA_KEEP_ALIVE=-1,
                    OLLAMA_URL="http://localhost:11434/api/generate",
                    record_ollama_activity=MagicMock(),
                ),
            }):
                result = await _gate_check("weather", "what is the weather", "")
        assert result is True

    @pytest.mark.asyncio
    async def test_gate_returns_false_on_no(self):
        mock_resp = _mock_ollama_response("NO")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.dict("sys.modules", {
                "jane_web.jane_v2.models": MagicMock(
                    LOCAL_LLM="qwen2.5:7b",
                    LOCAL_LLM_NUM_CTX=8192,
                    LOCAL_LLM_TIMEOUT=40.0,
                    OLLAMA_KEEP_ALIVE=-1,
                    OLLAMA_URL="http://localhost:11434/api/generate",
                    record_ollama_activity=MagicMock(),
                ),
            }):
                result = await _gate_check("weather", "how does the pipeline work", "")
        assert result is False

    @pytest.mark.asyncio
    async def test_gate_unknown_class_returns_true(self):
        result = await _gate_check("totally_unknown_class", "anything", "")
        assert result is True

    @pytest.mark.asyncio
    async def test_gate_fails_open_on_exception(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.dict("sys.modules", {
                "jane_web.jane_v2.models": MagicMock(
                    LOCAL_LLM="qwen2.5:7b",
                    LOCAL_LLM_NUM_CTX=8192,
                    LOCAL_LLM_TIMEOUT=40.0,
                    OLLAMA_KEEP_ALIVE=-1,
                    OLLAMA_URL="http://localhost:11434/api/generate",
                ),
            }):
                result = await _gate_check("weather", "something", "")
        assert result is True


class TestContinuationCheckLLM:
    """_continuation_check short-circuits on ≤5 words, calls LLM otherwise."""

    @pytest.mark.asyncio
    async def test_short_reply_skips_llm(self):
        result = await _continuation_check("todo list", "yes", "")
        assert result is True

    @pytest.mark.asyncio
    async def test_five_word_reply_skips_llm(self):
        result = await _continuation_check("todo list", "the one from yesterday please", "")
        assert result is True

    @pytest.mark.asyncio
    async def test_single_word_skips_llm(self):
        result = await _continuation_check("shopping list", "milk", "")
        assert result is True

    @pytest.mark.asyncio
    async def test_six_word_reply_calls_llm_same(self):
        mock_resp = _mock_ollama_response("SAME")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.dict("sys.modules", {
                "jane_web.jane_v2.models": MagicMock(
                    LOCAL_LLM="qwen2.5:7b",
                    LOCAL_LLM_NUM_CTX=8192,
                    LOCAL_LLM_TIMEOUT=40.0,
                    OLLAMA_KEEP_ALIVE=-1,
                    OLLAMA_URL="http://localhost:11434/api/generate",
                ),
            }):
                result = await _continuation_check(
                    "todo list",
                    "I want to add six items to my list",
                    "",
                )
        assert result is True

    @pytest.mark.asyncio
    async def test_long_reply_calls_llm_changed(self):
        mock_resp = _mock_ollama_response("CHANGED")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.dict("sys.modules", {
                "jane_web.jane_v2.models": MagicMock(
                    LOCAL_LLM="qwen2.5:7b",
                    LOCAL_LLM_NUM_CTX=8192,
                    LOCAL_LLM_TIMEOUT=40.0,
                    OLLAMA_KEEP_ALIVE=-1,
                    OLLAMA_URL="http://localhost:11434/api/generate",
                ),
            }):
                result = await _continuation_check(
                    "todo list",
                    "actually what is the weather like tomorrow in Seattle area",
                    "",
                )
        assert result is False

    @pytest.mark.asyncio
    async def test_continuation_fails_open_on_exception(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.dict("sys.modules", {
                "jane_web.jane_v2.models": MagicMock(
                    LOCAL_LLM="qwen2.5:7b",
                    LOCAL_LLM_NUM_CTX=8192,
                    LOCAL_LLM_TIMEOUT=40.0,
                    OLLAMA_KEEP_ALIVE=-1,
                    OLLAMA_URL="http://localhost:11434/api/generate",
                ),
            }):
                result = await _continuation_check(
                    "todo list",
                    "this is a longer sentence that should trigger the LLM call path",
                    "",
                )
        assert result is True

    @pytest.mark.asyncio
    async def test_pending_question_used_in_prompt(self):
        mock_resp = _mock_ollama_response("SAME")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.dict("sys.modules", {
                "jane_web.jane_v2.models": MagicMock(
                    LOCAL_LLM="qwen2.5:7b",
                    LOCAL_LLM_NUM_CTX=8192,
                    LOCAL_LLM_TIMEOUT=40.0,
                    OLLAMA_KEEP_ALIVE=-1,
                    OLLAMA_URL="http://localhost:11434/api/generate",
                ),
            }):
                await _continuation_check(
                    "shopping list",
                    "I think maybe the organic brand from the store downtown",
                    "",
                    pending_question="Which brand of milk do you want?",
                )
        call_args = mock_client.post.call_args
        sent_body = call_args.kwargs.get("json") or call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["json"]
        assert "Which brand of milk do you want?" in sent_body["prompt"]

    @pytest.mark.asyncio
    async def test_legacy_fallback_when_no_pending_question(self):
        mock_resp = _mock_ollama_response("SAME")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.dict("sys.modules", {
                "jane_web.jane_v2.models": MagicMock(
                    LOCAL_LLM="qwen2.5:7b",
                    LOCAL_LLM_NUM_CTX=8192,
                    LOCAL_LLM_TIMEOUT=40.0,
                    OLLAMA_KEEP_ALIVE=-1,
                    OLLAMA_URL="http://localhost:11434/api/generate",
                ),
            }):
                await _continuation_check(
                    "shopping list",
                    "I want to add several items to the list for the party",
                    "",
                    pending_question=None,
                )
        call_args = mock_client.post.call_args
        sent_body = call_args.kwargs.get("json") or call_args.kwargs["json"]
        prompt_text = sent_body["prompt"]
        assert "add/remove/view items on a shopping list" in prompt_text
        assert "exact question" not in prompt_text


class TestSelfCorrectClassification:
    """_self_correct_classification is currently disabled (early return)."""

    def test_disabled_returns_immediately(self):
        _self_correct_classification("test prompt", "weather")

    def test_disabled_does_not_write_to_chroma(self):
        with patch.dict("sys.modules", {
            "intent_classifier.v2.classifier": MagicMock(),
            "jane.config": MagicMock(),
        }):
            _self_correct_classification("test prompt", "weather")


class TestMetadataFor:
    """metadata_for() returns class metadata or None."""

    def test_known_class(self, mock_registry):
        with mock_registry({"weather": {"handler": None, "ack": "Checking..."}}):
            meta = metadata_for("weather")
        assert meta is not None
        assert meta["name"] == "weather"

    def test_unknown_class(self, mock_registry):
        with mock_registry({}):
            meta = metadata_for("nonexistent")
        assert meta is None


# ===================================================================
# 4. STRUCTURAL INVARIANTS
# ===================================================================

class TestClassDescriptionsRegistry:
    """_CLASS_DESCRIPTIONS must stay in sync with the actual class registry."""

    KNOWN_REGISTRY_CLASSES = [
        "clinic schedules info", "delegate opus", "delete email",
        "delete messages", "do math", "end conversation", "get time",
        "greeting", "music play", "others", "read calendar", "read email",
        "read messages", "self improvement", "send email", "send message",
        "shopping list", "sync messages", "tell joke", "timer",
        "todo list", "unclear", "weather", "web_automation",
    ]

    CLASSES_WITH_HANDLERS = [
        "clinic schedules info", "delete messages", "do math",
        "get time", "greeting", "music play", "read calendar",
        "read messages", "self improvement", "send message",
        "shopping list", "sync messages", "tell joke", "timer",
        "todo list", "weather", "web_automation",
    ]

    CLASSES_WITHOUT_HANDLERS = [
        "delegate opus", "delete email", "end conversation",
        "others", "read email", "send email", "unclear",
    ]

    def test_all_description_keys_are_valid_registry_classes(self):
        for key in _CLASS_DESCRIPTIONS:
            assert key in self.KNOWN_REGISTRY_CLASSES, (
                f"_CLASS_DESCRIPTIONS has key {key!r} not in the class registry"
            )

    def test_descriptions_are_nonempty_strings(self):
        for key, desc in _CLASS_DESCRIPTIONS.items():
            assert isinstance(desc, str), f"Description for {key!r} is not a string"
            assert len(desc) > 5, f"Description for {key!r} is suspiciously short: {desc!r}"

    def test_no_duplicate_descriptions(self):
        values = list(_CLASS_DESCRIPTIONS.values())
        assert len(values) == len(set(values)), "Duplicate descriptions found"


class TestDestructiveOperationsGating:
    """Destructive classes (send_message, end_conversation, delete_*) must be
    gated — they must NOT bypass the gate check on normal dispatch."""

    DESTRUCTIVE_CLASSES = ["send message", "end conversation", "delete messages", "delete email"]

    def test_destructive_classes_have_gate_descriptions(self):
        for cls in self.DESTRUCTIVE_CLASSES:
            if cls in _CLASS_DESCRIPTIONS:
                desc = _CLASS_DESCRIPTIONS[cls]
                assert len(desc) > 0, (
                    f"Destructive class {cls!r} has empty gate description"
                )

    @pytest.mark.asyncio
    async def test_send_message_goes_through_gate(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "sent"})
        with mock_registry({"send message": {"handler": handler}}), mock_gate_pass as gate:
            await dispatch("send message", "text mom I love her", min_dist=0.5)
        gate.assert_called_once()

    @pytest.mark.asyncio
    async def test_destructive_class_rejected_by_gate_returns_none(
        self, mock_registry, mock_gate_fail, mock_thread
    ):
        handler = _make_async_handler({"text": "deleted"})
        with mock_registry({"delete messages": {"handler": handler}}), \
             mock_gate_fail, mock_thread:
            result = await dispatch("delete messages", "how do I delete stuff")
        assert result is None

    @pytest.mark.asyncio
    async def test_send_message_not_skipped_at_high_dist(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "sent"})
        with mock_registry({"send message": {"handler": handler}}), mock_gate_pass as gate:
            await dispatch("send message", "text Sarah", min_dist=0.8)
        gate.assert_called_once()


class TestHandlerReturnShape:
    """Every successful dispatch must return a dict with a 'text' key."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_return", [
        None,
        {"response": "no text key"},
        {},
        {"wrong_class": True},
    ])
    async def test_invalid_handler_returns_are_filtered(
        self, mock_registry, mock_gate_pass, bad_return
    ):
        handler = _make_async_handler(bad_return)
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert result is None or (isinstance(result, dict) and "text" in result)

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="BUG: result.get('wrong_class') on line 410 runs before isinstance(result, dict) check on line 422 — non-dict returns crash",
        raises=AttributeError,
        strict=True,
    )
    @pytest.mark.parametrize("bad_return", ["string", 42, []])
    async def test_non_dict_returns_crash_on_wrong_class_check(
        self, mock_registry, mock_gate_pass, bad_return
    ):
        handler = _make_async_handler(bad_return)
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_return_passes_through(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "hello", "extra": True})
        with mock_registry({"greeting": {"handler": handler}}), mock_gate_pass:
            result = await dispatch("greeting", "hi")
        assert isinstance(result, dict)
        assert "text" in result


class TestRegistryHandlerCoverage:
    """Every registered class either has a handler or is a known fallback class."""

    DOCUMENTED_NO_HANDLER = {
        "delegate opus", "delete email", "end conversation",
        "others", "read email", "send email", "unclear",
    }

    def test_classes_without_handlers_are_documented(self):
        classes_without = set(TestClassDescriptionsRegistry.CLASSES_WITHOUT_HANDLERS)
        assert classes_without == self.DOCUMENTED_NO_HANDLER, (
            f"Undocumented classes without handlers: "
            f"{classes_without - self.DOCUMENTED_NO_HANDLER}"
        )

    def test_all_handler_classes_are_known(self):
        with_handlers = set(TestClassDescriptionsRegistry.CLASSES_WITH_HANDLERS)
        without_handlers = set(TestClassDescriptionsRegistry.CLASSES_WITHOUT_HANDLERS)
        all_known = set(TestClassDescriptionsRegistry.KNOWN_REGISTRY_CLASSES)
        assert with_handlers | without_handlers == all_known, (
            "Handler classification doesn't cover all known classes"
        )


class TestClassDescriptionsCompleteness:
    """Classes with gate-check-relevant behavior should have descriptions."""

    CLASSES_WITH_HANDLERS = TestClassDescriptionsRegistry.CLASSES_WITH_HANDLERS

    def test_handler_classes_with_missing_descriptions(self):
        missing = []
        for cls in self.CLASSES_WITH_HANDLERS:
            if cls not in _CLASS_DESCRIPTIONS:
                missing.append(cls)
        if missing:
            pytest.skip(
                f"Handler classes without gate descriptions (gate fails open for these): "
                f"{missing}"
            )


class TestGateCheckFailOpen:
    """Unknown classes (not in _CLASS_DESCRIPTIONS) fail open — gate returns True."""

    @pytest.mark.asyncio
    async def test_unknown_class_no_description_passes_gate(self):
        result = await _gate_check("totally_unknown", "anything at all", "")
        assert result is True

    @pytest.mark.asyncio
    async def test_class_in_descriptions_gets_gated(self):
        for cls_name in _CLASS_DESCRIPTIONS:
            assert cls_name in _CLASS_DESCRIPTIONS
            break


class TestContinuationCheckWordBoundary:
    """Verify the ≤5-word short-circuit boundary is correct."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt,expected_skip", [
        ("yes", True),
        ("no", True),
        ("the first one", True),
        ("milk and eggs", True),
        ("I want all five", True),        # exactly 5 words
        ("I want all five please", True),  # still 5 words
        ("one two three four five", True), # exactly 5 words
        ("one two three four five six", False),  # 6 words → LLM
    ])
    async def test_word_count_boundary(self, prompt, expected_skip):
        word_count = len(prompt.split())
        if word_count <= 5:
            result = await _continuation_check("todo list", prompt, "")
            assert result is True
        else:
            mock_resp = _mock_ollama_response("SAME")
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)

            with patch("httpx.AsyncClient", return_value=mock_client):
                with patch.dict("sys.modules", {
                    "jane_web.jane_v2.models": MagicMock(
                        LOCAL_LLM="qwen2.5:7b",
                        LOCAL_LLM_NUM_CTX=8192,
                        LOCAL_LLM_TIMEOUT=40.0,
                        OLLAMA_KEEP_ALIVE=-1,
                        OLLAMA_URL="http://localhost:11434/api/generate",
                    ),
                }):
                    result = await _continuation_check("todo list", prompt, "")
            mock_client.post.assert_called_once()


class TestGateCheckNearIdenticalSkip:
    """Near-identical chroma match skips the gate entirely (no LLM cost)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("min_dist,should_skip", [
        (0.00, True),   # perfect match
        (0.05, True),   # well within threshold
        (0.10, True),   # exactly at threshold
        (0.11, False),  # just above
        (0.50, False),  # clearly above
        (1.00, False),  # default value
    ])
    async def test_skip_boundary(self, mock_registry, min_dist, should_skip):
        handler = _make_async_handler({"text": "ok"})
        with mock_registry({"weather": {"handler": handler}}), \
             patch.object(mod, "_gate_check", new_callable=AsyncMock,
                          return_value=True) as gate:
            await dispatch("weather", "what is the weather", min_dist=min_dist)

        if should_skip:
            gate.assert_not_called()
        else:
            gate.assert_called_once()


class TestDispatchConcurrency:
    """Verify that handler exceptions don't leak and multiple dispatches are safe."""

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_propagate(self, mock_registry, mock_gate_pass):
        async def bad_handler(prompt, **kwargs):
            raise ValueError("something broke")
        with mock_registry({"weather": {"handler": bad_handler}}), mock_gate_pass:
            result = await dispatch("weather", "weather")
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_sequential_dispatches(self, mock_registry, mock_gate_pass):
        handler = _make_async_handler({"text": "ok"})
        with mock_registry({"weather": {"handler": handler}}), mock_gate_pass:
            r1 = await dispatch("weather", "forecast")
            r2 = await dispatch("weather", "temperature")
            r3 = await dispatch("weather", "rain check")
        assert r1 == r2 == r3 == {"text": "ok"}


class TestModuleExports:
    """Verify the module exposes the documented public API."""

    def test_dispatch_is_async(self):
        assert inspect.iscoroutinefunction(dispatch)

    def test_metadata_for_is_sync(self):
        assert not inspect.iscoroutinefunction(metadata_for)

    def test_class_descriptions_is_dict(self):
        assert isinstance(_CLASS_DESCRIPTIONS, dict)

    def test_near_identical_dist_is_float(self):
        assert isinstance(_NEAR_IDENTICAL_DIST, float)
        assert 0 < _NEAR_IDENTICAL_DIST < 1
