"""Unit tests for v3 classifier deterministic rules.

Tests the `_clinic_fast_path` and `_is_delete_intent` helpers added
2026-04-21 in response to transcript review issues 4, 7, 9, 12, 15, 16.

These rules run independently of Ollama/ChromaDB so they're safe to run
in a plain pytest invocation.
"""

from __future__ import annotations

import pytest

from intent_classifier.v3.classifier import (
    _clinic_fast_path,
    _is_delete_intent,
)


# ── _clinic_fast_path ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("prompt", [
    # From transcript evidence — these all previously misrouted:
    "how many patients do I have today",             # Issue 3
    "who's coming in tomorrow",                       # Issue 7
    "can you tell me about the clinic schedule on Wednesday",  # Issue 9
    "what is my clinic schedule look like tomorrow",  # Issue 12
    "is she working on Monday",                       # Issue 6
    "how busy is she on Wednesday",                   # Issue 5
    "any cancellations",                              # Issue 13
    "no I would like to know which patients canceled",  # Issue 16
    # Extra variants we want to support:
    "which patients are coming in",
    "any patients tomorrow",
    "how many patients does she have Tuesday",
    "my clinic schedule",
    "who is coming in today",
])
def test_clinic_fast_path_matches_schedule_queries(prompt):
    hit = _clinic_fast_path(prompt)
    assert hit == ("clinic schedules info", "Very High"), (
        f"expected clinic match for {prompt!r}, got {hit!r}"
    )


@pytest.mark.parametrize("prompt", [
    # Generic calendar queries — read_calendar territory, not clinic:
    "what's on my calendar today",
    "what's my agenda today",
    # Non-schedule queries that mention clinic:
    "are we still going to the clinic",
    # Short ambiguous follow-ups that need FIFO context (fast path must NOT fire):
    "how about tomorrow",
    "more details about the first patient",
    "what does her schedule look like this week",
    # Garbage-in:
    "",
    "   ",
])
def test_clinic_fast_path_ignores_ambiguous_queries(prompt):
    assert _clinic_fast_path(prompt) is None, (
        f"unexpected clinic match for {prompt!r}"
    )


@pytest.mark.parametrize("prompt", [
    # Send-intent phrasings must override the clinic fast path — mentioning
    # clinic words doesn't mean it's a lookup:
    "text my wife the clinic schedule",
    "email bob how many patients I have today",
    "tell Kathia any cancellations",
    "call the clinic about my patients",
])
def test_clinic_fast_path_skips_send_intents(prompt):
    assert _clinic_fast_path(prompt) is None, (
        f"fast path should not hijack send intent: {prompt!r}"
    )


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
