"""Audit tests for jane_web.jane_v2.stage2_dispatcher."""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


VESSENCE_ROOT = Path(__file__).resolve().parent.parent
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

from jane_web.jane_v2 import stage2_dispatcher as dispatcher  # noqa: E402
from jane_web.jane_v2.stage2_dispatcher import (  # noqa: E402
    _CLASS_DESCRIPTIONS,
    _NEAR_IDENTICAL_DIST,
    _continuation_check,
    _gate_check,
    _self_correct_classification,
    dispatch,
    metadata_for,
)


def _sync_handler(return_value):
    def handle(prompt, **kwargs):
        return return_value

    return handle


def _async_handler(return_value):
    async def handle(prompt, **kwargs):
        return return_value

    return handle


def _registry(entries: dict[str, dict]) -> dict[str, dict]:
    built = {}
    for name, overrides in entries.items():
        meta = {
            "name": name,
            "pkg_name": name.replace(" ", "_"),
            "priority": 50,
            "description": f"test class {name}",
            "handler": None,
            "few_shot": [],
            "ack": None,
            "escalate_ack": None,
        }
        meta.update(overrides)
        built[name] = meta
    return built


class _FakeAsyncClient:
    def __init__(self, response_text: str = "YES", *, post_side_effect=None):
        response = MagicMock()
        response.json.return_value = {"response": response_text}
        response.raise_for_status = MagicMock()
        self.post = AsyncMock(return_value=response, side_effect=post_side_effect)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def registry_patch():
    def apply(entries: dict[str, dict]):
        return patch.object(
            dispatcher.class_registry,
            "get_registry",
            return_value=_registry(entries),
        )

    return apply


@pytest.fixture
def gate_pass():
    return patch.object(dispatcher, "_gate_check", new_callable=AsyncMock, return_value=True)


@pytest.fixture
def gate_fail():
    return patch.object(dispatcher, "_gate_check", new_callable=AsyncMock, return_value=False)


@pytest.fixture
def continuation_same():
    return patch.object(
        dispatcher,
        "_continuation_check",
        new_callable=AsyncMock,
        return_value=True,
    )


@pytest.fixture
def continuation_changed():
    return patch.object(
        dispatcher,
        "_continuation_check",
        new_callable=AsyncMock,
        return_value=False,
    )


@pytest.fixture
def fake_models():
    from jane_web.jane_v2 import models

    with patch.object(models, "LOCAL_LLM", "audit-model"), patch.object(
        models, "LOCAL_LLM_NUM_CTX", 256
    ), patch.object(models, "LOCAL_LLM_TIMEOUT", 0.25), patch.object(
        models, "OLLAMA_KEEP_ALIVE", -1
    ), patch.object(
        models, "OLLAMA_URL", "http://ollama.invalid/api/generate"
    ), patch.object(
        models, "record_ollama_activity", MagicMock()
    ):
        yield models


@pytest.mark.asyncio
async def test_dispatch_invokes_async_handler_and_returns_text_shape(registry_patch, gate_pass):
    handler = _async_handler({"text": "Hello", "extra": {"source": "test"}})
    with registry_patch({"greeting": {"handler": handler}}), gate_pass:
        result = await dispatch("greeting", "hi")

    assert result == {"text": "Hello", "extra": {"source": "test"}}


@pytest.mark.asyncio
async def test_dispatch_offloads_sync_handler_to_thread(registry_patch, gate_pass):
    handler = _sync_handler({"text": "It is noon."})
    with registry_patch({"get time": {"handler": handler}}), gate_pass, patch.object(
        dispatcher.asyncio,
        "to_thread",
        new_callable=AsyncMock,
        return_value={"text": "It is noon."},
    ) as to_thread:
        result = await dispatch("get time", "what time is it")

    to_thread.assert_called_once()
    assert result == {"text": "It is noon."}


@pytest.mark.asyncio
async def test_dispatch_awaits_async_handler_without_to_thread(registry_patch, gate_pass):
    handler = _async_handler({"text": "async result"})
    with registry_patch({"weather": {"handler": handler}}), gate_pass, patch.object(
        dispatcher.asyncio,
        "to_thread",
        new_callable=AsyncMock,
    ) as to_thread:
        result = await dispatch("weather", "weather")

    to_thread.assert_not_called()
    assert result == {"text": "async result"}


@pytest.mark.asyncio
async def test_dispatch_returns_none_for_unknown_class(registry_patch):
    with registry_patch({}):
        assert await dispatch("missing class", "hello") is None


