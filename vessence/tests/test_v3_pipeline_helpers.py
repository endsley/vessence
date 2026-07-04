import asyncio

from jane_web.jane_v3 import pipeline


def _base_state() -> dict:
    return {
        "cls": "timer",
        "conf": "High",
        "classification": "timer:High",
        "stage1_ms": 1,
        "stage2_ms": 2,
        "result": None,
        "stage2_ack": None,
        "fallback_ack": None,
        "force_stage3": False,
    }


def test_v3_state_helper_preserves_base_shape_and_optional_params() -> None:
    assert pipeline._v3_state("weather", "High") == {
        "cls": "weather",
        "conf": "High",
        "classification": "weather:High",
        "stage1_ms": 0,
        "stage2_ms": 0,
        "result": None,
        "stage2_ack": None,
        "fallback_ack": None,
        "force_stage3": False,
    }

    assert pipeline._v3_state(
        "weather",
        "Very High",
        stage1_ms=12,
        stage2_ms=4,
        result={"text": "Sunny"},
        stage2_ack="stage2",
        fallback_ack="fallback",
        force_stage3=True,
        params={"city": "Boston"},
    ) == {
        "cls": "weather",
        "conf": "Very High",
        "classification": "weather:Very High",
        "stage1_ms": 12,
        "stage2_ms": 4,
        "result": {"text": "Sunny"},
        "stage2_ack": "stage2",
        "fallback_ack": "fallback",
        "force_stage3": True,
        "params": {"city": "Boston"},
    }


def test_v3_pending_helpers_handle_nested_and_malformed_data() -> None:
    pending = {
        "data": {
            "awaiting": "details",
            "original_class": "weather",
        }
    }

    assert pipeline._pending_data(pending) == {
        "awaiting": "details",
        "original_class": "weather",
    }
    assert pipeline._pending_awaiting(pending) == "details"
    assert pipeline._pending_original_class(pending) == "weather"
    assert pipeline._pending_data({"data": "bad"}) == {}
    assert pipeline._pending_awaiting({"awaiting": "top", "data": "bad"}) == "top"
    assert pipeline._pending_original_class({"data": "bad"}) == ""


def test_v3_stage2_pending_for_dispatch_preserves_question() -> None:
    pending_data = {"awaiting": "category"}
    result = pipeline._stage2_pending_for_dispatch(
        {"question": "Which category?"},
        pending_data,
    )

    assert result == {"awaiting": "category", "question": "Which category?"}
    assert result is not pending_data
    assert pipeline._stage2_pending_for_dispatch(
        {"question": "Outer?"},
        {"question": "Inner?"},
    ) == {"question": "Inner?"}


def test_v3_active_pending_data_for_class_matches_current_handler_only() -> None:
    pending_action = {
        "handler_class": "timer",
        "status": "awaiting_user",
        "data": {"awaiting": "label"},
    }

    assert pipeline._active_pending_data_for_class(
        {"pending_action": pending_action},
        "timer",
    ) == {"awaiting": "label"}
    assert pipeline._active_pending_data_for_class(
        {"pending_action": pending_action},
        "todo list",
    ) is None
    assert pipeline._active_pending_data_for_class(
        {"pending_action": {**pending_action, "status": "resolved"}},
        "timer",
    ) is None


def test_v3_active_pending_data_for_class_falls_back_to_pending_record() -> None:
    pending_action = {
        "handler_class": "timer",
        "status": "awaiting_user",
        "awaiting": "label",
    }

    assert pipeline._active_pending_data_for_class(
        {"pending_action": pending_action},
        "timer",
    ) is pending_action


def test_v3_stage3_followup_state_preserves_consumed_marker_and_original_class() -> None:
    state = pipeline._stage3_followup_state(
        {"data": {"original_class": "send message"}},
        "draft_body",
        {"type": "STAGE3_FOLLOWUP", "status": "resolved"},
    )

    assert state == {
        "cls": "stage3_followup",
        "conf": "High",
        "classification": "stage3_followup:High",
        "stage1_ms": 0,
        "stage2_ms": 0,
        "result": None,
        "stage2_ack": None,
        "fallback_ack": None,
        "force_stage3": True,
        "stage3_followup_topic": "draft_body",
        "stage3_followup_original_class": "send message",
        "resolve_pending_action": {"type": "STAGE3_FOLLOWUP", "status": "resolved"},
    }


def test_v3_cancel_pending_state_uses_handler_or_others() -> None:
    assert pipeline._cancel_pending_state(
        {"handler_class": "timer"},
        {"type": "STAGE2_FOLLOWUP", "status": "cancelled"},
    ) == {
        "cls": "timer",
        "conf": "High",
        "classification": "timer:High",
        "stage1_ms": 0,
        "stage2_ms": 0,
        "result": {"text": "Ok.", "conversation_end": True},
        "stage2_ack": None,
        "fallback_ack": None,
        "force_stage3": False,
        "resolve_pending_action": {"type": "STAGE2_FOLLOWUP", "status": "cancelled"},
    }

    assert pipeline._cancel_pending_state({}, None)["classification"] == "others:High"


