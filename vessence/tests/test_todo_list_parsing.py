from jane_web.jane_v2.classes.todo_list import handler
from jane_web.jane_v2.classes.todo_list.parsing import (
    detect_edit_intent,
    extract_item_text,
    is_placeholder_item_text,
)


def test_todo_handler_uses_extracted_edit_parsing_helpers():
    assert handler._detect_edit_intent is detect_edit_intent
    assert handler._extract_item_text is extract_item_text


def test_detect_edit_intent_for_add_remove_and_none():
    assert detect_edit_intent("add buy milk to my to-do") == "add"
    assert detect_edit_intent("put curtain rods on my home list") == "add"
    assert detect_edit_intent("cross off curtain rods") == "remove"
    assert detect_edit_intent("what is on my todo list") is None


def test_placeholder_item_text_is_not_treated_as_task_text():
    assert is_placeholder_item_text("an item")
    assert is_placeholder_item_text("new todo")
    assert not is_placeholder_item_text("buy milk")


def test_extract_add_item_text_from_supported_phrases():
    assert extract_item_text("add 'call the plumber' to my home list", "add") == "call the plumber"
    assert (
        extract_item_text(
            "add an item to the clinic and the item is to create a Gmail account.",
            "add",
        )
        == "to create a Gmail account"
    )
    assert extract_item_text("add a task for students: grade midterms", "add") == "grade midterms"
    assert extract_item_text("add buy milk to my to-do", "add") == "buy milk"
    assert extract_item_text("add an item to my list", "add") == "an item"
    assert is_placeholder_item_text(extract_item_text("add an item to my list", "add"))


def test_extract_remove_item_text_from_supported_phrases():
    assert extract_item_text("remove 'curtain rods' from my clinic list", "remove") == "curtain rods"
    assert extract_item_text("remove the curtain rods item", "remove") == "curtain rods"
    assert extract_item_text("delete email landlord from my todo", "remove") == "email landlord"
