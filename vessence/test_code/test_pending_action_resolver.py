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


if __name__ == "__main__":
    unittest.main()