def test_v3_handler_result_helper_accepts_valid_stage2_result(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "_ack_for",
        lambda cls, *, escalate: f"{'fallback' if escalate else 'stage2'}:{cls}",
    )
    result = {"text": "Done"}

    state = pipeline._apply_v3_handler_result(
        _base_state(),
        result,
        "timer",
        no_stage3=False,
        safe_deflection_fn=lambda cls: {"text": f"safe:{cls}"},
    )

    assert state["result"] is result
    assert state["stage2_ack"] == "stage2:timer"
    assert state["fallback_ack"] == "fallback:timer"
    assert state["force_stage3"] is False


def test_v3_handler_result_helper_deflects_invalid_private_result(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "_ack_for",
        lambda cls, *, escalate: f"{'fallback' if escalate else 'stage2'}:{cls}",
    )

    state = pipeline._apply_v3_handler_result(
        _base_state(),
        None,
        "clinic schedules info",
        no_stage3=True,
        safe_deflection_fn=lambda cls: {"text": f"safe:{cls}"},
    )

    assert state["result"] == {"text": "safe:clinic schedules info"}
    assert state["stage2_ack"] == "stage2:clinic schedules info"
    assert state["fallback_ack"] is None
    assert state["force_stage3"] is False


def test_v3_handler_result_helper_forces_stage3_and_preserves_pending_action(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "_ack_for",
        lambda cls, *, escalate: f"{'fallback' if escalate else 'stage2'}:{cls}",
    )
    pending = {"type": "STAGE2_FOLLOWUP", "status": "cancelled"}

    state = pipeline._apply_v3_handler_result(
        _base_state(),
        {
            "text": "pivot",
            "force_stage3": True,
            "structured": {"pending_action": pending},
        },
        "todo list",
        no_stage3=False,
        safe_deflection_fn=lambda cls: {"text": f"safe:{cls}"},
    )

    assert state["result"] is None
    assert state["force_stage3"] is True
    assert state["fallback_ack"] == "fallback:todo list"
    assert state["resolve_pending_action"] is pending


def test_v3_force_stage3_state_preserves_fallback_ack(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "_ack_for",
        lambda cls, *, escalate: f"{'fallback' if escalate else 'stage2'}:{cls}",
    )

    state = pipeline._force_stage3_state(_base_state(), "weather")

    assert state["force_stage3"] is True
    assert state["fallback_ack"] == "fallback:weather"
    assert state["stage2_ack"] is None


def test_v3_terminal_stage2_state_preserves_short_circuit_shape() -> None:
    state = _base_state()
    state["force_stage3"] = True
    state["stage2_ack"] = "stage2"
    state["fallback_ack"] = "fallback"
    state["stage2_ms"] = 99

    result = {"text": "Ok.", "conversation_end": True}

    assert pipeline._terminal_stage2_state(state, result) is state
    assert state["result"] is result
    assert state["force_stage3"] is False
    assert state["stage2_ack"] is None
    assert state["fallback_ack"] is None
    assert state["stage2_ms"] == 0


def test_v3_stage_metadata_preserves_response_timing_shape() -> None:
    state = _base_state()

    assert pipeline._v3_stage_metadata(state, stage="stage2") == {
        "classification": "timer:High",
        "stage": "stage2",
        "stage1_ms": 1,
        "stage2_ms": 2,
        "stage3_ms": 0,
    }
    assert pipeline._v3_stage_metadata(
        state,
        stage="stage3",
        stage2_ms=0,
        stage3_ms=9,
    ) == {
        "classification": "timer:High",
        "stage": "stage3",
        "stage1_ms": 1,
        "stage2_ms": 0,
        "stage3_ms": 9,
    }


def test_v3_handler_result_helper_wrong_class_forces_stage3(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "_ack_for",
        lambda cls, *, escalate: f"{'fallback' if escalate else 'stage2'}:{cls}",
    )

    state = pipeline._apply_v3_handler_result(
        _base_state(),
        {"text": "", "wrong_class": True},
        "weather",
        no_stage3=False,
        safe_deflection_fn=lambda cls: {"text": f"safe:{cls}"},
    )

    assert state["force_stage3"] is True
    assert state["fallback_ack"] == "fallback:weather"


def test_v3_handler_kwargs_filters_by_signature_and_preserves_unset_params() -> None:
    def all_kwargs(_prompt, *, context=None, pending=None, params=None):
        return context, pending, params

    def no_kwargs(_prompt):
        return None

    assert pipeline._v3_handler_kwargs(
        all_kwargs,
        context="ctx",
        pending={"awaiting": "x"},
    ) == {
        "context": "ctx",
        "pending": {"awaiting": "x"},
    }
    assert pipeline._v3_handler_kwargs(
        all_kwargs,
        context="ctx",
        pending={"awaiting": "x"},
        params={"action": "read"},
    ) == {
        "context": "ctx",
        "pending": {"awaiting": "x"},
        "params": {"action": "read"},
    }
    assert pipeline._v3_handler_kwargs(
        no_kwargs,
        context="ctx",
        pending={"awaiting": "x"},
        params={"action": "read"},
    ) == {}


