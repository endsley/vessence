import math

from jane_web.jane_v2.classes.shopping_list import handler
from jane_web.jane_v2.classes.shopping_list.actions import (
    DESTRUCTIVE_ACTIONS,
    DESTRUCTIVE_CONFIDENCE_THRESHOLD,
    VALID_ACTIONS,
    destructive_confidence_ok,
    format_check_response,
    parse_action_params,
    split_items,
    split_present_missing,
)
from jane_web.jane_v2.classes.shopping_list.responses import (
    build_add_response,
    build_check_response,
    build_clear_response,
    build_remove_response,
    build_view_response,
)


def test_handler_uses_extracted_shopping_list_helpers() -> None:
    assert handler._VALID_ACTIONS is VALID_ACTIONS
    assert handler._parse_action_params is parse_action_params
    assert handler._split_items is split_items
    assert handler._destructive_confidence_ok is destructive_confidence_ok
    assert handler._split_present_missing is split_present_missing
    assert handler._build_view_response is build_view_response
    assert handler._build_add_response is build_add_response
    assert handler._build_remove_response is build_remove_response
    assert handler._build_clear_response is build_clear_response
    assert handler._build_check_response is build_check_response


def test_split_items_accepts_comma_separated_strings_only() -> None:
    assert split_items("milk, eggs,  bread ") == ["milk", "eggs", "bread"]
    assert split_items("milk,, eggs") == ["milk", "eggs"]
    assert split_items("") == []
    assert split_items(None) == []
    assert split_items(["milk"]) == []


def test_destructive_confidence_ok_rejects_bool_non_numeric_and_nonfinite_values() -> None:
    assert DESTRUCTIVE_ACTIONS == {"remove", "clear"}
    assert destructive_confidence_ok(DESTRUCTIVE_CONFIDENCE_THRESHOLD)
    assert destructive_confidence_ok(1)
    assert not destructive_confidence_ok(0.79)
    assert not destructive_confidence_ok(True)
    assert not destructive_confidence_ok("0.95")
    assert not destructive_confidence_ok(math.nan)
    assert not destructive_confidence_ok(math.inf)


def test_parse_action_params_validates_before_store_mutation() -> None:
    assert parse_action_params(None) == ("missing_params", None)
    assert parse_action_params({"action": 7}) == ("malformed_action", {"raw_action": 7})
    assert parse_action_params({"action": " reorder "}) == ("unknown_action", {"action": "reorder"})

    assert parse_action_params({"action": " add ", "items": "milk, eggs", "confidence": 0.1}) == (
        "ok",
        {"action": "add", "items": ["milk", "eggs"], "confidence": None},
    )
    assert parse_action_params({"action": "remove", "items": "milk", "confidence": 0.79}) == (
        "low_confidence",
        {"action": "remove", "confidence": 0.79},
    )
    assert parse_action_params({"action": "clear", "confidence": 0.8}) == (
        "ok",
        {"action": "clear", "items": [], "confidence": 0.8},
    )


def test_split_present_missing_is_case_insensitive_and_preserves_requested_text() -> None:
    assert split_present_missing(["Milk", "bananas"], ["milk", "Eggs"]) == (
        ["Milk"],
        ["bananas"],
    )


def test_format_check_response_preserves_existing_handler_text() -> None:
    assert format_check_response(["milk"], []) == "Yes — milk is on your shopping list."
    assert format_check_response([], ["bananas"]) == "No — bananas is not on your shopping list."
    assert format_check_response(["milk"], ["bananas"]) == (
        "Mixed: milk is on the list; bananas is not."
    )


def test_shopping_list_response_builders_preserve_text_shapes() -> None:
    assert build_view_response([]) == {"text": "Your shopping list is empty."}
    assert build_view_response(["milk", "eggs"]) == {
        "text": "Your shopping list has: milk, eggs."
    }
    assert build_add_response(["milk"], ["milk", "eggs"]) == {
        "text": "Added milk. Your shopping list now has 2 items."
    }
    assert build_remove_response(["milk", "eggs"]) == {
        "text": "Removed milk, eggs from your shopping list."
    }
    assert build_clear_response() == {"text": "Your shopping list has been cleared."}
    assert build_check_response(["milk"], ["bananas"]) == {
        "text": "Mixed: milk is on the list; bananas is not."
    }
