"""Response builders for the TODO-list Stage 2 handler."""
from __future__ import annotations

import datetime as _dt

from agent_skills.private_handler_utils import pending_continuation_data

from .categories import friendly_category_name, speak_category_list, speak_items, visible_categories

TODO_INTENT = "todo list"


def todo_pending_expires_at(minutes: int = 2) -> str:
    return (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def build_todo_pending(
    awaiting: str,
    data: dict,
    question: str = "",
    *,
    expires_at: str | None = None,
) -> dict:
    """Build a STAGE2_FOLLOWUP pending_action for TODO-list turns."""
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "todo list",
        "status": "awaiting_user",
        "awaiting": awaiting,
        "data": pending_continuation_data(data, awaiting),
        "question": question,
        "expires_at": expires_at or todo_pending_expires_at(),
    }


def simple_todo_response(
    text: str,
    *,
    entities: dict | None = None,
    conversation_end: bool = False,
) -> dict:
    structured = {"intent": TODO_INTENT}
    if entities is not None:
        structured["entities"] = entities
    response: dict = {"text": text, "structured": structured}
    if conversation_end:
        response["conversation_end"] = True
    return response


def done_response(result: str, *, entities: dict | None = None) -> dict:
    return simple_todo_response(f"Done. {result}", entities=entities)


def missing_cache_response() -> dict:
    return simple_todo_response(
        "I don't have a cached copy of your TODO list yet. "
        "The cron job may not have run since Jane last started."
    )


def empty_list_response() -> dict:
    return simple_todo_response("Your TODO list looks empty right now.")


def ask_category_response(categories: list[dict]) -> dict:
    text = speak_category_list(categories)
    return {
        "text": text,
        "structured": {
            "intent": TODO_INTENT,
            "entities": {"stage": "await_category"},
            "pending_action": build_todo_pending("category", {}, question=text),
        },
    }


def ask_add_item_response() -> dict:
    ask = "What item should I add?"
    return {
        "text": ask,
        "structured": {
            "intent": TODO_INTENT,
            "entities": {"action": "add"},
            "pending_action": build_todo_pending("add_item", {"action": "add"}, question=ask),
        },
    }


def ask_remove_item_response() -> dict:
    ask = "Which item should I remove? Tell me the text or item number."
    return {
        "text": ask,
        "structured": {
            "intent": TODO_INTENT,
            "entities": {"action": "remove"},
            "pending_action": build_todo_pending("remove_item", {"action": "remove"}, question=ask),
        },
    }


def read_and_ask_another(
    cat: dict,
    categories: list[dict],
    already_read: list[str] | None = None,
) -> dict:
    """Read one category and, when useful, ask whether to continue."""
    spoken = speak_items(cat)
    seen = list(already_read or [])
    if cat.get("name") and cat["name"] not in seen:
        seen.append(cat["name"])
    remaining = [
        category.get("name", "")
        for category in visible_categories(categories)
        if category.get("name") and category["name"] not in seen and category.get("items")
    ]
    if not remaining:
        text = f"{spoken} That's everything on your list."
        return {
            "text": text,
            "conversation_end": True,
            "structured": {
                "intent": TODO_INTENT,
                "entities": {"category": cat.get("name", "")},
            },
        }
    follow = "Want to hear another category?"
    text = f"{spoken} {follow}"
    return {
        "text": text,
        "structured": {
            "intent": TODO_INTENT,
            "entities": {"category": cat.get("name", "")},
            "pending_action": build_todo_pending(
                "another_category_or_stop",
                {"already_read": seen},
                question=follow,
            ),
        },
    }


def ask_item_for_category_response(category_name: str) -> dict:
    ask = f"What item should I add to {friendly_category_name(category_name)}?"
    return {
        "text": ask,
        "structured": {
            "intent": TODO_INTENT,
            "entities": {"action": "add", "category": category_name},
            "pending_action": build_todo_pending(
                "add_item_for_category",
                {"action": "add", "category": category_name},
                question=ask,
            ),
        },
    }


def ask_add_category_response(categories: list[dict], item_text: str | None = None) -> dict:
    text = speak_category_list(categories).replace(
        "Which one do you want to hear?",
        "Which category should I add it to?",
    )
    entities = {"action": "add"}
    pending_data = {"action": "add"}
    awaiting = "add_category_then_item"
    if item_text:
        entities["item_text"] = item_text
        pending_data["item_text"] = item_text
        awaiting = "add_category"
    return {
        "text": text,
        "structured": {
            "intent": TODO_INTENT,
            "entities": entities,
            "pending_action": build_todo_pending(
                awaiting,
                pending_data,
                question=text,
            ),
        },
    }


def confirm_item_then_ask_category_response(item_text: str) -> dict:
    ask = f"Got it: '{item_text}'. Which category should I add it to?"
    return {
        "text": ask,
        "structured": {
            "intent": TODO_INTENT,
            "entities": {"action": "add", "item_text": item_text},
            "pending_action": build_todo_pending(
                "add_category",
                {"action": "add", "item_text": item_text},
                question=ask,
            ),
        },
    }
