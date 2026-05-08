"""Tests for the structured short-term memory extractor (Job #86).

Covers:
- turn-kind classifier on representative inputs
- per-kind extraction (with mocked LLM) preserves the right fields
- skip gate rejects low-value turns
- flattening produces the expected labeled-bullet shape + metadata
- top-level ``build_short_term_note`` end-to-end behavior
- realistic case studies: code edit, calendar, messaging, todo, low-value chatter
"""
from __future__ import annotations

import json

from memory.v1.short_term_extractor import (
    EXTRACT_KEYS,
    build_short_term_note,
    classify_turn_kind,
    extract_structured,
    flatten_to_metadata,
    flatten_to_note,
    should_skip,
    _empty_extracted,
    _parse_json_blob,
)


# ---------------------------------------------------------------------------
# classifier
# ---------------------------------------------------------------------------

def test_classify_code_edit():
    assert classify_turn_kind(
        "I edited /home/chieh/code/foo.py to refactor the loop."
    ) == "code"


def test_classify_debugging_when_error_present():
    assert classify_turn_kind(
        "Got a Traceback: AttributeError in attempts.py — root cause is the missing field."
    ) == "debugging"


def test_classify_calendar_meeting():
    assert classify_turn_kind(
        "Schedule a meeting with Sarah next Thursday at 3pm."
    ) == "calendar"


def test_classify_messages_text():
    assert classify_turn_kind(
        "Please text my mom that I'll be late tonight."
    ) == "messages"


def test_classify_todo_grocery():
    assert classify_turn_kind(
        "Add eggs and milk to my grocery list please."
    ) == "todo"


def test_classify_general_smalltalk():
    assert classify_turn_kind("Hi, how are you doing today?") == "general"


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------

def test_parse_json_strips_fenced_block():
    blob = "```json\n" + json.dumps({k: [] for k in EXTRACT_KEYS}) + "\n```"
    out = _parse_json_blob(blob)
    assert out is not None
    for k in EXTRACT_KEYS:
        assert out[k] == []


def test_parse_json_finds_object_in_messy_response():
    blob = (
        "Sure, here it is:\n"
        '{"facts": ["fact1"], "decisions": [], "open_loops": [], '
        '"artifacts": ["foo.py"], "people": [], "time_refs": []}'
    )
    out = _parse_json_blob(blob)
    assert out is not None
    assert out["facts"] == ["fact1"]
    assert out["artifacts"] == ["foo.py"]


def test_parse_json_returns_none_on_garbage():
    assert _parse_json_blob("complete nonsense, no JSON anywhere") is None


def test_parse_json_tolerates_string_for_list_field():
    """If the model returns a single string instead of a list, coerce it."""
    blob = '{"facts": "single fact", "decisions": [], "open_loops": [], "artifacts": [], "people": [], "time_refs": []}'
    out = _parse_json_blob(blob)
    assert out is not None
    assert out["facts"] == ["single fact"]


# ---------------------------------------------------------------------------
# skip gate
# ---------------------------------------------------------------------------

def test_skip_when_completely_empty():
    assert should_skip(_empty_extracted()) is True


def test_skip_when_only_facts_present():
    """Pure trivia with no decisions / loops / artifacts is low-value."""
    e = _empty_extracted()
    e["facts"] = ["the sky is blue"]
    assert should_skip(e) is True


def test_skip_when_only_people():
    e = _empty_extracted()
    e["people"] = ["Sarah"]
    assert should_skip(e) is True


def test_keep_when_decision_present():
    e = _empty_extracted()
    e["decisions"] = ["fixed the bug"]
    assert should_skip(e) is False


def test_keep_when_open_loop_present():
    e = _empty_extracted()
    e["open_loops"] = ["run smoke test"]
    assert should_skip(e) is False


def test_keep_when_artifact_present():
    """Even without a decision, a real artifact reference is worth keeping."""
    e = _empty_extracted()
    e["artifacts"] = ["/home/chieh/foo.py"]
    assert should_skip(e) is False


# ---------------------------------------------------------------------------
# flatten
# ---------------------------------------------------------------------------

def test_flatten_to_note_skips_empty_categories():
    e = _empty_extracted()
    e["decisions"] = ["fix1", "fix2"]
    e["open_loops"] = ["next thing"]
    note = flatten_to_note(e)
    assert "Decisions: fix1; fix2" in note
    assert "Open loops: next thing" in note
    assert "Facts:" not in note      # empty category absent


def test_flatten_to_note_orders_decisions_first():
    e = _empty_extracted()
    e["facts"] = ["f"]
    e["decisions"] = ["d"]
    note = flatten_to_note(e)
    assert note.index("Decisions:") < note.index("Facts:")


def test_flatten_to_metadata_serializes_lists_to_strings():
    e = _empty_extracted()
    e["artifacts"] = ["/a.py", "/b.py"]
    e["people"] = ["Sarah"]
    e["open_loops"] = ["x"]
    meta = flatten_to_metadata("code", e)
    assert meta["turn_kind"] == "code"
    assert meta["has_open_loop"] is True
    assert meta["artifact_paths"] == "/a.py | /b.py"
    assert meta["person_names"] == "Sarah"
    assert meta["n_open_loops"] == 1


# ---------------------------------------------------------------------------
# extract_structured (with mocked LLM)
# ---------------------------------------------------------------------------

def _mock_llm(payload: dict):
    """Return a function that ignores the prompt and returns the payload."""
    def _llm(prompt, **kw):
        return json.dumps(payload)
    return _llm


def test_extract_structured_returns_empty_on_llm_failure():
    def boom(prompt, **kw):
        raise RuntimeError("LLM down")
    out = extract_structured("code", "anything", llm_call=boom)
    for k in EXTRACT_KEYS:
        assert out[k] == []