@pytest.mark.asyncio
async def test_dispatch_returns_none_for_registered_class_without_handler(
    registry_patch,
    gate_pass,
):
    with registry_patch({"others": {"handler": None}}), gate_pass:
        assert await dispatch("others", "anything") is None


@pytest.mark.asyncio
async def test_dispatch_returns_none_when_handler_declines(registry_patch, gate_pass):
    with registry_patch({"weather": {"handler": _async_handler(None)}}), gate_pass:
        assert await dispatch("weather", "forecast") is None


@pytest.mark.asyncio
async def test_dispatch_returns_none_when_handler_crashes(registry_patch, gate_pass):
    async def bad_handler(prompt, **kwargs):
        raise RuntimeError("boom")

    with registry_patch({"weather": {"handler": bad_handler}}), gate_pass:
        assert await dispatch("weather", "forecast") is None


@pytest.mark.asyncio
async def test_dispatch_rejects_dict_without_text_key(registry_patch, gate_pass):
    with registry_patch({"greeting": {"handler": _async_handler({"response": "hi"})}}), gate_pass:
        assert await dispatch("greeting", "hi") is None


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Dispatcher calls result.get('wrong_class') before checking that result is a dict.",
    raises=AttributeError,
    strict=True,
)
async def test_dispatch_rejects_non_dict_handler_return_without_crashing(
    registry_patch,
    gate_pass,
):
    with registry_patch({"greeting": {"handler": _async_handler("plain text")}}), gate_pass:
        assert await dispatch("greeting", "hi") is None


@pytest.mark.asyncio
async def test_wrong_class_result_spawns_self_correction_thread(registry_patch, gate_pass):
    handler = _async_handler({"wrong_class": True})
    with registry_patch({"greeting": {"handler": handler}}), gate_pass, patch.object(
        dispatcher.threading,
        "Thread",
    ) as thread_cls:
        result = await dispatch("greeting", "how does the greeting handler work")

    assert result is None
    thread_cls.assert_called_once()
    assert thread_cls.call_args.kwargs["target"] is dispatcher._self_correct_classification
    assert thread_cls.call_args.kwargs["args"] == (
        "how does the greeting handler work",
        "greeting",
    )
    assert thread_cls.call_args.kwargs["daemon"] is True


@pytest.mark.asyncio
async def test_gate_rejection_blocks_handler_and_self_corrects_when_not_high_conf(
    registry_patch,
    gate_fail,
):
    handler = AsyncMock(return_value={"text": "should not run"})
    with registry_patch({"weather": {"handler": handler}}), gate_fail, patch.object(
        dispatcher.threading,
        "Thread",
    ) as thread_cls:
        result = await dispatch("weather", "meta question", stage1_conf="Low")

    assert result is None
    handler.assert_not_called()
    thread_cls.assert_called_once()


@pytest.mark.asyncio
async def test_gate_rejection_does_not_self_correct_high_confidence(
    registry_patch,
    gate_fail,
):
    handler = AsyncMock(return_value={"text": "should not run"})
    with registry_patch({"weather": {"handler": handler}}), gate_fail, patch.object(
        dispatcher.threading,
        "Thread",
    ) as thread_cls:
        result = await dispatch("weather", "meta question", stage1_conf="High")

    assert result is None
    handler.assert_not_called()
    thread_cls.assert_not_called()


@pytest.mark.asyncio
async def test_gate_is_skipped_for_near_identical_chroma_match(registry_patch):
    handler = _async_handler({"text": "ok"})
    with registry_patch({"weather": {"handler": handler}}), patch.object(
        dispatcher,
        "_gate_check",
        new_callable=AsyncMock,
        return_value=True,
    ) as gate:
        assert await dispatch("weather", "forecast", min_dist=_NEAR_IDENTICAL_DIST) == {
            "text": "ok"
        }

    gate.assert_not_called()


@pytest.mark.asyncio
async def test_gate_runs_above_near_identical_threshold(registry_patch):
    handler = _async_handler({"text": "ok"})
    with registry_patch({"weather": {"handler": handler}}), patch.object(
        dispatcher,
        "_gate_check",
        new_callable=AsyncMock,
        return_value=True,
    ) as gate:
        assert await dispatch("weather", "forecast", min_dist=_NEAR_IDENTICAL_DIST + 0.001)

    gate.assert_called_once()


