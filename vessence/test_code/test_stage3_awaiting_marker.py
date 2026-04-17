"""Unit tests for Stage 3 [[AWAITING:<topic>]] marker pipeline.

Covers:
- Marker extraction (strip + topic capture)
- pending_action_resolver routing STAGE3_FOLLOWUP → stage3_followup action
- System prompt includes the AWAITING instruction
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "/home/chieh/ambient/vessence")

from jane_web.jane_v2 import pipeline  # noqa: E402
from jane_web.jane_v2 import pending_action_resolver  # noqa: E402


class ExtractAwaitingMarkerTest(unittest.TestCase):
    def test_no_marker_returns_unchanged(self) -> None:
        text = "Here is a normal reply with no marker."
        cleaned, topic = pipeline._extract_awaiting_marker(text)
        self.assertEqual(cleaned, text)
        self.assertIsNone(topic)

    def test_trailing_marker_extracted(self) -> None:
        text = "Which pasta recipe did you mean? [[AWAITING:which_pasta_recipe]]"
        cleaned, topic = pipeline._extract_awaiting_marker(text)
        self.assertEqual(cleaned, "Which pasta recipe did you mean?")
        self.assertEqual(topic, "which_pasta_recipe")

    def test_marker_with_spaces_gets_normalized(self) -> None:
        text = "Ready? [[AWAITING:confirm send email]]"
        cleaned, topic = pipeline._extract_awaiting_marker(text)
        self.assertEqual(cleaned, "Ready?")
        self.assertEqual(topic, "confirm_send_email")

    def test_topic_length_capped(self) -> None:
        long_topic = "a" * 100
        text = f"hello [[AWAITING:{long_topic}]]"
        cleaned, topic = pipeline._extract_awaiting_marker(text)
        self.assertIsNotNone(topic)
        self.assertLessEqual(len(topic), 60)

    def test_only_trailing_marker_counts(self) -> None:
        # Marker at END activates; mid-text marker does not.
        text_tail = (
            "Earlier I said [[AWAITING:ignore_me]] but now I really mean "
            "[[AWAITING:real_topic]]"
        )
        cleaned, topic = pipeline._extract_awaiting_marker(text_tail)
        self.assertEqual(topic, "real_topic")
        self.assertIn("[[AWAITING:ignore_me]]", cleaned)
        self.assertNotIn("[[AWAITING:real_topic]]", cleaned)

    def test_mid_text_marker_ignored(self) -> None:
        text = "I said [[AWAITING:mid_text]] and then kept talking normally."
        cleaned, topic = pipeline._extract_awaiting_marker(text)
        self.assertIsNone(topic)
        self.assertEqual(cleaned, text)

    def test_whitespace_trimmed(self) -> None:
        text = "Hello [[AWAITING: topic_with_pad ]]"
        cleaned, topic = pipeline._extract_awaiting_marker(text)
        self.assertEqual(topic, "topic_with_pad")

    def test_empty_string(self) -> None:
        cleaned, topic = pipeline._extract_awaiting_marker("")
        self.assertEqual(cleaned, "")
        self.assertIsNone(topic)

    def test_malformed_marker_ignored(self) -> None:
        # Missing colon — parser is strict, should leave alone
        text = "Hello [[AWAITING no_colon]]"
        cleaned, topic = pipeline._extract_awaiting_marker(text)
        self.assertEqual(cleaned, text)
        self.assertIsNone(topic)


class ResolverStage3FollowupTest(unittest.TestCase):
    def _fake_state_with(self, pending: dict) -> dict:
        return {"pending_action": pending, "pending_turn_id": "turn-42"}

    def test_routes_stage3_followup(self) -> None:
        pending = {
            "type": "STAGE3_FOLLOWUP",
            "handler_class": "stage3",
            "status": "awaiting_user",
            "awaiting": "which_pasta_recipe",
            "expires_at": "2099-01-01T00:00:00Z",
        }
        with patch("vault_web.recent_turns.get_active_state",
                   return_value=self._fake_state_with(pending)):
            out = pending_action_resolver.resolve("sess-1", "the red one")
        self.assertIsNotNone(out)
        self.assertEqual(out["action"], "stage3_followup")
        self.assertEqual(out["pending"]["awaiting"], "which_pasta_recipe")
        self.assertEqual(out["pending_turn_id"], "turn-42")

    def test_cancel_still_wins_over_stage3(self) -> None:
        # Universal cancel should work from any pending type, including
        # STAGE3_FOLLOWUP.
        pending = {"type": "STAGE3_FOLLOWUP", "awaiting": "x"}
        with patch("vault_web.recent_turns.get_active_state",
                   return_value=self._fake_state_with(pending)):
            out = pending_action_resolver.resolve("sess-1", "never mind")
        self.assertIsNotNone(out)
        self.assertEqual(out["action"], "cancel")

    def test_no_pending_returns_none(self) -> None:
        with patch("vault_web.recent_turns.get_active_state",
                   return_value={"pending_action": None}):
            out = pending_action_resolver.resolve("sess-1", "hello")
        self.assertIsNone(out)

    def test_non_cancel_reply_with_stage3_pending_returns_followup(self) -> None:
        # Any non-cancel reply routes to stage3_followup (that's the point).
        pending = {"type": "STAGE3_FOLLOWUP", "awaiting": "pick_color"}
        with patch("vault_web.recent_turns.get_active_state",
                   return_value=self._fake_state_with(pending)):
            out = pending_action_resolver.resolve("sess-1", "purple I think")
        self.assertEqual(out["action"], "stage3_followup")

    def test_soft_no_survives_as_answer_to_stage3(self) -> None:
        # Plain "no" must reach Opus as an answer, not cancel the flow.
        pending = {"type": "STAGE3_FOLLOWUP", "awaiting": "confirm_send"}
        with patch("vault_web.recent_turns.get_active_state",
                   return_value=self._fake_state_with(pending)):
            out = pending_action_resolver.resolve("sess-1", "no")
        self.assertEqual(out["action"], "stage3_followup")

    def test_nope_also_survives(self) -> None:
        pending = {"type": "STAGE3_FOLLOWUP", "awaiting": "confirm_send"}
        with patch("vault_web.recent_turns.get_active_state",
                   return_value=self._fake_state_with(pending)):
            out = pending_action_resolver.resolve("sess-1", "nope")
        self.assertEqual(out["action"], "stage3_followup")

    def test_strong_cancel_still_cancels_stage3(self) -> None:
        # "never mind" / "cancel" should still abort the flow.
        pending = {"type": "STAGE3_FOLLOWUP", "awaiting": "confirm_send"}
        for phrase in ("never mind", "cancel", "forget it", "abort"):
            with patch("vault_web.recent_turns.get_active_state",
                       return_value=self._fake_state_with(pending)):
                out = pending_action_resolver.resolve("sess-1", phrase)
            self.assertEqual(out["action"], "cancel",
                             f"phrase={phrase!r} should cancel")

    def test_sms_confirm_still_cancels_on_no(self) -> None:
        # Regression: legacy SMS confirmation flow must still cancel on "no".
        pending = {"type": "SEND_MESSAGE_CONFIRMATION"}
        with patch("vault_web.recent_turns.get_active_state",
                   return_value=self._fake_state_with(pending)):
            out = pending_action_resolver.resolve("sess-1", "no")
        self.assertEqual(out["action"], "cancel")


class SystemPromptInstructionTest(unittest.TestCase):
    def test_awaiting_instruction_mentions_marker_format(self) -> None:
        from context_builder.v1 import context_builder
        text = context_builder.AWAITING_MARKER_INSTRUCTION
        self.assertIn("[[AWAITING:", text)
        self.assertIn("stripped", text.lower())

    def test_instruction_appended_to_system_sections(self) -> None:
        # Smoke check: instruction is the second item so it's close to
        # the base prompt but doesn't clobber it.
        import inspect
        from context_builder.v1 import context_builder
        src = inspect.getsource(context_builder._build_system_sections)
        self.assertIn("AWAITING_MARKER_INSTRUCTION", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
