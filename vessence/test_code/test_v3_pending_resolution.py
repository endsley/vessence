from __future__ import annotations

import asyncio
from unittest.mock import patch

from jane_web.jane_v3 import pipeline


def _run(coro):
    return asyncio.run(coro)


def test_v3_respects_resolver_cancel_for_stage2_followup():
    pending = {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "clinic schedules info",
        "status": "awaiting_user",
        "awaiting": "clinic_followup",
        "data": {"awaiting": "clinic_followup"},
        "question": "(awaiting:clinic_followup)",
    }
    resolved = {
        "action": "cancel",
        "pending": pending,
        "pending_turn_id": "turn-1",
    }

    with patch("jane_web.jane_v2.pending_action_resolver.resolve", return_value=resolved):
        state = _run(pipeline._classify_and_maybe_handle("No", session_id="s1"))

    assert state["stage1_ms"] == 0
    assert state["force_stage3"] is False
    assert state["result"] == {"text": "Ok.", "conversation_end": True}
    marker = state.get("resolve_pending_action")
    assert marker is not None
    assert marker["status"] == "cancelled"
    assert marker["resolution"] == "abandoned"


def test_v3_respects_resolver_followup_without_reclassification():
    pending = {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "clinic schedules info",
        "status": "awaiting_user",
        "awaiting": "clinic_followup",
        "data": {"awaiting": "clinic_followup"},
        "question": "(awaiting:clinic_followup)",
    }
    resolved = {
        "action": "followup",
        "handler_class": "clinic schedules info",
        "pending": pending,
        "pending_data": pending["data"],
        "pending_turn_id": "turn-1",
    }

    async def fake_handler(prompt: str, pending=None, context=""):
        assert prompt == "Tuesday"
        assert pending == {
            "awaiting": "clinic_followup",
            "question": "(awaiting:clinic_followup)",
        }
        assert context == "fifo ctx"
        return {"text": "Tuesday details"}

    registry = {
        "clinic schedules info": {
            "handler": fake_handler,
        }
    }

    with patch("jane_web.jane_v2.pending_action_resolver.resolve", return_value=resolved), \
         patch("jane_web.jane_v2.recent_context.render_stage2_context", return_value="fifo ctx"), \
         patch("jane_web.jane_v3.pipeline.class_registry.get_registry", return_value=registry):
        state = _run(pipeline._classify_and_maybe_handle("Tuesday", session_id="s1"))

    assert state["stage1_ms"] == 0
    assert state["force_stage3"] is False
    assert state["result"] == {"text": "Tuesday details"}
    marker = state.get("resolve_pending_action")
    assert marker is not None
    assert marker["status"] == "resolved"
    assert marker["resolution"] == "answered"