@pytest.mark.asyncio
async def test_pending_followup_skips_gate_and_uses_continuation_check(
    registry_patch,
    continuation_same,
):
    async def handler(prompt, *, pending=None):
        return {"text": f"pending={pending['awaiting']}"}

    with registry_patch({"todo list": {"handler": handler}}), continuation_same, patch.object(
        dispatcher,
        "_gate_check",
        new_callable=AsyncMock,
    ) as gate:
        result = await dispatch("todo list", "clinic", pending={"awaiting": "category"})

    gate.assert_not_called()
    assert result == {"text": "pending=category"}


@pytest.mark.asyncio
async def test_pending_topic_change_abandons_without_calling_handler(
    registry_patch,
    continuation_changed,
):
    handler = AsyncMock(return_value={"text": "should not run"})
    with registry_patch({"todo list": {"handler": handler}}), continuation_changed:
        result = await dispatch(
            "todo list",
            "actually what is the weather tomorrow",
            pending={"awaiting": "category", "question": "Which category?"},
        )

    assert result == {"abandon_pending": True}
    handler.assert_not_called()


@pytest.mark.asyncio
async def test_pending_question_is_removed_before_handler_receives_pending(
    registry_patch,
    continuation_same,
):
    received = {}

    async def handler(prompt, *, pending=None):
        received["pending"] = pending
        return {"text": "ok"}

    pending = {"awaiting": "category", "question": "Which category?"}
    with registry_patch({"todo list": {"handler": handler}}), continuation_same:
        assert await dispatch("todo list", "clinic", pending=pending) == {"text": "ok"}

    assert received["pending"] == {"awaiting": "category"}
    assert pending == {"awaiting": "category", "question": "Which category?"}


@pytest.mark.asyncio
async def test_dispatch_passes_only_declared_context_pending_and_params(
    registry_patch,
    continuation_same,
):
    received = {}

    async def handler(prompt, *, context="", pending=None, params=None):
        received.update(
            {"prompt": prompt, "context": context, "pending": pending, "params": params}
        )
        return {"text": "ok"}

    with registry_patch({"shopping list": {"handler": handler}}), continuation_same:
        await dispatch(
            "shopping list",
            "milk",
            context="recent context",
            pending={"awaiting": "item"},
            params={"action": "add"},
        )

    assert received == {
        "prompt": "milk",
        "context": "recent context",
        "pending": {"awaiting": "item"},
        "params": {"action": "add"},
    }


@pytest.mark.asyncio
async def test_dispatch_tolerates_empty_prompt(registry_patch, gate_pass):
    with registry_patch({"greeting": {"handler": _async_handler({"text": "empty"})}}), gate_pass:
        assert await dispatch("greeting", "") == {"text": "empty"}


@pytest.mark.asyncio
async def test_dispatch_tolerates_empty_class_name(registry_patch):
    with registry_patch({}):
        assert await dispatch("", "hello") is None


@pytest.mark.asyncio
async def test_dispatch_tolerates_none_class_name(registry_patch):
    with registry_patch({}):
        assert await dispatch(None, "hello") is None


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="_gate_check calls prompt.lower() before its exception guard.",
    raises=AttributeError,
    strict=True,
)
async def test_dispatch_treats_none_prompt_as_malformed_input(registry_patch):
    with registry_patch({"weather": {"handler": _async_handler({"text": "ok"})}}):
        assert await dispatch("weather", None) is None


@pytest.mark.asyncio
async def test_dispatch_handles_very_long_prompt(registry_patch, gate_pass):
    long_prompt = "weather " * 20_000
    with registry_patch({"weather": {"handler": _async_handler({"text": "ok"})}}), gate_pass:
        assert await dispatch("weather", long_prompt) == {"text": "ok"}


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Malformed registry metadata is not guarded before meta.get('handler').",
    raises=AttributeError,
    strict=True,
)
async def test_dispatch_treats_malformed_registry_entry_as_decline(gate_pass):
    with patch.object(
        dispatcher.class_registry,
        "get_registry",
        return_value={"greeting": object()},
    ), gate_pass:
        assert await dispatch("greeting", "hi") is None


@pytest.mark.asyncio
async def test_gate_check_calls_ollama_and_returns_true_for_yes(fake_models):
    client = _FakeAsyncClient("YES")
    with patch("httpx.AsyncClient", return_value=client):
        assert await _gate_check("weather", "what is the weather", "") is True

    body = client.post.call_args.kwargs["json"]
    assert body["model"] == "audit-model"
    assert body["stream"] is False
    assert body["think"] is False
    assert "current/forecast weather" in body["prompt"]


