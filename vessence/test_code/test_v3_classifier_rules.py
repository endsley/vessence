"""Unit tests for v3 classifier deterministic rules.

Tests the `_is_delete_intent` helper. (The clinic fast path was removed
2026-04-21 — clinic misclassifications are now addressed by adding
exemplars to intent_classifier/v2/classes/clinic_schedules_info.py
instead, per the pipeline architecture guideline.)

These rules run independently of Ollama/ChromaDB so they're safe to run
in a plain pytest invocation.
"""

from __future__ import annotations

import pytest

from intent_classifier.v3.classifier import _is_delete_intent


# ── _is_delete_intent ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("prompt", [
    "can you delete it for me",   # Issue 15 (verbatim)
    "delete it",
    "delete that",
    "delete them",
    "please delete that",
    "could you delete those",
    "delete the message",
    "Delete It.",
])
def test_is_delete_intent_matches(prompt):
    assert _is_delete_intent(prompt), f"expected delete intent for {prompt!r}"


@pytest.mark.parametrize("prompt", [
    "send it",
    "read it",
    "that's delete",               # delete not at start
    "I want to delete everything eventually",   # not a terse command
    "",
])
def test_is_delete_intent_rejects_non_delete(prompt):
    assert not _is_delete_intent(prompt), (
        f"unexpected delete intent for {prompt!r}"
    )