def test_extract_structured_returns_empty_on_garbage_response():
    def garbage(prompt, **kw):
        return "no JSON here at all"
    out = extract_structured("code", "x", llm_call=garbage)
    assert all(out[k] == [] for k in EXTRACT_KEYS)


def test_extract_structured_passes_through_clean_dict():
    payload = {
        "facts": ["f"], "decisions": ["d"], "open_loops": [],
        "artifacts": ["foo.py"], "people": [], "time_refs": [],
    }
    out = extract_structured("code", "x", llm_call=_mock_llm(payload))
    assert out["facts"] == ["f"]
    assert out["artifacts"] == ["foo.py"]


# ---------------------------------------------------------------------------
# build_short_term_note (top-level)
# ---------------------------------------------------------------------------

def test_build_skips_when_both_messages_empty():
    note, _search, meta, skip = build_short_term_note("", "", llm_call=_mock_llm({k: [] for k in EXTRACT_KEYS}))
    assert skip is True
    assert note == ""


def test_build_code_edit_preserves_files_and_symbols():
    """Realistic code-edit turn — extractor should preserve file paths and
    function names in the artifacts field.
    """
    payload = {
        "facts": ["off-by-one in selection range"],
        "decisions": ["bumped upper bound from N to N+1 in _select_pool"],
        "open_loops": ["run smoke test against Cloud SQL"],
        "artifacts": ["app/services/attempts.py", "_select_pool"],
        "people": [],
        "time_refs": [],
    }
    note, _search, meta, skip = build_short_term_note(
        "fix the off-by-one in attempts.py",
        "Done — bumped upper bound in app/services/attempts.py:_select_pool. Need to smoke test still.",
        llm_call=_mock_llm(payload),
    )
    assert skip is False
    assert "app/services/attempts.py" in note
    assert "_select_pool" in note
    assert "smoke test" in note.lower()
    assert meta["turn_kind"] == "code"
    assert meta["has_open_loop"] is True
    assert "attempts.py" in meta["artifact_paths"]


def test_build_calendar_preserves_names_and_dates():
    payload = {
        "facts": ["doctor appointment exists in calendar"],
        "decisions": [],
        "open_loops": ["confirm with dentist for second visit"],
        "artifacts": [],
        "people": ["Dr. Smith"],
        "time_refs": ["April 30 2026 at 2pm"],
    }
    note, _search, meta, skip = build_short_term_note(
        "When is my doctor appointment?",
        "[CALENDAR DATA] Dr. Smith on Apr 30 2026 at 2pm. Dentist needs confirmation for second visit.",
        llm_call=_mock_llm(payload),
    )
    assert skip is False
    assert "Dr. Smith" in note
    assert "April 30 2026" in note
    assert meta["turn_kind"] == "calendar"
    assert "Dr. Smith" in meta["person_names"]
    assert "April 30 2026" in meta["time_refs"]


def test_build_messaging_preserves_recipient_and_action():
    payload = {
        "facts": [],
        "decisions": ["sent text to Mom: I will be late"],
        "open_loops": [],
        "artifacts": ["contacts.sms_send_direct"],
        "people": ["Mom"],
        "time_refs": [],
    }
    note, _search, meta, skip = build_short_term_note(
        "Tell mom I'll be late",
        "msg sent",
        llm_call=_mock_llm(payload),
    )
    assert skip is False
    assert "Mom" in note
    assert meta["turn_kind"] == "messages"
    assert meta["has_decision"] is True


def test_build_todo_preserves_items():
    payload = {
        "facts": ["grocery list now contains: milk, eggs, bread"],
        "decisions": ["added milk and eggs to grocery list"],
        "open_loops": [],
        "artifacts": ["grocery list"],
        "people": [],
        "time_refs": [],
    }
    note, _search, meta, skip = build_short_term_note(
        "Add milk and eggs to my grocery list",
        "Added — list now has: milk, eggs, bread.",
        llm_call=_mock_llm(payload),
    )
    assert skip is False
    assert "milk" in note.lower()
    assert "eggs" in note.lower()
    assert meta["turn_kind"] == "todo"


def test_build_skips_low_value_chatter():
    """A pure-greeting turn with no decisions / artifacts / open loops
    should be dropped before reaching Chroma.
    """
    payload = {k: [] for k in EXTRACT_KEYS}
    note, _search, meta, skip = build_short_term_note(
        "Hi Jane!",
        "Hello! How can I help?",
        llm_call=_mock_llm(payload),
    )
    assert skip is True
    assert note == ""
    assert meta.get("skipped") is True


def test_build_skips_when_only_facts_present():
    """Even a non-empty extraction is skipped if it has no actionable bits.

    This is the bar for being worth taking up a Chroma slot.
    """
    payload = _empty_extracted()
    payload["facts"] = ["the user mentioned they are tired"]
    payload["people"] = ["the user"]
    note, _search, meta, skip = build_short_term_note(
        "I'm tired",
        "Sorry to hear that — get some rest.",
        llm_call=_mock_llm(payload),
    )
    assert skip is True


def test_build_uses_strip_metadata_cleaner():
    """The cleaner argument should be invoked on both messages."""
    captured: list[str] = []

    def fake_cleaner(s: str) -> str:
        captured.append(s)
        return s.replace("[META]", "").strip()

    payload = _empty_extracted()
    payload["decisions"] = ["did the thing"]
    note, _search, meta, skip = build_short_term_note(
        "user msg [META]",
        "asst msg [META]",
        cleaner=fake_cleaner,
        llm_call=_mock_llm(payload),
    )
    assert "[META]" not in note
    assert any("[META]" in c for c in captured), "cleaner must be called on raw input"
    assert skip is False
