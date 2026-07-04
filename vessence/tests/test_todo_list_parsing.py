import asyncio
import sys
import types

from jane_web.jane_v2.classes.todo_list import handler
from jane_web.jane_v2.classes.todo_list.parsing import (
    detect_edit_intent,
    extract_item_text,
    is_placeholder_item_text,
    quoted_item_text,
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


def test_quoted_item_text_extracts_straight_and_curly_quoted_items():
    assert quoted_item_text("add 'call the plumber' to my home list") == "call the plumber"
    assert quoted_item_text("remove “curtain rods” from my clinic list") == "curtain rods"
    assert quoted_item_text("add buy milk") is None


def test_todo_params_normalization_strips_action_item_and_category() -> None:
    assert handler._todo_action_params(None) == handler._TodoActionParams()
    assert handler._todo_action_params({
        "action": " ADD ",
        "item": "  buy milk  ",
        "category": " home ",
    }) == handler._TodoActionParams(
        action="add",
        item="buy milk",
        category="home",
    )


def test_todo_params_edit_dispatch_delegates_to_edit_helper(monkeypatch) -> None:
    calls = []

    async def fake_handle_edit(prompt, edit_type, categories, **kwargs):
        calls.append((prompt, edit_type, categories, kwargs))
        return {"text": "done"}

    monkeypatch.setattr(handler, "_handle_edit", fake_handle_edit)

    handled, response = asyncio.run(
        handler._handle_params_edit(
            "add buy milk",
            [{"name": "For our Home", "items": []}],
            handler._TodoActionParams(action="add", item="buy milk", category="home"),
        )
    )

    assert handled is True
    assert response == {"text": "done"}
    assert calls == [
        (
            "add buy milk",
            "add",
            [{"name": "For our Home", "items": []}],
            {
                "item_text": "buy milk",
                "category_name": "home",
                "from_params": True,
            },
        )
    ]


def test_todo_params_edit_dispatch_ignores_non_edit_actions() -> None:
    assert asyncio.run(
        handler._handle_params_edit(
            "read my home list",
            [],
            handler._TodoActionParams(action="read", category="home"),
        )
    ) == (False, None)


def test_todo_first_turn_declines_ambient_project_prompts() -> None:
    assert handler._should_decline_ambient_project("what is on the Ambient project list")
    assert not handler._should_decline_ambient_project("what is on the home project list")


def test_todo_shopping_list_params_maps_supported_actions() -> None:
    assert handler._shopping_list_params(None) is None
    assert handler._shopping_list_params({"action": "read", "item": "milk"}) is None
    assert handler._shopping_list_params({"action": "add", "item": "milk"}) == {
        "action": "add",
        "items": "milk",
    }
    assert handler._shopping_list_params({"action": "remove", "item": "milk"}) == {
        "action": "remove",
        "items": "milk",
    }
    assert handler._shopping_list_params({"action": "check", "item": None}) == {
        "action": "view",
        "items": None,
    }


def test_todo_maybe_delegate_shopping_list_ignores_non_shopping_prompt() -> None:
    assert asyncio.run(handler._maybe_delegate_shopping_list("read my todo list", None)) == (
        False,
        None,
    )


def test_todo_first_turn_read_response_handles_empty_and_params_category() -> None:
    empty = handler._first_turn_read_response("read my list", [], handler._TodoActionParams())
    assert empty["text"] == "Your TODO list looks empty right now."

    home = handler._first_turn_read_response(
        "read my list",
        [
            {"name": "For our Home", "items": ["fix sink"]},
            {"name": "For the clinic", "items": ["order tea"]},
        ],
        handler._TodoActionParams(category="home"),
    )
    assert home["structured"]["entities"]["category"] == "For our Home"
    assert home["structured"]["pending_action"]["awaiting"] == "another_category_or_stop"


def test_todo_first_turn_read_response_uses_direct_match_or_asks_category() -> None:
    categories = [
        {"name": "For our Home", "items": ["fix sink"]},
        {"name": "For the clinic", "items": ["order tea"]},
    ]

    direct = handler._first_turn_read_response(
        "what is on the clinic list",
        categories,
        handler._TodoActionParams(),
    )
    ask = handler._first_turn_read_response(
        "what is on my todo list",
        categories,
        handler._TodoActionParams(),
    )

    assert direct["structured"]["entities"]["category"] == "For the clinic"
    assert ask["structured"]["entities"] == {"stage": "await_category"}


def test_todo_pending_data_accepts_wrapper_and_legacy_shapes() -> None:
    wrapper = {"awaiting": "legacy", "data": {"awaiting": "add_item", "category": "For our Home"}}
    legacy = {"awaiting": "category"}

    wrapper_data = handler._todo_pending_data(wrapper)

    assert wrapper_data == {"awaiting": "add_item", "category": "For our Home"}
    assert handler._todo_pending_awaiting(wrapper, wrapper_data) == "add_item"
    assert handler._todo_pending_data(legacy) == legacy
    assert handler._todo_pending_awaiting(legacy, legacy) == "category"


def test_todo_resume_edit_ignores_reading_followups() -> None:
    assert asyncio.run(
        handler._handle_resume_edit("home", {}, "category", [{"name": "For our Home", "items": []}])
    ) == (False, None)


def test_todo_resume_add_category_then_item_asks_for_item() -> None:
    handled, response = asyncio.run(
        handler._handle_resume_edit(
            "home",
            {"awaiting": "add_category_then_item"},
            "add_category_then_item",
            [{"name": "For our Home", "items": ["fix sink"]}],
        )
    )

    assert handled is True
    assert response["structured"]["entities"] == {"action": "add", "category": "For our Home"}
    assert response["structured"]["pending_action"]["awaiting"] == "add_item_for_category"


def test_todo_resume_add_category_abandons_without_category_match() -> None:
    handled, response = asyncio.run(
        handler._handle_resume_edit(
            "somewhere else",
            {"awaiting": "add_category", "item_text": "buy milk"},
            "add_category",
            [{"name": "For our Home", "items": []}],
        )
    )

    assert handled is True
    assert response == {"abandon_pending": True}


def test_todo_resume_add_item_for_category_uses_saved_category(monkeypatch) -> None:
    calls = []
    fake_docs_tools = types.ModuleType("agent_skills.docs_tools")

    def fake_add_item(item_text, category):
        calls.append((item_text, category))
        return "added"

    fake_docs_tools.todo_add_item = fake_add_item
    monkeypatch.setitem(sys.modules, "agent_skills.docs_tools", fake_docs_tools)
    monkeypatch.setattr(handler, "_refresh_cache", lambda: None)

    handled, response = asyncio.run(
        handler._handle_resume_edit(
            "buy milk",
            {"awaiting": "add_item_for_category", "category": "For our Home"},
            "add_item_for_category",
            [{"name": "For our Home", "items": []}],
        )
    )

    assert handled is True
    assert calls == [("buy milk", "For our Home")]
    assert response["text"] == "Done. added"
    assert response["structured"]["entities"] == {
        "action": "add",
        "category": "For our Home",
        "item_text": "buy milk",
    }


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