@pytest.mark.asyncio
async def test_gate_check_returns_false_for_no(fake_models):
    client = _FakeAsyncClient("NO")
    with patch("httpx.AsyncClient", return_value=client):
        assert await _gate_check("weather", "how does this handler work", "") is False


@pytest.mark.asyncio
async def test_gate_check_unknown_class_fails_open_without_llm(fake_models):
    with patch("httpx.AsyncClient") as async_client:
        assert await _gate_check("not registered", "anything", "") is True

    async_client.assert_not_called()


@pytest.mark.asyncio
async def test_gate_check_fails_open_on_llm_error(fake_models):
    client = _FakeAsyncClient(post_side_effect=RuntimeError("ollama down"))
    with patch("httpx.AsyncClient", return_value=client):
        assert await _gate_check("weather", "forecast", "") is True


@pytest.mark.asyncio
async def test_continuation_check_short_replies_skip_llm(fake_models):
    with patch("httpx.AsyncClient") as async_client:
        assert await _continuation_check("todo list", "clinic", "") is True
        assert await _continuation_check("todo list", "one two three four five", "") is True

    async_client.assert_not_called()


@pytest.mark.asyncio
async def test_continuation_check_long_reply_uses_pending_question(fake_models):
    client = _FakeAsyncClient("CHANGED")
    with patch("httpx.AsyncClient", return_value=client):
        result = await _continuation_check(
            "todo list",
            "actually tell me what the weather is tomorrow",
            "recent FIFO",
            pending_question="Which category? Home, clinic, or students?",
        )

    assert result is False
    body = client.post.call_args.kwargs["json"]
    assert "Which category? Home, clinic, or students?" in body["prompt"]
    assert "recent FIFO" in body["prompt"]


@pytest.mark.asyncio
async def test_continuation_check_long_reply_legacy_fallback_uses_class_description(
    fake_models,
):
    client = _FakeAsyncClient("SAME")
    with patch("httpx.AsyncClient", return_value=client):
        assert await _continuation_check(
            "shopping list",
            "I want to add several things for the party tonight",
            "",
        )

    body = client.post.call_args.kwargs["json"]
    assert _CLASS_DESCRIPTIONS["shopping list"] in body["prompt"]


@pytest.mark.asyncio
async def test_continuation_check_fails_open_on_llm_error(fake_models):
    client = _FakeAsyncClient(post_side_effect=RuntimeError("timeout"))
    with patch("httpx.AsyncClient", return_value=client):
        assert await _continuation_check(
            "todo list",
            "this longer reply should trigger the LLM branch",
            "",
        )


def test_self_correct_classification_is_currently_disabled_and_does_not_write_db():
    fake_classifier = ModuleType("intent_classifier.v2.classifier")
    fake_classifier._load = MagicMock()
    fake_classifier._embed_fn = MagicMock(return_value=[[0.1]])
    fake_classifier.CHROMA_PATH = "/tmp/chroma"
    fake_classifier._collection = MagicMock()

    fake_config = ModuleType("jane.config")
    fake_config.get_chroma_client = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "intent_classifier.v2.classifier": fake_classifier,
            "jane.config": fake_config,
        },
    ):
        _self_correct_classification("misclassified prompt", "weather")

    fake_classifier._load.assert_not_called()
    fake_config.get_chroma_client.assert_not_called()


def test_metadata_for_reads_registry(registry_patch):
    with registry_patch({"weather": {"handler": None, "ack": "Checking weather."}}):
        assert metadata_for("weather")["ack"] == "Checking weather."
        assert metadata_for("missing") is None


def test_class_description_mapping_has_only_registered_keys():
    registry = dispatcher.class_registry.get_registry(refresh=True)
    missing = sorted(set(_CLASS_DESCRIPTIONS) - set(registry))
    assert not missing


def test_class_description_values_are_nonempty_unique_strings():
    values = list(_CLASS_DESCRIPTIONS.values())
    assert values
    assert len(values) == len(set(values))
    for key, value in _CLASS_DESCRIPTIONS.items():
        assert isinstance(value, str), key
        assert value.strip(), key


