from memory.v1 import short_term_extractor
from memory.v1.turn_kind import TURN_KIND_PATTERNS, classify_turn_kind


def test_short_term_extractor_uses_extracted_turn_kind_classifier() -> None:
    assert short_term_extractor._TURN_KIND_PATTERNS is TURN_KIND_PATTERNS
    assert short_term_extractor.classify_turn_kind is classify_turn_kind


def test_classify_turn_kind_detects_calendar_messages_todo_debugging_and_code() -> None:
    assert classify_turn_kind("Move the calendar appointment to Friday") == "calendar"
    assert classify_turn_kind("Tell Kathia I am running late by SMS") == "messages"
    assert classify_turn_kind("Add milk to my shopping list") == "todo"
    assert classify_turn_kind("The traceback shows a regression in the handler") == "debugging"
    assert classify_turn_kind("Patch jane_web/main.py and add a function") == "code"


def test_classify_turn_kind_defaults_to_general_and_uses_order_for_ties() -> None:
    assert classify_turn_kind("") == "general"
    assert classify_turn_kind("ordinary conversation with no durable signal") == "general"
    assert classify_turn_kind("calendar email") == "calendar"


def test_classify_turn_kind_only_scores_the_first_4000_chars() -> None:
    assert classify_turn_kind("x" * 4001 + " traceback") == "general"
    assert classify_turn_kind("x" * 3990 + " traceback") == "debugging"
