"""Unit tests for the 2026-04-18 self-improvement fixes.

Covers:
  - Issue 12: Stage 1 subject-change stripping + "weathers" → "weather" fixup
  - Issue 13: stage3_escalate forwards skip_router=True to stream_message
  - Issue 14: pending_action_resolver detects topic-pivot phrases for
    STAGE3_FOLLOWUP / STAGE2_FOLLOWUP and get_active_state honors the
    cancelled type on subsequent turns
"""

from __future__ import annotations

import inspect
import os
import tempfile
import unittest


class Stage1StripTests(unittest.TestCase):
    """Issue 12 — subject-change stripping."""

    def test_strips_change_the_subject_to_weather(self):
        from jane_web.jane_v2.stage1_classifier import _strip_system_markers
        cleaned = _strip_system_markers("I would like to change the subject to Weathers")
        self.assertEqual(cleaned.lower(), "weather")

    def test_strips_plain_change_the_subject(self):
        from jane_web.jane_v2.stage1_classifier import _strip_system_markers
        cleaned = _strip_system_markers("change the subject to weather")
        self.assertEqual(cleaned.lower(), "weather")

    def test_strips_lets_talk_about(self):
        from jane_web.jane_v2.stage1_classifier import _strip_system_markers
        cleaned = _strip_system_markers("Let's talk about the weather")
        self.assertEqual(cleaned.lower(), "the weather")

    def test_strips_switching_the_topic_to(self):
        from jane_web.jane_v2.stage1_classifier import _strip_system_markers
        cleaned = _strip_system_markers("Switching the topic to weather")
        self.assertEqual(cleaned.lower(), "weather")

    def test_plural_weathers_singular(self):
        from jane_web.jane_v2.stage1_classifier import _strip_system_markers
        cleaned = _strip_system_markers("how's the weathers today")
        self.assertIn("weather", cleaned.lower())
        self.assertNotIn("weathers", cleaned.lower())

    def test_unaffected_non_pivot_prompt(self):
        from jane_web.jane_v2.stage1_classifier import _strip_system_markers
        cleaned = _strip_system_markers("what is the weather today")
        self.assertEqual(cleaned, "what is the weather today")

    def test_preserves_sms_tool_result_stripping(self):
        """Existing behavior still works for TOOL_RESULT markers."""
        from jane_web.jane_v2.stage1_classifier import _strip_system_markers
        cleaned = _strip_system_markers(
            "[TOOL_RESULT:{\"ok\":true}] did the text send?"
        )
        self.assertEqual(cleaned, "did the text send?")


class Stage3EscalateSkipRouterTests(unittest.TestCase):
    """Issue 13 — stage3_escalate must forward skip_router=True.

    We can't exercise the full stream without an LLM process, so assert
    the call-site invariant statically by inspecting the source.
    """

    def test_stage3_escalate_source_passes_skip_router(self):
        from jane_web.jane_v2 import stage3_escalate
        src = inspect.getsource(stage3_escalate.escalate_stream)
        self.assertIn(
            "skip_router=True", src,
            "stage3_escalate.escalate_stream must forward skip_router=True "
            "to prevent jane_proxy from reclassifying an already-classified turn "
            "(see Issue 13 — READ_MESSAGES dispatched inside an unrelated Stage 3).",
        )


