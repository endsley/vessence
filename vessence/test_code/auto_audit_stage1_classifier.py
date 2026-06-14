"""Auto-audit tests for jane_web.jane_v2.stage1_classifier.

These tests cover the Stage 1 wrapper's documented behavior, malformed
inputs, mocked ChromaDB integration, and Contract 5 routing invariants.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

VESSENCE_ROOT = Path(__file__).resolve().parent.parent
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

from jane_web.jane_v2 import classes as class_registry
from jane_web.jane_v2 import stage1_classifier as s1

CLASSES_DIR = VESSENCE_ROOT / "jane_web" / "jane_v2" / "classes"
INTENT_CLASSES_DIR = VESSENCE_ROOT / "intent_classifier" / "v2" / "classes"
PIPELINE_PATH = VESSENCE_ROOT / "jane_web" / "jane_v2" / "pipeline.py"
STAGE2_DISPATCHER_PATH = VESSENCE_ROOT / "jane_web" / "jane_v2" / "stage2_dispatcher.py"

DESTRUCTIVE_RAW_CLASSES = {
    "DELETE_EMAIL",
    "DELETE_MESSAGES",
    "END_CONVERSATION",
    "SEND_MESSAGE",
}
EFFECTIVE_MIN_CONF_OVERRIDES = {
    "END_CONVERSATION": 0.80,
}


def _mock_result(
    raw_cls: str = "WEATHER",
    confidence: float = 0.90,
    margin: float = 0.50,
    min_dist: float = 0.10,
) -> dict:
    return {
        "classification": raw_cls,
        "confidence": confidence,
        "margin": margin,
        "min_dist": min_dist,
        "latency_ms": 3.0,
    }


def _intent_classifier_class_names() -> dict[str, Path]:
    names: dict[str, Path] = {}
    for path in sorted(INTENT_CLASSES_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "CLASS_NAME" for t in node.targets):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                names[node.value.value] = path
                break
    return names


def _referenced_classifier_outputs() -> dict[str, set[str]]:
    """Collect raw classifier labels referenced by v2 audit/adversarial fixtures."""
    refs: dict[str, set[str]] = {}
    for path in sorted(INTENT_CLASSES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        stack = [data]
        labels: set[str] = set()
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                for key, value in item.items():
                    if key == "classification" and isinstance(value, str):
                        labels.add(value)
                    elif isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(item, list):
                stack.extend(item)
        if labels:
            refs[str(path.relative_to(VESSENCE_ROOT))] = labels
    return refs


def _prompt_for_raw_class(raw_cls: str) -> str:
    prompts = {
        "END_CONVERSATION": "goodbye",
        "READ_MESSAGES": "read my text messages",
        "SYNC_MESSAGES": "sync my text messages",
        "READ_EMAIL": "check my email",
        "READ_CALENDAR": "show my calendar",
        "CLINIC_SCHEDULES_INFO": "clinic patient schedule",
        "DELETE_EMAIL": "delete that email",
        "DELETE_MESSAGES": "delete that text message",
        "SEND_MESSAGE": "text Kathia I am running late",
        "DELEGATE_OPUS": "open ended thought",
        "FORCE_STAGE3": "plain prompt",
    }
    return prompts.get(raw_cls, f"sample prompt for {raw_cls.lower()}")


@pytest.fixture
def chroma_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    fake_intent = types.ModuleType("intent_classifier")
    fake_v2 = types.ModuleType("intent_classifier.v2")
    fake_classifier = types.ModuleType("intent_classifier.v2.classifier")
    fake_classifier.stage1_classify = mock
    monkeypatch.setitem(sys.modules, "intent_classifier", fake_intent)
    monkeypatch.setitem(sys.modules, "intent_classifier.v2", fake_v2)
    monkeypatch.setitem(sys.modules, "intent_classifier.v2.classifier", fake_classifier)
    return mock


AMBIGUOUS_END_CONVERSATION_PROMPTS = (
    "Can you stop playing music?",
    "That's enough about the weather, what about tomorrow?",
    "I'm done with my shopping list, now what about dinner?",
    "Forget about the timer and set a new one.",
    "Thanks for the weather, now play some music.",
    "All set with the playlist, what's the time?",
    "Never mind the email, check my calendar instead.",
    "Drop the current topic and tell me a joke.",
    "I'm good on that, but what about tomorrow's forecast?",
    "OK great, now send a message to mom.",
    "Cancel the timer please and set a new one for 10 minutes.",
    "Stop talking about the weather and play jazz.",
    "Enough with the jokes, read my messages.",
    "Nah, not that song, play something else.",
    "Skip it, I want to hear the news instead.",
    "I'm done editing my shopping list, show it to me.",
    "Leave it alone and move on to the next task.",
    "That's all for emails, what about texts?",
    "We're done with that topic, switch to cooking.",
    "No thanks on the reminder, just tell me the time.",
    "Stop the countdown but keep listening.",
    "Cancel that message draft and start a new one.",
    "Dismiss the notification but answer my question.",
    "Quiet the music and tell me the weather.",
    "Silence the alarm and open my calendar.",
    "Enough about timers, show my TODO list.",
    "Forget it for the email, text Kathia instead.",
    "Drop it from the list, then read the list.",
    "Abort the browser task and explain why it failed.",
    "Not now for music, check the clinic schedule.",
    "Go away from this topic and talk about Python.",
    "All good for now, but did anyone text me?",
    "All set there, now sync messages.",
    "Ok done with that, what's next?",
    "Roger that, add milk to my shopping list.",
    "Thanks, can you also check my inbox?",
    "Thank you for explaining, but I have another question.",
    "Bye is the word I want to send in the text.",
    "The conversation over dinner was strange.",
    "Tell me about good night sleep habits.",
    "I need to cancel my subscription; how do I do that?",
    "The drop in temperature is concerning.",
    "What does silence mean in meditation?",
    "Stop and think about this for a second.",
    "Nope, use the other playlist.",
    "Never mind the previous city; use Boston.",
    "Close the browser tab and summarize the page.",
    "End the timer after five minutes.",
    "Shush the volume, then continue.",
    "Ok thanks, now tell me today's date.",
)


def test_ambiguous_prompt_fixture_has_contract_required_size() -> None:
    assert len(AMBIGUOUS_END_CONVERSATION_PROMPTS) >= 50


def test_stage1_source_has_no_direct_llm_client_calls() -> None:
    source = Path(s1.__file__).read_text(encoding="utf-8").lower()
    forbidden = ("openai", "anthropic", "ollama", "requests.post", "httpx.")
    assert not [token for token in forbidden if token in source]


def test_class_map_keys_are_uppercase_and_values_are_registry_style() -> None:
    assert s1._CLASS_MAP
    for raw_cls, pipeline_name in s1._CLASS_MAP.items():
        assert raw_cls == raw_cls.upper()
        assert pipeline_name == pipeline_name.lower()
        assert raw_cls.strip() == raw_cls
        assert pipeline_name.strip() == pipeline_name
        assert pipeline_name


def test_class_map_values_are_pipeline_registry_keys() -> None:
    registry = class_registry.get_registry(refresh=True)
    missing = sorted(set(s1._CLASS_MAP.values()) - set(registry))
    assert not missing, (
        "_CLASS_MAP emits names that are not in jane_web.jane_v2.classes registry: "
        f"{missing}"
    )


def test_class_map_values_have_class_pack_directories() -> None:
    missing = []
    for pipeline_name in sorted(set(s1._CLASS_MAP.values())):
        pack_dir = CLASSES_DIR / pipeline_name.replace(" ", "_")
        if not pack_dir.is_dir():
            missing.append(f"{pipeline_name} -> {pack_dir}")
    assert not missing


def test_all_intent_classifier_class_names_are_mapped_or_explicitly_escalated() -> None:
    intent_names = _intent_classifier_class_names()
    missing = {
        name: str(path.relative_to(VESSENCE_ROOT))
        for name, path in intent_names.items()
        if name not in s1._CLASS_MAP
    }
    assert not missing, (
        "Every ChromaDB CLASS_NAME should be explicit in _CLASS_MAP. "
        "If a class is exemplar-only, map it to 'others' so fallback routing is intentional. "
        f"Missing: {missing}"
    )


def test_all_classifier_output_labels_referenced_by_fixtures_are_mapped() -> None:
    referenced = _referenced_classifier_outputs()
    missing: dict[str, list[str]] = {}
    for path, labels in referenced.items():
        unknown = sorted(label for label in labels if label not in s1._CLASS_MAP)
        if unknown:
            missing[path] = unknown
    assert not missing, (
        "Classifier fixtures reference raw labels that stage1_classifier._CLASS_MAP "
        f"cannot route: {missing}"
    )


def test_proven_and_strict_sets_reference_known_raw_classes() -> None:
    assert not (s1.PROVEN_CLASSES & s1.STRICT_CLASSES)
    assert s1.PROVEN_CLASSES <= set(s1._CLASS_MAP)
    assert s1.STRICT_CLASSES <= set(s1._CLASS_MAP)


def test_strict_classes_have_keyword_guards_and_strict_gate() -> None:
    assert s1.STRICT_CLASSES <= set(s1._STRICT_KEYWORDS)
    assert set(s1._STRICT_KEYWORDS) <= s1.STRICT_CLASSES
    for raw_cls in s1.STRICT_CLASSES:
        assert s1._gate_for(raw_cls) == s1._GATE_STRICT
        assert s1._GATE_STRICT["conf"] >= 1.0
        assert s1._GATE_STRICT["margin"] >= 0.40


def test_gate_threshold_order_is_precision_first() -> None:
    assert s1._GATE_NEW["conf"] >= 0.80
    assert s1._GATE_NEW["conf"] > s1._GATE_PROVEN["conf"]
    assert s1._GATE_STRICT["conf"] >= s1._GATE_NEW["conf"]
    for gate in (s1._GATE_NEW, s1._GATE_PROVEN, s1._GATE_STRICT):
        assert gate["margin"] > 0


def test_destructive_raw_classes_require_at_least_080_gate() -> None:
    missing = sorted(DESTRUCTIVE_RAW_CLASSES - set(s1._CLASS_MAP))
    assert not missing
    too_loose = {
        raw_cls: {
            "effective_conf": EFFECTIVE_MIN_CONF_OVERRIDES.get(
                raw_cls,
                s1._gate_for(raw_cls)["conf"],
            ),
            "gate": s1._gate_for(raw_cls),
        }
        for raw_cls in sorted(DESTRUCTIVE_RAW_CLASSES)
        if EFFECTIVE_MIN_CONF_OVERRIDES.get(raw_cls, s1._gate_for(raw_cls)["conf"]) < 0.80
    }
    assert not too_loose, (
        "Destructive classes must not dispatch on a loose Stage 1 gate. "
        f"Thresholds below 0.80: {too_loose}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_cls,expected_name", sorted(s1._CLASS_MAP.items()))
async def test_every_class_map_entry_is_reachable_from_one_chroma_output(
    raw_cls: str,
    expected_name: str,
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result(raw_cls, confidence=1.0, margin=1.0, min_dist=0.01)
    cls, _, _ = await s1.classify(_prompt_for_raw_class(raw_cls))
    assert cls == expected_name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_cls",
    sorted(raw_cls for raw_cls, mapped in s1._CLASS_MAP.items() if mapped == "others"),
)
async def test_every_others_mapping_is_always_low_confidence(
    raw_cls: str,
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result(raw_cls, confidence=1.0, margin=1.0)
    cls, conf, dist = await s1.classify("plain prompt")
    assert (cls, conf) == ("others", "Low")
    assert isinstance(dist, float)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_cls",
    ["DELEGATE_OPUS", "FORCE_STAGE3", "UNKNOWN_FROM_CHROMA"],
)
async def test_fallback_and_unknown_classes_always_return_others_low(
    raw_cls: str,
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result(raw_cls, confidence=1.0, margin=1.0)
    cls, conf, dist = await s1.classify("plain prompt")
    assert cls == "others"
    assert conf == "Low"
    assert isinstance(dist, float)


@pytest.mark.asyncio
async def test_force_stage3_phrase_bypasses_chromadb_and_returns_others_low(
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result("WEATHER", confidence=1.0, margin=1.0)
    cls, conf, dist = await s1.classify("please think this through carefully")
    assert (cls, conf, dist) == ("others", "Low", 1.0)
    chroma_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_chromadb_is_awaited_once_for_normal_prompt(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("WEATHER", confidence=0.90, margin=0.50)
    cls, conf, _ = await s1.classify("what is the weather")
    assert (cls, conf) == ("weather", "High")
    chroma_mock.assert_awaited_once_with("what is the weather")


@pytest.mark.asyncio
async def test_system_markers_are_stripped_before_chromadb(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("READ_MESSAGES", confidence=1.0, margin=0.60)
    raw = '[TOOL_RESULT:{"tool":"sms","data":{"body":"send message"}}] read my texts'
    cls, conf, _ = await s1.classify(raw)
    assert (cls, conf) == ("read messages", "High")
    sent_prompt = chroma_mock.await_args.args[0]
    assert "TOOL_RESULT" not in sent_prompt
    assert "send message" not in sent_prompt
    assert sent_prompt == "read my texts"


@pytest.mark.asyncio
async def test_chromadb_failure_falls_back_to_others_low(chroma_mock: AsyncMock) -> None:
    chroma_mock.side_effect = RuntimeError("vector db unavailable")
    assert await s1.classify("hello") == ("others", "Low", 1.0)


@pytest.mark.asyncio
async def test_missing_chromadb_fields_default_to_delegate_low(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = {}
    cls, conf, dist = await s1.classify("hello")
    assert (cls, conf, dist) == ("others", "Low", 1.0)


@pytest.mark.asyncio
async def test_classify_returns_documented_three_tuple(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("GREETING", confidence=0.90, margin=0.50)
    result = await s1.classify("hello")
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert result[0] == "greeting"
    assert result[1] in {"High", "Low"}
    assert isinstance(result[2], float)


@pytest.mark.asyncio
async def test_proven_class_below_gate_is_low(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("WEATHER", confidence=0.59, margin=0.50)
    cls, conf, _ = await s1.classify("weather")
    assert (cls, conf) == ("weather", "Low")


@pytest.mark.asyncio
async def test_proven_class_below_margin_is_low(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("WEATHER", confidence=0.90, margin=0.19)
    cls, conf, _ = await s1.classify("weather")
    assert (cls, conf) == ("weather", "Low")


@pytest.mark.asyncio
async def test_new_class_requires_new_class_gate(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("SHOPPING_LIST", confidence=0.79, margin=0.50)
    cls, conf, _ = await s1.classify("add milk to my shopping list")
    assert (cls, conf) == ("shopping list", "Low")


@pytest.mark.asyncio
async def test_strict_class_requires_unanimous_confidence(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("READ_EMAIL", confidence=0.99, margin=1.0)
    cls, conf, _ = await s1.classify("check my email")
    assert (cls, conf) == ("read email", "Low")


@pytest.mark.asyncio
async def test_strict_class_requires_literal_keyword(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("READ_MESSAGES", confidence=1.0, margin=1.0)
    cls, conf, _ = await s1.classify("any updates from yesterday")
    assert (cls, conf) == ("read messages", "Low")


@pytest.mark.asyncio
async def test_strict_class_with_unanimous_votes_and_keyword_can_be_high(
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result("READ_MESSAGES", confidence=1.0, margin=1.0)
    cls, conf, _ = await s1.classify("read my text messages")
    assert (cls, conf) == ("read messages", "High")


@pytest.mark.asyncio
async def test_end_conversation_requires_at_least_080_even_when_proven(
    chroma_mock: AsyncMock,
) -> None:
    assert "END_CONVERSATION" in s1.PROVEN_CLASSES
    chroma_mock.return_value = _mock_result("END_CONVERSATION", confidence=0.79, margin=1.0)
    cls, conf, _ = await s1.classify("goodbye")
    assert (cls, conf) == ("end conversation", "Low")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_cls,prompt",
    [
        ("DELETE_EMAIL", "delete that email"),
        ("DELETE_MESSAGES", "delete that text message"),
        ("SEND_MESSAGE", "text Kathia I am running late"),
    ],
)
async def test_destructive_action_classes_do_not_fire_on_borderline_confidence(
    raw_cls: str,
    prompt: str,
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result(raw_cls, confidence=0.79, margin=1.0)
    cls, conf, _ = await s1.classify(prompt)
    assert cls == s1._CLASS_MAP[raw_cls]
    assert conf == "Low"


@pytest.mark.asyncio
async def test_end_conversation_accepts_080_with_complete_ending_phrase(
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result("END_CONVERSATION", confidence=0.80, margin=1.0)
    cls, conf, _ = await s1.classify("goodbye")
    assert (cls, conf) == ("end conversation", "High")


@pytest.mark.asyncio
async def test_end_conversation_high_embedding_without_phrase_is_low(
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result("END_CONVERSATION", confidence=1.0, margin=1.0)
    prompt = "I think setting the context window to 1024 is not long enough"
    cls, conf, _ = await s1.classify(prompt)
    assert (cls, conf) == ("end conversation", "Low")


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", AMBIGUOUS_END_CONVERSATION_PROMPTS)
async def test_end_conversation_does_not_fire_on_ambiguous_prompts(
    prompt: str,
    chroma_mock: AsyncMock,
) -> None:
    chroma_mock.return_value = _mock_result("END_CONVERSATION", confidence=1.0, margin=1.0)
    cls, conf, _ = await s1.classify(prompt)
    assert cls == "end conversation"
    assert conf == "Low"


def test_end_conversation_phrase_guard_accepts_only_complete_endings() -> None:
    for phrase in ("bye", "goodbye", "thanks", "all done", "stop", "end conversation"):
        assert s1._end_conversation_phrase_ok(phrase)
    for phrase in (
        "stop and think about this",
        "tell me about the end of the conversation",
        "enough about weather, what about news",
        "cancel the timer and set a new one",
    ):
        assert not s1._end_conversation_phrase_ok(phrase)


def test_strict_keyword_guard_blocks_prefix_false_positive() -> None:
    assert s1._strict_keyword_ok("READ_CALENDAR", "show my schedule")
    assert not s1._strict_keyword_ok("READ_CALENDAR", "reschedule the meeting")
    assert s1._strict_keyword_ok("READ_EMAIL", "check my emails")
    assert not s1._strict_keyword_ok("READ_EMAIL", "any updates")
    assert s1._strict_keyword_ok("WEATHER", "any prompt")


def test_clinic_schedule_guard_rejects_personal_schedule_without_clinic_context() -> None:
    assert not s1._clinic_schedule_ok("what is on my schedule today")
    assert s1._clinic_schedule_ok("what is on my schedule at the clinic")
    assert s1._clinic_schedule_ok("show Kathia her schedule")


def test_strip_system_markers_handles_tool_result_with_nested_json() -> None:
    raw = '[TOOL_RESULT:{"tool":"sms","data":{"id":1,"body":"hi"}}] any messages?'
    assert s1._strip_system_markers(raw) == "any messages?"


def test_strip_system_markers_handles_sms_and_phone_blocks() -> None:
    sms = "[SMS SEND REQUEST to 123]\nbody\n[END SMS SEND REQUEST]\ndid it send?"
    phone = "[PHONE TOOL RESULTS]\nbody\n[END PHONE TOOL RESULTS]\nwhat happened?"
    assert s1._strip_system_markers(sms) == "did it send?"
    assert s1._strip_system_markers(phone) == "what happened?"


def test_strip_system_markers_handles_truncated_or_malformed_markers() -> None:
    assert s1._strip_system_markers("hello [SMS SEND REQUEST to 123]\nbody") == "hello"
    malformed = "[TOOL_RESULT:{not json] what time is it?"
    assert "what time" in s1._strip_system_markers(malformed)


def test_strip_system_markers_normalizes_subject_change_and_plural_weather() -> None:
    assert s1._strip_system_markers("change the subject to weather") == "weather"
    assert s1._strip_system_markers("let's talk about music") == "music"
    assert s1._strip_system_markers("how are the weathers today") == "how are the weather today"


def test_strip_system_markers_preserves_plain_or_fully_stripped_text() -> None:
    plain = "What's the weather like?"
    marker_only = '[TOOL_RESULT:{"status":"ok"}]'
    assert s1._strip_system_markers(plain) == plain
    assert s1._strip_system_markers(marker_only) == marker_only


@pytest.mark.asyncio
async def test_empty_input_routes_to_mocked_delegate_low(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("DELEGATE_OPUS", confidence=0.0, margin=0.0)
    cls, conf, dist = await s1.classify("")
    assert (cls, conf) == ("others", "Low")
    assert isinstance(dist, float)


@pytest.mark.asyncio
async def test_whitespace_input_does_not_crash(chroma_mock: AsyncMock) -> None:
    chroma_mock.return_value = _mock_result("DELEGATE_OPUS", confidence=0.0, margin=0.0)
    cls, conf, _ = await s1.classify("   \n\t   ")
    assert (cls, conf) == ("others", "Low")


@pytest.mark.asyncio
async def test_very_long_input_is_passed_to_chromadb_wrapper(chroma_mock: AsyncMock) -> None:
    long_prompt = "what is the weather " * 5000
    chroma_mock.return_value = _mock_result("WEATHER", confidence=0.90, margin=0.50)
    cls, conf, _ = await s1.classify(long_prompt)
    assert (cls, conf) == ("weather", "High")
    chroma_mock.assert_awaited_once_with(long_prompt.strip())


@pytest.mark.asyncio
async def test_none_input_is_rejected_as_malformed_prompt(chroma_mock: AsyncMock) -> None:
    with pytest.raises((AttributeError, TypeError)):
        await s1.classify(None)  # type: ignore[arg-type]
    chroma_mock.assert_not_awaited()


def test_registered_classes_have_handlers_or_documented_escalation_path() -> None:
    registry = class_registry.get_registry(refresh=True)
    pipeline_source = PIPELINE_PATH.read_text(encoding="utf-8")
    no_handler_failures = []
    for class_name, meta in registry.items():
        if meta.get("handler") is not None:
            continue
        pkg = meta["pkg_name"]
        metadata_mod = __import__(
            f"jane_web.jane_v2.classes.{pkg}.metadata",
            fromlist=["METADATA"],
        )
        text = (
            (metadata_mod.__doc__ or "")
            + "\n"
            + str(meta.get("description") or "")
            + "\n"
            + str(meta.get("escalate_ack") or "")
        ).lower()
        documented = "no handler" in text or "escalat" in text or "short-circuit" in text
        pipeline_managed = class_name == "end conversation" and 'cls == "end conversation"' in pipeline_source
        if not documented and not pipeline_managed:
            no_handler_failures.append(class_name)
    assert not no_handler_failures


def test_registered_handlers_are_callable_and_accept_prompt_argument() -> None:
    registry = class_registry.get_registry(refresh=True)
    failures = []
    for class_name, meta in registry.items():
        handler = meta.get("handler")
        if handler is None:
            continue
        signature = inspect.signature(handler)
        required = [
            p
            for p in signature.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if not callable(handler) or not required or required[0].name != "prompt" or len(required) > 1:
            failures.append(f"{class_name}: {signature}")
    assert not failures


def test_registered_handler_source_mentions_documented_result_shape() -> None:
    registry = class_registry.get_registry(refresh=True)
    markers = (
        '"text"',
        "'text'",
        '"wrong_class"',
        "'wrong_class'",
        '"abandon_pending"',
        "'abandon_pending'",
        "return None",
    )
    missing = []
    for class_name, meta in registry.items():
        handler = meta.get("handler")
        if handler is None:
            continue
        source = inspect.getsource(handler)
        if not any(marker in source for marker in markers):
            missing.append(class_name)
    assert not missing


@pytest.mark.asyncio
async def test_dispatcher_rejects_handler_result_without_text_or_control_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jane_web.jane_v2 import stage2_dispatcher

    def bad_handler(prompt: str) -> dict:
        return {"payload": "missing text"}

    monkeypatch.setattr(stage2_dispatcher, "_gate_check", AsyncMock(return_value=True))
    monkeypatch.setattr(
        stage2_dispatcher.class_registry,
        "get_registry",
        lambda: {"weather": {"handler": bad_handler}},
    )
    assert await stage2_dispatcher.dispatch("weather", "weather", stage1_conf="High") is None


@pytest.mark.asyncio
async def test_dispatcher_accepts_handler_result_with_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jane_web.jane_v2 import stage2_dispatcher

    def good_handler(prompt: str) -> dict:
        return {"text": "ok"}

    monkeypatch.setattr(stage2_dispatcher, "_gate_check", AsyncMock(return_value=True))
    monkeypatch.setattr(
        stage2_dispatcher.class_registry,
        "get_registry",
        lambda: {"weather": {"handler": good_handler}},
    )
    assert await stage2_dispatcher.dispatch("weather", "weather", stage1_conf="High") == {"text": "ok"}


def test_pipeline_dispatch_condition_matches_stage1_confidence_contract() -> None:
    source = PIPELINE_PATH.read_text(encoding="utf-8")
    assert 'conf in ("High", "Medium") and cls != "others"' in source
    assert 'cls == "end conversation"' in source


def test_stage2_dispatcher_documents_invalid_handler_shape_guard() -> None:
    source = STAGE2_DISPATCHER_PATH.read_text(encoding="utf-8")
    assert '"text" not in result' in source
    assert "returned invalid shape" in source
