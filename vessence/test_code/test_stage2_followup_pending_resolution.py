"""Regression tests for Stage 2 follow-up pending-action lifecycle."""
from __future__ import annotations

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, "/home/chieh/ambient/vessence")

from jane_web.jane_v2 import pipeline  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


class Stage2FollowupPendingResolutionTest(unittest.TestCase):
    def test_successful_followup_without_new_pending_marks_old_pending_resolved(self) -> None:
        pending = {
            "type": "STAGE2_FOLLOWUP",
            "handler_class": "todo list",
            "status": "awaiting_user",
            "awaiting": "add_category",
            "data": {"action": "add", "item_text": "buy milk", "awaiting": "add_category"},
            "question": "Which category should I add it to?",
        }
        resolved = {
            "action": "followup",
            "handler_class": "todo list",
            "pending": pending,
            "pending_data": pending["data"],
            "pending_turn_id": "turn-1",
        }
        handler_result = {
            "text": "Done. Added buy milk.",
            "structured": {
                "intent": "todo list",
                "entities": {"action": "add", "category": "Do it Immediately"},
            },
        }

        with patch.object(pipeline.pending_action_resolver, "resolve", return_value=resolved), \
             patch.object(pipeline.recent_context, "render_stage2_context", return_value=""), \
             patch.object(pipeline.stage2_dispatcher, "dispatch", new=AsyncMock(return_value=handler_result)):
            state = _run(pipeline._classify_and_try_stage2("urgent stuff", session_id="s1"))

        marker = state.get("resolve_pending_action")
        self.assertIsNotNone(marker)
        self.assertEqual(marker["type"], "STAGE2_FOLLOWUP")
        self.assertEqual(marker["handler_class"], "todo list")
        self.assertEqual(marker["status"], "resolved")
        self.assertEqual(marker["resolution"], "answered")
        self.assertEqual(marker["awaiting"], "add_category")

    def test_successful_followup_with_new_pending_keeps_new_pending_authoritative(self) -> None:
        pending = {
            "type": "STAGE2_FOLLOWUP",
            "handler_class": "todo list",
            "status": "awaiting_user",
            "awaiting": "add_category_then_item",
            "data": {"action": "add", "awaiting": "add_category_then_item"},
            "question": "Which category should I add it to?",
        }
        next_pending = {
            "type": "STAGE2_FOLLOWUP",
            "handler_class": "todo list",
            "status": "awaiting_user",
            "awaiting": "add_item_for_category",
            "data": {
                "action": "add",
                "category": "Do it Immediately",
                "awaiting": "add_item_for_category",
            },
            "question": "What item should I add to your urgent list?",
        }
        resolved = {
            "action": "followup",
            "handler_class": "todo list",
            "pending": pending,
            "pending_data": pending["data"],
            "pending_turn_id": "turn-1",
        }
        handler_result = {
            "text": "What item should I add to your urgent list?",
            "structured": {
                "intent": "todo list",
                "pending_action": next_pending,
            },
        }

        with patch.object(pipeline.pending_action_resolver, "resolve", return_value=resolved), \
             patch.object(pipeline.recent_context, "render_stage2_context", return_value=""), \
             patch.object(pipeline.stage2_dispatcher, "dispatch", new=AsyncMock(return_value=handler_result)):
            state = _run(pipeline._classify_and_try_stage2("urgent stuff", session_id="s1"))

        self.assertNotIn("resolve_pending_action", state)
        self.assertEqual(
            state["result"]["structured"]["pending_action"]["awaiting"],
            "add_item_for_category",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
