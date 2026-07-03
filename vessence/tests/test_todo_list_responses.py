import re

from jane_web.jane_v2.classes.todo_list import handler
from jane_web.jane_v2.classes.todo_list.responses import (
    ask_add_category_response,
    ask_add_item_response,
    ask_category_response,
    ask_item_for_category_response,
    ask_remove_item_response,
    build_todo_pending,
    confirm_item_then_ask_category_response,
    done_response,
    empty_list_response,
    missing_cache_response,
    read_and_ask_another,
    simple_todo_response,
    todo_pending_expires_at,
)


def test_todo_handler_uses_extracted_response_helpers() -> None:
    assert handler._pending is build_todo_pending
    assert handler._read_and_ask_another is read_and_ask_another
    assert handler._expires_at is todo_pending_expires_at
    assert handler._ask_add_category_response is ask_add_category_response
    assert handler._ask_add_item_response is ask_add_item_response
    assert handler._ask_category_response is ask_category_response
    assert handler._ask_item_for_category_response is ask_item_for_category_response
    assert handler._ask_remove_item_response is ask_remove_item_response
    assert handler._confirm_item_then_ask_category_response is confirm_item_then_ask_category_response
    assert handler._done_response is done_response
    assert handler._empty_list_response is empty_list_response
    assert handler._missing_cache_response is missing_cache_response
    assert handler._simple_todo_response is simple_todo_response


def test_build_todo_pending_preserves_followup_shape() -> None:
    assert build_todo_pending(
        "category",
        {"already_read": ["For our Home"]},
        question="Which category?",
        expires_at="2030-01-02T03:04:05Z",
    ) == {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "todo list",
        "status": "awaiting_user",
        "awaiting": "category",
        "data": {"already_read": ["For our Home"], "awaiting": "category"},
        "question": "Which category?",
        "expires_at": "2030-01-02T03:04:05Z",
    }

    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        todo_pending_expires_at(),
    )


def test_simple_todo_response_builders_preserve_common_shapes() -> None:
    assert simple_todo_response("plain") == {
        "text": "plain",
        "structured": {"intent": "todo list"},
    }
    assert simple_todo_response(
        "done",
        entities={"action": "add"},
        conversation_end=True,
    ) == {
        "text": "done",
        "conversation_end": True,
        "structured": {"intent": "todo list", "entities": {"action": "add"}},
    }
    assert done_response("Added buy milk", entities={"action": "add"}) == {
        "text": "Done. Added buy milk",
        "structured": {"intent": "todo list", "entities": {"action": "add"}},
    }
    assert missing_cache_response() == {
        "text": (
            "I don't have a cached copy of your TODO list yet. "
            "The cron job may not have run since Jane last started."
        ),
        "structured": {"intent": "todo list"},
    }
    assert empty_list_response() == {
        "text": "Your TODO list looks empty right now.",
        "structured": {"intent": "todo list"},
    }


def test_followup_prompt_response_builders_preserve_pending_shapes() -> None:
    categories = [
        {"name": "For our Home", "items": ["Buy milk"]},
        {"name": "For the clinic", "items": ["Order forms"]},
    ]

    ask_category = ask_category_response(categories)
    assert ask_category["text"] == (
        "Two categories: home and the clinic. Which one do you want to hear?"
    )
    assert ask_category["structured"]["entities"] == {"stage": "await_category"}
    assert ask_category["structured"]["pending_action"]["awaiting"] == "category"
    assert ask_category["structured"]["pending_action"]["question"] == ask_category["text"]

    ask_add_item = ask_add_item_response()
    assert ask_add_item["text"] == "What item should I add?"
    assert ask_add_item["structured"]["entities"] == {"action": "add"}
    assert ask_add_item["structured"]["pending_action"]["awaiting"] == "add_item"

    ask_remove_item = ask_remove_item_response()
    assert ask_remove_item["text"] == "Which item should I remove? Tell me the text or item number."
    assert ask_remove_item["structured"]["entities"] == {"action": "remove"}
    assert ask_remove_item["structured"]["pending_action"]["awaiting"] == "remove_item"


def test_read_and_ask_another_preserves_pending_continuation_shape() -> None:
    categories = [
        {"name": "For our Home", "items": ["Buy milk"]},
        {"name": "For the clinic", "items": ["Order forms"]},
    ]

    result = read_and_ask_another(categories[0], categories)

    assert result["text"] == "For home: Buy milk. Want to hear another category?"
    structured = result["structured"]
    assert structured["entities"] == {"category": "For our Home"}
    assert structured["pending_action"]["awaiting"] == "another_category_or_stop"
    assert structured["pending_action"]["question"] == "Want to hear another category?"
    assert structured["pending_action"]["data"] == {
        "already_read": ["For our Home"],
        "awaiting": "another_category_or_stop",
    }


def test_add_followup_response_builders_preserve_pending_shapes() -> None:
    categories = [
        {"name": "For our Home", "items": ["Buy milk"]},
        {"name": "Urgent Stuff", "items": ["Call"]},
    ]

    ask_item = ask_item_for_category_response("Urgent Stuff")
    assert ask_item["text"] == "What item should I add to Urgent Stuff?"
    assert ask_item["structured"]["entities"] == {
        "action": "add",
        "category": "Urgent Stuff",
    }
    assert ask_item["structured"]["pending_action"]["awaiting"] == "add_item_for_category"
    assert ask_item["structured"]["pending_action"]["question"] == ask_item["text"]

    ask_category = ask_add_category_response(categories, item_text="buy stamps")
    assert ask_category["text"].endswith("Which category should I add it to?")
    assert ask_category["structured"]["entities"] == {
        "action": "add",
        "item_text": "buy stamps",
    }
    assert ask_category["structured"]["pending_action"]["awaiting"] == "add_category"
    assert ask_category["structured"]["pending_action"]["data"]["item_text"] == "buy stamps"

    ask_category_then_item = ask_add_category_response(categories)
    assert ask_category_then_item["structured"]["entities"] == {"action": "add"}
    assert ask_category_then_item["structured"]["pending_action"]["awaiting"] == (
        "add_category_then_item"
    )

    confirm_then_ask = confirm_item_then_ask_category_response("buy stamps")
    assert confirm_then_ask["text"] == "Got it: 'buy stamps'. Which category should I add it to?"
    assert confirm_then_ask["structured"]["pending_action"]["awaiting"] == "add_category"


def test_read_and_ask_another_ends_when_no_visible_items_remain() -> None:
    categories = [
        {"name": "For our Home", "items": ["Buy milk"]},
        {"name": "Jane", "items": ["internal"]},
        {"name": "For the clinic", "items": []},
    ]

    result = read_and_ask_another(categories[0], categories)

    assert result == {
        "text": "For home: Buy milk. That's everything on your list.",
        "conversation_end": True,
        "structured": {
            "intent": "todo list",
            "entities": {"category": "For our Home"},
        },
    }
