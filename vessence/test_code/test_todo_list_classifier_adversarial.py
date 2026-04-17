"""Adversarial classifier test for the new `todo list` class.

We care about two failure modes:

  - FALSE POSITIVE — a prompt that ISN'T about the TODO list gets
    routed to the `todo list` handler, hijacking weather, shopping
    list, SMS, timer, etc.

  - FALSE NEGATIVE — a prompt that IS about the TODO list gets
    routed elsewhere (timer, others, greeting), so the fast-path
    fails and user gets a slow Stage 3 hallucination.

The test fires a large batch of adversarial prompts at the live
Stage 1 classifier (embedding + Gemma) and compares the returned
class label against the expected category. Budget: ~1s per prompt.

Expectations kept conservative on the classifier:
  - HIGH accuracy required on the positive set.
  - On the negative set, we accept anything EXCEPT `todo list`.
  - For the Ambient-project set, label must NOT be `todo list`
    (Ambient explicitly escalates to Stage 3).
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest

sys.path.insert(0, "/home/chieh/ambient/vessence")

# Classifier is the async Stage 1 entry point.
from jane_web.jane_v2 import stage1_classifier  # noqa: E402


# ── Adversarial fixtures ─────────────────────────────────────────────────────

# Things that ARE about the TODO list. Must classify as `todo list`.
# Every prompt here includes an explicit todo/to-do/task/errand anchor —
# bare "my X list" is inherently ambiguous with wish-list, reading-list,
# etc., so we require the todo keyword to qualify for the fast path.
POSITIVE_TODO = [
    "what's on my todo list",
    "what's on my to do list",
    "what's on my to-do list",
    "read me my todo list",
    "read me my to-do list",
    "read my task list",
    "read my tasks",
    "show me my tasks",
    "show me my to-do list",
    "what's left on my todo",
    "what's left on my to-do list",
    "what's pending on my todo",
    "catch me up on my todo",
    "catch me up on my tasks",
    "go through my todo list",
    "run through my to-do",
    "what tasks are pending on my todo",
    "what errands do I have on my todo",
    "what's urgent on my todo list",
    "what's on my todo for the clinic",
    "what tasks do I have for the clinic",
    "what tasks do I have for my students",
    "what's on my todo for home",
]

# Things that look TODO-ish but are NOT. Must NOT classify as `todo list`.
NEGATIVE_LOOKALIKES = [
    # Shopping list is a separate class
    "what's on my shopping list",
    "add milk to the shopping list",
    "what do I need from the store",
    # Timer / reminder
    "remind me to buy eggs in 30 minutes",
    "set a timer for my laundry",
    # SMS / contacts
    "text Kathia I'll be home late",
    "tell mom I'm okay",
    # Weather / time / greetings
    "what's the weather like tomorrow",
    "good morning Jane",
    "hey Jane how's it going",
    "what time is it",
    # Casual chat / creative
    "write me a poem about the ocean",
    "tell me a joke",
    "what's 2 plus 2",
    # Self-improvement (different class)
    "what did you fix last night",
    "any improvements this week",
]

# Prompts that mention Ambient project goals — MUST escalate to Stage 3,
# NOT get eaten by the todo_list class.
AMBIENT_ESCALATIONS = [
    "what are my ambient project goals",
    "tell me about the ambient project",
    "what's the status of the ambient project",
    "what's next for the ambient project",
    "how's the ambient project going",
    "remind me of the ambient project plan",
    "what am I working on for ambient",
    "what's pending on ambient",
]


def _classify(prompt: str) -> tuple[str, str]:
    """Sync wrapper around the async classifier. Returns (cls, conf)."""
    return asyncio.run(stage1_classifier.classify(prompt))


class _LiveClassifierRequired(unittest.TestCase):
    """Base — skip if embedding DB or Gemma isn't reachable."""

    @classmethod
    def setUpClass(cls) -> None:
        # The classifier depends on ChromaDB + a local LLM. If either is
        # unreachable, don't fail CI — just skip.
        try:
            probe_cls, probe_conf = _classify("hello there")
            cls._probe_ok = True
            cls._probe_class = probe_cls
        except Exception as e:
            cls._probe_ok = False
            cls._probe_err = str(e)

    def setUp(self) -> None:
        if not getattr(self, "_probe_ok", False):
            self.skipTest(
                f"Stage 1 classifier not reachable: "
                f"{getattr(self, '_probe_err', 'unknown')}"
            )


class PositiveAccuracyTest(_LiveClassifierRequired):
    """Every prompt in POSITIVE_TODO should classify as `todo list`.

    Budget: we tolerate ONE classifier miss (~95% recall) to leave room
    for Gemma jitter on borderline phrasings; raise to strict 100% once
    the class has been tuned over a few days.
    """

    def test_positive_recall(self) -> None:
        misses = []
        for p in POSITIVE_TODO:
            cls, conf = _classify(p)
            if cls != "todo list":
                misses.append((p, cls, conf))
        # Record miss details for audit before asserting.
        if misses:
            for p, cls, conf in misses:
                print(f"[FALSE NEGATIVE] {p!r} → {cls}:{conf}")
        self.assertLessEqual(
            len(misses), 1,
            f"Too many false negatives ({len(misses)}/{len(POSITIVE_TODO)})",
        )


class NegativeAccuracyTest(_LiveClassifierRequired):
    """Nothing in NEGATIVE_LOOKALIKES should classify as `todo list`.

    Budget: zero tolerance for false positives — hijacking weather/SMS
    with a TODO fast-path would break user flows badly.
    """

    def test_no_false_positives(self) -> None:
        misses = []
        for p in NEGATIVE_LOOKALIKES:
            cls, conf = _classify(p)
            if cls == "todo list":
                misses.append((p, cls, conf))
        if misses:
            for p, cls, conf in misses:
                print(f"[FALSE POSITIVE] {p!r} → {cls}:{conf}")
        self.assertEqual(
            len(misses), 0,
            f"{len(misses)} false positive(s) in negative set",
        )


class AmbientEscalationTest(_LiveClassifierRequired):
    """Ambient-project prompts MUST NOT go to the todo_list class.

    Chieh explicitly wants these to escalate to Stage 3 (Opus). Any
    `todo list` hit here is a behavior regression.
    """

    def test_ambient_escalates(self) -> None:
        misses = []
        for p in AMBIENT_ESCALATIONS:
            cls, conf = _classify(p)
            if cls == "todo list":
                misses.append((p, cls, conf))
        if misses:
            for p, cls, conf in misses:
                print(f"[AMBIENT REGRESSION] {p!r} → {cls}:{conf}")
        self.assertEqual(
            len(misses), 0,
            f"{len(misses)} Ambient prompt(s) wrongly routed to todo_list",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