def test_v3_invoke_handler_supports_sync_and_async_handlers() -> None:
    def sync_handler(prompt, *, context=None):
        return {"text": f"sync:{prompt}:{context}"}

    async def async_handler(prompt, *, pending=None):
        return {"text": f"async:{prompt}:{pending['awaiting']}"}

    assert asyncio.run(
        pipeline._invoke_v3_handler(sync_handler, "hello", {"context": "ctx"})
    ) == {"text": "sync:hello:ctx"}
    assert asyncio.run(
        pipeline._invoke_v3_handler(async_handler, "hello", {"pending": {"awaiting": "x"}})
    ) == {"text": "async:hello:x"}


def test_v3_resolver_followup_missing_handler_forces_stage3(monkeypatch) -> None:
    monkeypatch.setattr(pipeline.class_registry, "get_registry", lambda: {})
    monkeypatch.setattr(
        pipeline,
        "_ack_for",
        lambda cls, *, escalate: f"ack:{cls}:{escalate}",
    )

    state = asyncio.run(
        pipeline._resolver_followup_state(
            "reply",
            "session-1",
            {"handler_class": ""},
            {},
            None,
        )
    )

    assert state == {
        "cls": "others",
        "conf": "High",
        "classification": "others:High",
        "stage1_ms": 0,
        "stage2_ms": 0,
        "result": None,
        "stage2_ack": None,
        "fallback_ack": "ack:others:True",
        "force_stage3": True,
    }


def test_v3_resolver_followup_invokes_handler_with_pending_context(monkeypatch) -> None:
    from jane_web.jane_v2 import recent_context

    def handler(_prompt, *, context=None, pending=None):
        return context, pending

    seen = {}

    async def fake_invoke(handler_arg, prompt, kwargs):
        seen["handler"] = handler_arg
        seen["prompt"] = prompt
        seen["kwargs"] = kwargs
        return {"text": "Done"}

    monkeypatch.setattr(
        pipeline.class_registry,
        "get_registry",
        lambda: {"todo list": {"handler": handler}},
    )
    monkeypatch.setattr(pipeline, "_stage2_fifo_turns", lambda cls, default: 9)
    monkeypatch.setattr(
        recent_context,
        "render_stage2_context",
        lambda session_id, *, max_turns: f"context:{session_id}:{max_turns}",
    )
    monkeypatch.setattr(pipeline, "_invoke_v3_handler", fake_invoke)
    monkeypatch.setattr(
        pipeline,
        "_ack_for",
        lambda cls, *, escalate: f"ack:{cls}:{escalate}",
    )

    state = asyncio.run(
        pipeline._resolver_followup_state(
            "reply",
            "session-1",
            {
                "handler_class": "todo list",
                "pending_data": {"awaiting": "category"},
            },
            {"question": "Which category?"},
            lambda pending, *, status, resolution: {
                "pending": pending,
                "status": status,
                "resolution": resolution,
            },
        )
    )

    assert seen == {
        "handler": handler,
        "prompt": "reply",
        "kwargs": {
            "context": "context:session-1:9",
            "pending": {
                "awaiting": "category",
                "question": "Which category?",
            },
        },
    }
    assert state["cls"] == "todo list"
    assert state["result"] == {"text": "Done"}
    assert state["stage2_ack"] == "ack:todo list:False"
    assert state["fallback_ack"] == "ack:todo list:True"
    assert state["force_stage3"] is False
    assert state["resolve_pending_action"] == {
        "pending": {"question": "Which category?"},
        "status": "resolved",
        "resolution": "answered",
    }


def test_v3_resolver_followup_invalid_result_forces_stage3(monkeypatch) -> None:
    from jane_web.jane_v2 import recent_context

    def handler(_prompt):
        return None

    async def fake_invoke(*_args, **_kwargs):
        return {"bad": "shape"}

    monkeypatch.setattr(
        pipeline.class_registry,
        "get_registry",
        lambda: {"timer": {"handler": handler}},
    )
    monkeypatch.setattr(
        recent_context,
        "render_stage2_context",
        lambda _session_id, *, max_turns: "",
    )
    monkeypatch.setattr(pipeline, "_invoke_v3_handler", fake_invoke)
    monkeypatch.setattr(
        pipeline,
        "_ack_for",
        lambda cls, *, escalate: f"ack:{cls}:{escalate}",
    )

    state = asyncio.run(
        pipeline._resolver_followup_state(
            "reply",
            "session-1",
            {"handler_class": "timer"},
            {},
            lambda *_args, **_kwargs: {"should": "not be used"},
        )
    )

    assert state["cls"] == "timer"
    assert state["result"] is None
    assert state["stage2_ack"] is None
    assert state["fallback_ack"] == "ack:timer:True"
    assert state["force_stage3"] is True
    assert "resolve_pending_action" not in state