class ResolverPivotTests(unittest.TestCase):
    """Issue 14 — pivot detection + cancelled-type propagation."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="pivot_test_")
        os.environ["VAULT_WEB_DB_PATH"] = os.path.join(cls._tmp, "vw.db")
        from vault_web import database as _db
        _db.DB_PATH = os.environ["VAULT_WEB_DB_PATH"]
        _db.init_db()

    def setUp(self):
        from vault_web.recent_turns import clear
        self.sid = f"_pivot_{self._testMethodName}"
        clear(self.sid)

    def _seed_stage3_followup(self, awaiting="misclassified_examples"):
        from vault_web.recent_turns import add_structured
        add_structured(self.sid, {
            "user_text": "tell me about misclassifications",
            "assistant_text": "Can you give me some examples?",
            "intent": "others",
            "pending_action": {
                "type": "STAGE3_FOLLOWUP",
                "handler_class": "stage3",
                "status": "awaiting_user",
                "awaiting": awaiting,
            },
        })

    def _seed_stage2_followup_todo(self):
        from vault_web.recent_turns import add_structured
        add_structured(self.sid, {
            "user_text": "add something to my todo list",
            "assistant_text": "Which category?",
            "intent": "todo list",
            "pending_action": {
                "type": "STAGE2_FOLLOWUP",
                "handler_class": "todo list",
                "status": "awaiting_user",
                "awaiting": "category",
            },
        })

    # ── Pivot detection ────────────────────────────────────────────────
    def test_pivot_focus_on_different_issue(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_stage3_followup()
        r = resolve(self.sid, "no no I actually think we should focus on the different issue")
        self.assertIsNotNone(r)
        self.assertEqual(r["action"], "pivot")

    def test_pivot_change_the_subject(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_stage3_followup()
        r = resolve(self.sid, "change the subject to weather")
        self.assertIsNotNone(r)
        self.assertEqual(r["action"], "pivot")

    def test_pivot_not_what_i_asked_on_stage2_followup(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_stage2_followup_todo()
        r = resolve(self.sid, "that is not what I asked for")
        self.assertIsNotNone(r)
        self.assertEqual(r["action"], "pivot")

    def test_plain_answer_still_routes_followup(self):
        """An actual category answer must NOT trip the pivot detector."""
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_stage2_followup_todo()
        r = resolve(self.sid, "home")
        self.assertIsNotNone(r)
        self.assertEqual(r["action"], "followup")

    def test_confirm_pending_unaffected_by_pivot(self):
        """Pivot detection only applies to FOLLOWUP types, not SMS confirm."""
        from vault_web.recent_turns import add_structured
        from jane_web.jane_v2.pending_action_resolver import resolve
        add_structured(self.sid, {
            "user_text": "tell her I love her",
            "assistant_text": "Send 'I love you' to Kathia?",
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "awaiting_user",
                "data": {},
            },
        })
        # Even a phrase that would trigger pivot stays in confirm-world.
        r = resolve(self.sid, "yes")
        self.assertIsNotNone(r)
        self.assertEqual(r["action"], "confirm")

    # ── Cancelled-type propagation ─────────────────────────────────────
    def test_get_active_state_suppresses_older_type_when_newer_cancelled(self):
        """A newer cancelled STAGE3_FOLLOWUP record must suppress an older
        active STAGE3_FOLLOWUP so the resolver doesn't keep re-entering
        it after a pivot."""
        from vault_web.recent_turns import add_structured, get_active_state
        # Older turn: stage 3 asked a question (awaiting_user).
        add_structured(self.sid, {
            "user_text": "tell me about X",
            "assistant_text": "What examples do you have?",
            "intent": "others",
            "pending_action": {
                "type": "STAGE3_FOLLOWUP",
                "handler_class": "stage3",
                "status": "awaiting_user",
                "awaiting": "examples",
            },
        })
        # Sanity: active pending exists.
        state = get_active_state(self.sid)
        self.assertIsNotNone(state["pending_action"])

        # Newer turn: user pivoted, pipeline wrote a cancelled marker.
        add_structured(self.sid, {
            "user_text": "let's talk about weather",
            "assistant_text": "It's 72 and sunny.",
            "intent": "weather",
            "pending_action": {
                "type": "STAGE3_FOLLOWUP",
                "handler_class": "stage3",
                "status": "cancelled",
            },
        })
        state2 = get_active_state(self.sid)
        self.assertIsNone(
            state2["pending_action"],
            "Older active STAGE3_FOLLOWUP should be suppressed by the "
            "newer cancelled marker of the same type.",
        )


if __name__ == "__main__":
    unittest.main()
