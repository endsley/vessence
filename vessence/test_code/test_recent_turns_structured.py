"""Unit tests for the structured FIFO layer added for job 069.

Verifies:
  - legacy prose rows round-trip via both get_recent() and get_recent_structured()
  - structured rows round-trip with all fields intact
  - expired pending_actions are treated as resolved
  - get_active_state picks the newest unresolved pending from a multi-turn history
  - add_structured populates summary so legacy prose callers still work
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import unittest


class StructuredFifoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="fifo_test_")
        os.environ["VAULT_WEB_DB_PATH"] = os.path.join(cls._tmp, "vw.db")
        # Reset module-level cache / ensure env is read before first connect.
        from vault_web import database as _db  # noqa
        _db.DB_PATH = os.environ["VAULT_WEB_DB_PATH"]
        _db.init_db()

    def setUp(self):
        from vault_web.recent_turns import clear
        self.sid = f"_test_{self._testMethodName}"
        clear(self.sid)

    def test_legacy_prose_roundtrip(self):
        from vault_web.recent_turns import add, get_recent, get_recent_structured
        add(self.sid, "user: hi / jane: hello there")
        self.assertEqual(get_recent(self.sid), ["user: hi / jane: hello there"])
        recs = get_recent_structured(self.sid)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["summary"], "user: hi / jane: hello there")
        self.assertEqual(recs[0].get("schema_version"), 0)  # synthesized legacy

    def test_structured_roundtrip(self):
        from vault_web.recent_turns import add_structured, get_recent_structured, get_recent
        add_structured(self.sid, {
            "user_text": "tell Kathia I love her",
            "assistant_text": "Send 'I love you' to Kathia?",
            "intent": "send message",
            "confidence": "High",
            "entities": {"recipient": "Kathia", "message_body": "I love you"},
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "awaiting_user",
                "data": {"phone_number": "+15551234", "body": "I love you",
                         "display_name": "Kathia"},
            },
            "safety": {"side_effectful": True, "requires_confirmation": True},
        })
        recs = get_recent_structured(self.sid)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["intent"], "send message")
        self.assertEqual(r["confidence"], "High")
        self.assertEqual(r["entities"]["recipient"], "Kathia")
        self.assertEqual(r["pending_action"]["type"], "SEND_MESSAGE_CONFIRMATION")
        self.assertTrue(r["safety"]["side_effectful"])
        # Legacy prose callers still get a readable summary.
        self.assertTrue(get_recent(self.sid))
        self.assertIn("Kathia", get_recent(self.sid)[0])

    def test_active_state_picks_newest_unresolved(self):
        from vault_web.recent_turns import add_structured, get_active_state, add
        # Older turn with resolved pending (shouldn't be returned).
        add_structured(self.sid, {
            "user_text": "tell Bob hi",
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "resolved",
                "resolution": "confirmed",
            },
        })
        # Intervening plain-prose turn.
        add(self.sid, "user: weather? / jane: 51 and clear.")
        # Newer turn with an active pending.
        add_structured(self.sid, {
            "user_text": "tell Kathia hey",
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "awaiting_user",
                "data": {"display_name": "Kathia", "body": "hey", "phone_number": "+1"},
            },
        })
        state = get_active_state(self.sid)
        self.assertIsNotNone(state["pending_action"])
        self.assertEqual(state["pending_action"]["data"]["display_name"], "Kathia")
        self.assertEqual(state["last_intent"], "send message")

    def test_expired_pending_is_ignored(self):
        from vault_web.recent_turns import add_structured, get_active_state
        past = (dt.datetime.utcnow() - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        add_structured(self.sid, {
            "user_text": "tell Alice hi",
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "awaiting_user",
                "expires_at": past,
                "data": {"display_name": "Alice"},
            },
        })
        state = get_active_state(self.sid)
        self.assertIsNone(state["pending_action"])

    def test_no_session_returns_empty(self):
        from vault_web.recent_turns import get_recent_structured, get_active_state
        self.assertEqual(get_recent_structured(""), [])
        s = get_active_state("")
        self.assertIsNone(s["pending_action"])


if __name__ == "__main__":
    unittest.main()