@pytest.mark.asyncio
@pytest.mark.parametrize("class_name", sorted(_CLASS_DESCRIPTIONS))
async def test_every_class_description_value_is_reachable_from_gate_prompt(
    class_name,
    fake_models,
):
    client = _FakeAsyncClient("YES")
    with patch("httpx.AsyncClient", return_value=client):
        assert await _gate_check(class_name, "please handle this", "") is True

    body = client.post.call_args.kwargs["json"]
    assert _CLASS_DESCRIPTIONS[class_name] in body["prompt"]


def _metadata_text(meta: dict) -> str:
    pkg_name = meta["pkg_name"]
    metadata_mod = importlib.import_module(f"jane_web.jane_v2.classes.{pkg_name}.metadata")
    parts = [
        inspect.getdoc(metadata_mod) or "",
        str(meta.get("description") or ""),
        str(meta.get("ack") or ""),
        str(meta.get("escalate_ack") or ""),
    ]
    return "\n".join(parts).lower()


def test_every_registered_class_has_handler_or_documented_escalation():
    registry = dispatcher.class_registry.get_registry(refresh=True)
    undocumented = {}

    for name, meta in registry.items():
        handler = meta.get("handler")
        if handler is not None:
            assert callable(handler), name
            continue

        text = _metadata_text(meta)
        if not any(
            phrase in text
            for phrase in (
                "no handler",
                "always escalates",
                "escalates to stage 3",
                "stage 3",
                "fallback",
                "delegate",
                "short-circuits",
            )
        ):
            undocumented[name] = meta.get("pkg_name")

    assert not undocumented


