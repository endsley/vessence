import asyncio

from jane_web.jane_v2 import stage2_dispatcher
from jane_web.jane_v2.stage2_dispatcher_prompts import (
    CLASS_DESCRIPTIONS,
    continuation_check_prompt,
    gate_check_prompt,
)


def test_stage2_dispatcher_uses_extracted_prompt_helpers():
    assert stage2_dispatcher._CLASS_DESCRIPTIONS is CLASS_DESCRIPTIONS
    assert stage2_dispatcher._continuation_check_prompt is continuation_check_prompt
    assert stage2_dispatcher._gate_check_prompt is gate_check_prompt
    assert stage2_dispatcher._post_ollama_response.__name__ == "post_ollama_response"


def test_dispatcher_gate_skip_and_pending_question_helpers() -> None:
    assert stage2_dispatcher._should_skip_gate(None, 0.10)
    assert not stage2_dispatcher._should_skip_gate({"awaiting": "category"}, 0.01)
    assert not stage2_dispatcher._should_skip_gate(None, 0.11)
    assert stage2_dispatcher._pending_question_text({"question": "Which category?"}) == (
        "Which category?"
    )
    assert stage2_dispatcher._pending_question_text(None) == ""


def test_start_self_correct_thread_preserves_background_task_shape(monkeypatch) -> None:
    started = []

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.args, self.daemon))

    monkeypatch.setattr(stage2_dispatcher.threading, "Thread", FakeThread)

    stage2_dispatcher._start_self_correct_thread("wrong prompt", "weather")

    assert started == [
        (
            stage2_dispatcher._self_correct_classification,
            ("wrong prompt", "weather"),
            True,
        )
    ]


def test_pre_handler_dispatch_check_skips_gate_for_near_identical_match(monkeypatch) -> None:
    async def fail_gate(*_args, **_kwargs):
        raise AssertionError("gate should not run")

    async def fail_continuation(*_args, **_kwargs):
        raise AssertionError("continuation should not run")

    monkeypatch.setattr(stage2_dispatcher, "_gate_check", fail_gate)
    monkeypatch.setattr(stage2_dispatcher, "_continuation_check", fail_continuation)

    assert asyncio.run(
        stage2_dispatcher._pre_handler_dispatch_check(
            "weather",
            "what is the weather",
            "",
            None,
            "Low",
            0.01,
        )
    ) is stage2_dispatcher._DISPATCH_CONTINUE


def test_pre_handler_dispatch_check_rejected_gate_self_corrects_low_conf(monkeypatch) -> None:
    started = []

    async def reject_gate(*_args, **_kwargs):
        return False

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.args, self.daemon))

    monkeypatch.setattr(stage2_dispatcher, "_gate_check", reject_gate)
    monkeypatch.setattr(stage2_dispatcher.threading, "Thread", FakeThread)

    assert asyncio.run(
        stage2_dispatcher._pre_handler_dispatch_check(
            "weather",
            "wrong prompt",
            "context",
            None,
            "Low",
            0.5,
        )
    ) is None
    assert started == [
        (
            stage2_dispatcher._self_correct_classification,
            ("wrong prompt", "weather"),
            True,
        )
    ]


def test_pre_handler_dispatch_check_rejected_gate_trusts_high_conf(monkeypatch) -> None:
    async def reject_gate(*_args, **_kwargs):
        return False

    class FailThread:
        def __init__(self, **_kwargs):
            raise AssertionError("self-correct thread should not start")

    monkeypatch.setattr(stage2_dispatcher, "_gate_check", reject_gate)
    monkeypatch.setattr(stage2_dispatcher.threading, "Thread", FailThread)

    assert asyncio.run(
        stage2_dispatcher._pre_handler_dispatch_check(
            "weather",
            "wrong prompt",
            "context",
            None,
            "High",
            0.5,
        )
    ) is None


def test_pre_handler_dispatch_check_abandons_changed_pending_topic(monkeypatch) -> None:
    calls = []

    async def changed_topic(class_name, prompt, context, pending_question=None):
        calls.append((class_name, prompt, context, pending_question))
        return False

    monkeypatch.setattr(stage2_dispatcher, "_continuation_check", changed_topic)

    assert asyncio.run(
        stage2_dispatcher._pre_handler_dispatch_check(
            "todo list",
            "what about Google Docs?",
            "recent",
            {"question": "Which category?"},
            "Low",
            1.0,
        )
    ) == {"abandon_pending": True}
    assert calls == [("todo list", "what about Google Docs?", "recent", "Which category?")]


def test_normalize_handler_result_returns_abandon_and_valid_results() -> None:
    abandon = {"abandon_pending": True, "force_stage3": True}
    valid = {"text": "Done"}

    assert stage2_dispatcher._normalize_handler_result(abandon, "todo list", "prompt") is abandon
    assert stage2_dispatcher._normalize_handler_result(valid, "todo list", "prompt") is valid


def test_normalize_handler_result_returns_none_for_decline_and_invalid_shape() -> None:
    assert stage2_dispatcher._normalize_handler_result(None, "todo list", "prompt") is None
    assert stage2_dispatcher._normalize_handler_result("not a dict", "todo list", "prompt") is None
    assert stage2_dispatcher._normalize_handler_result({}, "todo list", "prompt") is None


def test_normalize_handler_result_wrong_class_starts_self_correct(monkeypatch) -> None:
    started = []

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.args, self.daemon))

    monkeypatch.setattr(stage2_dispatcher.threading, "Thread", FakeThread)

    assert stage2_dispatcher._normalize_handler_result(
        {"wrong_class": True},
        "weather",
        "debug the weather handler",
    ) is None
    assert started == [
        (
            stage2_dispatcher._self_correct_classification,
            ("debug the weather handler", "weather"),
            True,
        )
    ]


def test_dispatcher_invalid_handler_result_returns_none(monkeypatch) -> None:
    def bad_handler(_prompt):
        return "not a dict"

    monkeypatch.setattr(
        stage2_dispatcher.class_registry,
        "get_registry",
        lambda: {"bad class": {"handler": bad_handler}},
    )

    assert asyncio.run(
        stage2_dispatcher.dispatch("bad class", "hello", min_dist=0.0)
    ) is None


def test_continuation_check_prompt_prefers_literal_pending_question():
    prompt = continuation_check_prompt(
        "todo list",
        "clinic",
        "User: previous\nJane: Which category?",
        pending_question="Which category should I read?",
    )

    assert 'Jane just asked the user this exact question:' in prompt
    assert '"Which category should I read?"' in prompt
    assert "Recent conversation:\nUser: previous" in prompt
    assert "User's reply: clinic" in prompt
    assert prompt.endswith("SAME or CHANGED:")


def test_continuation_check_prompt_uses_class_description_fallback():
    prompt = continuation_check_prompt("weather", "tomorrow", "", pending_question=None)

    assert "the user wants the current/forecast weather" in prompt
    assert "User's reply: tomorrow" in prompt


def test_gate_check_prompt_returns_none_for_unknown_class_and_preserves_examples():
    assert gate_check_prompt("unknown", "hello", "") is None

    prompt = gate_check_prompt("get time", "what time is it", "recent context")
    assert prompt is not None
    assert "The classifier predicted: the user wants the current time" in prompt
    assert '"the time you told me was wrong" → NO (complaint)' in prompt
    assert "Recent conversation:\nrecent context" in prompt
    assert prompt.endswith("Answer ONE word — YES or NO:")
