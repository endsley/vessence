"""Unit tests for jane_web.jane_v2.pending_action_resolver (job 069).

Verifies:
  - no pending → passes through (returns None)
  - confirm phrases deterministically route to confirm
  - cancel phrases route to cancel
  - ambiguous revisions fall through (Stage 3 handles those)
  - pending type other than SEND_MESSAGE_CONFIRMATION falls through
"""

from __future__ import annotations

import os
import tempfile
import unittest


class ResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="resolver_test_")
        os.environ["VAULT_WEB_DB_PATH"] = os.path.join(cls._tmp, "vw.db")
        from vault_web import database as _db
        _db.DB_PATH = os.environ["VAULT_WEB_DB_PATH"]
        _db.init_db()

    def setUp(self):
        from vault_web.recent_turns import clear
        self.sid = f"_res_{self._testMethodName}"
        clear(self.sid)

    def _seed_pending_sms(self):
        from vault_web.recent_turns import add_structured
        add_structured(self.sid, {
            "user_text": "tell Kathia I love her",
            "assistant_text": "Send 'I love you' to Kathia?",
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "awaiting_user",
                "data": {"display_name": "Kathia", "body": "I love you",
                         "phone_number": "+15551234"},
            },
        })

    def test_no_pending_returns_none(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self.assertIsNone(resolve(self.sid, "yes"))

    def test_confirm_variants(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_pending_sms()
        for phrase in ("yes", "Yes!", "yeah", "go ahead", "send it", "ok", "okay."):
            r = resolve(self.sid, phrase)
            self.assertIsNotNone(r, f"{phrase!r} should confirm")
            self.assertEqual(r["action"], "confirm")

    def test_cancel_variants(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_pending_sms()
        for phrase in ("no", "nope", "cancel", "cancel that", "never mind",
                       "stop", "abort"):
            r = resolve(self.sid, phrase)
            self.assertIsNotNone(r, f"{phrase!r} should cancel")
            self.assertEqual(r["action"], "cancel")

    def test_ambiguous_revision_falls_through(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_pending_sms()
        for phrase in ("actually make it nicer", "change it to say hi",
                       "what about tomorrow", "tell him that too",
                       "yes please cancel"):  # ambiguous: not exact match
            self.assertIsNone(resolve(self.sid, phrase),
                              f"{phrase!r} should fall through, not resolve")

    def test_other_pending_type_falls_through(self):
        from vault_web.recent_turns import add_structured
        from jane_web.jane_v2.pending_action_resolver import resolve
        add_structured(self.sid, {
            "user_text": "start a workout",
            "intent": "others",
            "pending_action": {
                "type": "SOME_FUTURE_PENDING_TYPE",
                "status": "awaiting_user",
            },
        })
        self.assertIsNone(resolve(self.sid, "yes"))

    # ── STAGE2_FOLLOWUP tests (multi-turn Stage 2 conversations) ──

    def _seed_timer_followup(self, awaiting="duration", data=None):
        from vault_web.recent_turns import add_structured
        add_structured(self.sid, {
            "user_text": "hey Jane I want to create a timer",
            "assistant_text": "Sure — how long should the timer run?",
            "intent": "timer",
            "pending_action": {
                "type": "STAGE2_FOLLOWUP",
                "handler_class": "timer",
                "status": "awaiting_user",
                "awaiting": awaiting,
                "data": data or {},
            },
        })

    def test_followup_routes_to_handler_class(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_timer_followup("duration")
        r = resolve(self.sid, "5 minutes")
        self.assertIsNotNone(r)
        self.assertEqual(r["action"], "followup")
        self.assertEqual(r["handler_class"], "timer")

    def test_followup_cancel_override(self):
        from jane_web.jane_v2.pending_action_resolver import resolve
        self._seed_timer_followup("label", {"duration_ms": 300000})
        for phrase in ("never mind", "cancel", "forget it"):
            r = resolve(self.sid, phrase)
            self.assertIsNotNone(r, f"{phrase!r} should cancel")
            self.assertEqual(r["action"], "cancel")

    def test_followup_no_handler_class_returns_none(self):
        from vault_web.recent_turns import add_structured
        from jane_web.jane_v2.pending_action_resolver import resolve
        add_structured(self.sid, {
            "user_text": "broken flow",
            "pending_action": {
                "type": "STAGE2_FOLLOWUP",
                "status": "awaiting_user",
                "awaiting": "label",
            },
        })
        self.assertIsNone(resolve(self.sid, "pasta"))


class TimerStateMachineTests(unittest.TestCase):
    """End-to-end timer state machine without the DB/pipeline — purely
    the handler's response to (prompt, pending) pairs."""

    def test_full_conversation_no_duration(self):
        """The pipeline passes pending_action["data"] (not the whole
        pending_action) as the handler's `pending` kwarg. Tests mirror
        that contract so they catch shape-mismatch regressions."""
        from jane_web.jane_v2.classes.timer.handler import handle
        r1 = handle("hey Jane I want to create a timer")
        pa1 = r1["structured"]["pending_action"]
        self.assertEqual(pa1["awaiting"], "duration")

        r2 = handle("5 minutes", pending=pa1["data"])
        pa2 = r2["structured"].get("pending_action")
        self.assertIsNotNone(pa2)
        self.assertEqual(pa2["awaiting"], "label")
        self.assertEqual(pa2["data"]["duration_ms"], 5 * 60 * 1000)

        r3 = handle("pasta is ready", pending=pa2["data"])
        self.assertIsNone(r3["structured"].get("pending_action"),
                          "final turn should NOT emit a new pending")
        self.assertIn("timer.set", r3["text"])
        self.assertIn('"duration_ms":300000', r3["text"])
        self.assertIn('"label":"pasta is ready"', r3["text"])

    def test_duration_given_asks_for_label(self):
        from jane_web.jane_v2.classes.timer.handler import handle
        r = handle("set a 5 minute timer")
        pa = r["structured"].get("pending_action")
        self.assertIsNotNone(pa)
        self.assertEqual(pa["awaiting"], "label")
        r2 = handle("no label", pending=pa["data"])
        self.assertIsNone(r2["structured"].get("pending_action"))
        self.assertIn("timer.set", r2["text"])
        self.assertIn('"label":""', r2["text"])

    def test_regression_no_infinite_loop(self):
        """Reproduces the duration↔label ping-pong bug: pipeline passes
        pending_action.data (flat dict with duration_ms + awaiting), not
        the nested pending_action record. Handler must read the flat
        shape or it loses state on every turn and re-asks forever."""
        from jane_web.jane_v2.classes.timer.handler import handle
        # Simulate exactly what the pipeline hands in: the .data dict.
        r = handle("pasta",
                   pending={"duration_ms": 10000, "awaiting": "label"})
        pa = r["structured"].get("pending_action")
        self.assertIsNone(pa, "label-reply with known duration must fire, not re-ask")
        self.assertIn("timer.set", r["text"])
        self.assertIn('"duration_ms":10000', r["text"])
        self.assertIn('"label":"pasta"', r["text"])

    def test_both_given_fires_immediately(self):
        from jane_web.jane_v2.classes.timer.handler import handle
        r = handle("set a 5 minute pasta timer")
        self.assertIsNone(r["structured"].get("pending_action"))
        self.assertIn("timer.set", r["text"])

    def test_pivot_abandons(self):
        from jane_web.jane_v2.classes.timer.handler import handle
        r = handle("what's the weather",
                   pending={"duration_ms": 300000, "awaiting": "label"})
        self.assertTrue(r.get("abandon_pending"))

    def test_unparseable_duration_reprompts(self):
        from jane_web.jane_v2.classes.timer.handler import handle
        r = handle("huh", pending={"awaiting": "duration"})
        pa = r["structured"].get("pending_action")
        self.assertIsNotNone(pa)
        self.assertEqual(pa["awaiting"], "duration")


if __name__ == "__main__":
    unittest.main()