def test_pending_handler_class_literals_in_production_code_are_registered():
    registry = dispatcher.class_registry.get_registry(refresh=True)
    allowed_non_registry_handlers = {"stage3"}
    references: dict[str, set[str]] = {}

    for path in (VESSENCE_ROOT / "jane_web" / "jane_v2").rglob("*.py"):
        tree = ast.parse(path.read_text())
        rel = str(path.relative_to(VESSENCE_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "handler_class"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        references.setdefault(value.value, set()).add(rel)
            elif isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "handler_class"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        references.setdefault(keyword.value.value, set()).add(rel)

    missing = {
        value: sorted(paths)
        for value, paths in references.items()
        if value not in registry and value not in allowed_non_registry_handlers
    }
    assert not missing


def test_registry_few_shot_labels_reference_registered_classes_or_documented_specials():
    registry = dispatcher.class_registry.get_registry(refresh=True)
    allowed = {"others"}
    valid_labels = set(registry) | {str(meta.get("pkg_name")) for meta in registry.values()}
    bad = []

    for source_class, meta in registry.items():
        for prompt, label in meta.get("few_shot") or []:
            label_class = str(label).split(":", 1)[0].strip()
            if label_class not in valid_labels and label_class not in allowed:
                bad.append((source_class, prompt, label))

    assert bad == []


def test_registry_handlers_are_async_or_sync_callables():
    registry = dispatcher.class_registry.get_registry(refresh=True)
    for name, meta in registry.items():
        handler = meta.get("handler")
        if handler is None:
            continue
        assert callable(handler), name
        signature = inspect.signature(handler)
        assert "prompt" in signature.parameters, name


@pytest.mark.asyncio
async def test_dispatcher_filters_bad_handler_shapes_to_documented_none(
    registry_patch,
    gate_pass,
):
    for bad_return in (None, {}, {"wrong_class": True}, {"response": "missing text"}):
        with registry_patch({"greeting": {"handler": _async_handler(bad_return)}}), gate_pass:
            result = await dispatch("greeting", "hi")
        assert result is None


@pytest.mark.asyncio
async def test_destructive_dispatch_cannot_fire_when_gate_rejects(
    registry_patch,
    gate_fail,
):
    handler = AsyncMock(return_value={"text": "sent"})
    with registry_patch({"send message": {"handler": handler}}), gate_fail, patch.object(
        dispatcher.threading,
        "Thread",
    ):
        result = await dispatch("send message", "text Sarah hello", min_dist=1.0)

    assert result is None
    handler.assert_not_called()


def test_send_message_direct_send_requires_numeric_confidence_at_least_080():
    from jane_web.jane_v2.classes.send_message.handler import _has_direct_send_confidence

    assert _has_direct_send_confidence(0.80) is True
    assert _has_direct_send_confidence(0.8001) is True
    assert _has_direct_send_confidence(0.79) is False
    assert _has_direct_send_confidence("High") is False
    assert _has_direct_send_confidence(True) is False
    assert _has_direct_send_confidence(None) is False


@pytest.mark.asyncio
async def test_send_message_borderline_confidence_does_not_emit_direct_send(monkeypatch):
    from jane_web.jane_v2.classes.send_message import handler as send_message_handler

    sms_helpers = ModuleType("agent_skills.sms_helpers")
    sms_helpers.resolve_recipient = MagicMock(
        return_value={
            "phone_number": "+15551234567",
            "display_name": "Sarah",
            "source": "alias",
        }
    )
    sms_helpers.add_alias = MagicMock()
    sms_helpers._normalize_name = lambda value: value.strip().lower()
    monkeypatch.setitem(sys.modules, "agent_skills.sms_helpers", sms_helpers)

    result = await send_message_handler.handle(
        "text Sarah hello",
        params={
            "recipient": "Sarah",
            "body": "Hello",
            "intent_kind": "send",
            "confidence": 0.79,
        },
    )

    assert result is None


@pytest.mark.asyncio
async def test_send_message_confident_direct_send_returns_documented_shape(monkeypatch):
    from jane_web.jane_v2.classes.send_message import handler as send_message_handler

    sms_helpers = ModuleType("agent_skills.sms_helpers")
    sms_helpers.resolve_recipient = MagicMock(
        return_value={
            "phone_number": "+15551234567",
            "display_name": "Sarah",
            "source": "alias",
        }
    )
    sms_helpers.add_alias = MagicMock()
    sms_helpers._normalize_name = lambda value: value.strip().lower()
    monkeypatch.setitem(sys.modules, "agent_skills.sms_helpers", sms_helpers)

    result = await send_message_handler.handle(
        "text Sarah hello",
        params={
            "recipient": "Sarah",
            "body": "Hello",
            "intent_kind": "send",
            "confidence": 0.80,
        },
    )

    assert isinstance(result, dict)
    assert "text" in result
    assert "contacts.sms_send_direct" in result["text"]
    assert result.get("conversation_end") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("confidence", [None, True, "High", 0.0, 0.79])
async def test_shopping_list_destructive_actions_block_borderline_confidence(
    monkeypatch,
    confidence,
):
    from jane_web.jane_v2.classes.shopping_list import handler as shopping_handler

    shopping_mod = ModuleType("agent_skills.shopping_list")
    shopping_mod.add_item = MagicMock()
    shopping_mod.remove_item = MagicMock()
    shopping_mod.clear_list = MagicMock()
    shopping_mod.get_list = MagicMock(return_value=["milk"])
    monkeypatch.setitem(sys.modules, "agent_skills.shopping_list", shopping_mod)

    for action in ("remove", "clear"):
        result = await shopping_handler.handle(
            f"{action} milk",
            params={"action": action, "items": "milk", "confidence": confidence},
        )
        assert result is None

    shopping_mod.remove_item.assert_not_called()
    shopping_mod.clear_list.assert_not_called()


@pytest.mark.asyncio
async def test_shopping_list_destructive_actions_allow_confidence_080(monkeypatch):
    from jane_web.jane_v2.classes.shopping_list import handler as shopping_handler

    shopping_mod = ModuleType("agent_skills.shopping_list")
    shopping_mod.add_item = MagicMock()
    shopping_mod.remove_item = MagicMock()
    shopping_mod.clear_list = MagicMock()
    shopping_mod.get_list = MagicMock(return_value=["milk"])
    monkeypatch.setitem(sys.modules, "agent_skills.shopping_list", shopping_mod)

    remove_result = await shopping_handler.handle(
        "remove milk",
        params={"action": "remove", "items": "milk", "confidence": 0.80},
    )
    clear_result = await shopping_handler.handle(
        "clear the list",
        params={"action": "clear", "items": "", "confidence": 0.80},
    )

    assert "text" in remove_result
    assert "text" in clear_result
    shopping_mod.remove_item.assert_called_once_with("milk", "default", confidence=0.80)
    shopping_mod.clear_list.assert_called_once_with("default", confidence=0.80)


def test_dispatch_public_api_shape():
    assert inspect.iscoroutinefunction(dispatch)
    assert not inspect.iscoroutinefunction(metadata_for)
    assert isinstance(_CLASS_DESCRIPTIONS, dict)
    assert isinstance(_NEAR_IDENTICAL_DIST, float)
    assert 0 < _NEAR_IDENTICAL_DIST < 1
