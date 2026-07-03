import math

import pytest

from agent_skills import shopping_list
from agent_skills.shopping_list_data import (
    CONFIDENCE_THRESHOLD,
    add_item_to_lists,
    clear_list_in_lists,
    coerce_lists_data,
    format_lists_for_context,
    list_key,
    remove_item_from_lists,
    require_confidence,
)


def test_shopping_list_module_exposes_legacy_confidence_helper_and_constant():
    assert shopping_list._CONFIDENCE_THRESHOLD == CONFIDENCE_THRESHOLD
    assert shopping_list._require_confidence is require_confidence


def test_coerce_lists_data_accepts_only_string_lists():
    valid = {"default": ["milk"], "costco": []}

    assert coerce_lists_data(valid) is valid
    assert coerce_lists_data([]) == {}
    assert coerce_lists_data({1: ["milk"]}) == {}
    assert coerce_lists_data({"default": ["milk", 3]}) == {}
    assert coerce_lists_data({"default": "milk"}) == {}


def test_list_key_lowercases_without_stripping_existing_key_behavior():
    assert list_key("Costco") == "costco"
    assert list_key(" Costco ") == " costco "
    with pytest.raises(ValueError, match="list_name is required"):
        list_key("   ")


def test_require_confidence_preserves_threshold_and_type_rules():
    require_confidence(CONFIDENCE_THRESHOLD)
    require_confidence(1)
    require_confidence(math.inf)

    with pytest.raises(PermissionError, match="below"):
        require_confidence(0.79)
    with pytest.raises(PermissionError, match="below"):
        require_confidence(math.nan)
    with pytest.raises(TypeError, match="numeric"):
        require_confidence(True)
    with pytest.raises(TypeError, match="numeric"):
        require_confidence("0.95")


def test_add_item_to_lists_creates_lowercase_list_and_dedupes_case_insensitively():
    data: dict[str, list[str]] = {}

    first = add_item_to_lists(data, "  Milk  ", "Default")
    second = add_item_to_lists(data, "milk", "DEFAULT")
    empty = add_item_to_lists(data, "   ", "Errands")

    assert first.items == ["Milk"]
    assert second.items == ["Milk"]
    assert empty.items == []
    assert data == {"default": ["Milk"], "errands": []}


def test_remove_item_from_lists_mutates_existing_lists_only():
    data = {"default": ["Milk", "eggs"]}

    removed = remove_item_from_lists(data, " milk ", "DEFAULT")
    missing = remove_item_from_lists(data, "bread", "missing")

    assert removed.items == ["eggs"]
    assert removed.should_save
    assert missing.items == []
    assert not missing.should_save
    assert data == {"default": ["eggs"]}
    with pytest.raises(ValueError, match="item is required"):
        remove_item_from_lists(data, "   ")


def test_clear_list_in_lists_sets_empty_list_and_requests_save():
    data = {"costco": ["paper towels"]}

    mutation = clear_list_in_lists(data, "Costco")

    assert mutation.items == []
    assert mutation.should_save
    assert data == {"costco": []}


def test_format_lists_for_context_preserves_existing_text():
    assert format_lists_for_context({}) == (
        "No shopping lists exist yet. The user can ask you to create one."
    )
    assert format_lists_for_context({"default": ["milk"], "costco": []}) == (
        "**Default list:**\n"
        "  - milk\n\n"
        "**Costco list:** (empty)"
    )
