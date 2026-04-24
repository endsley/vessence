"""todo_list class — classifier metadata."""

import json
import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)

_VESSENCE_DATA_HOME = Path(os.environ.get(
    "VESSENCE_DATA_HOME",
    str(Path.home() / "ambient" / "vessence-data"),
))
_TODO_CACHE_PATH = Path(os.environ.get(
    "TODO_CACHE_PATH",
    str(_VESSENCE_DATA_HOME / "todo_list_cache.json"),
))


def _fetch_live_todo_text() -> str | None:
    """Fetch the TODO list live from Google Docs and return formatted text.

    Returns None on any failure so the caller can fall back to cache.
    """
    try:
        from agent_skills.fetch_todo_list import fetch_doc_text, parse_categories
        raw_text = fetch_doc_text()
        categories = parse_categories(raw_text)
        if not categories:
            return None
        lines = []
        for cat in categories:
            lines.append(f"## {cat['name']}")
            for i, item in enumerate(cat["items"], 1):
                lines.append(f"  {i}. {item}")
            lines.append("")
        return "\n".join(lines).strip()
    except Exception as e:
        _logger.warning("todo_list metadata: live fetch failed: %s", e)
        return None


def _format_cache_data() -> str | None:
    """Read the local cache file and return formatted text as fallback."""
    try:
        raw = _TODO_CACHE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        return None
    categories = data.get("categories", [])
    if not categories:
        return None
    lines = []
    for cat in categories:
        lines.append(f"## {cat['name']}")
        for i, item in enumerate(cat["items"], 1):
            lines.append(f"  {i}. {item}")
        lines.append("")
    return "\n".join(lines).strip()


def _escalation_context() -> str:
    """Inject the live TODO list from Google Docs so Stage 3 (Opus)
    has the data in-context without needing a tool call.

    Fetches live from Google Docs (single source of truth). Falls back
    to the local cache if the live fetch fails (network error, auth
    issue, etc.).
    """
    # Try live fetch first — Google Doc is the source of truth
    todo_text = _fetch_live_todo_text()
    source = "live from Google Docs"
    if todo_text is None:
        # Fall back to cache
        todo_text = _format_cache_data()
        source = f"local cache ({_TODO_CACHE_PATH})"

    lines = []
    if todo_text:
        lines.append(f"Current TODO list ({source}):")
        lines.append(todo_text)
    else:
        lines.append(
            "TODO list is unavailable (live fetch failed and no cached copy). "
            "Ask the user to try again later."
        )

    lines.append("")
    lines.append(
        "Category aliases (user says → Google Doc header):\n"
        "  urgent / immediately / asap → \"Do it Immediately\"\n"
        "  clinic / kathia / water lily → \"For the clinic\"\n"
        "  home / house / household → \"For our Home\"\n"
        "  student / students / school / teaching → \"For my students\"\n"
    )
    lines.append(
        "Note: \"Ambient project goals\" and \"jane\" categories are for "
        "long-range project planning, NOT daily errands. If the user asks "
        "about those, answer from memory/knowledge, not this list."
    )
    lines.append("")
    lines.append(
        "Editing tools (import from agent_skills.docs_tools):\n"
        "  todo_add_item(item_text, category_name) — add an item\n"
        "  todo_remove_item(item_text, category=None) — remove an item"
    )
    return "\n".join(lines)


PARAMS_SCHEMA = {
    "action": (
        "enum REQUIRED — one of: read | add | remove. "
        "read = list/check items. add = put a new item on a list. "
        "remove = cross off / delete an existing item."
    ),
    "category": (
        "string|null — which sub-list. Recognized aliases: "
        "urgent (synonyms: immediately, asap, do-now), "
        "clinic (synonyms: kathia, water lily), "
        "home (synonyms: house, household), "
        "students (synonyms: student, school, teaching). "
        "Null if the user didn't specify a category."
    ),
    "item": (
        "string|null — for action=add: the new task text verbatim. "
        "For action=remove: the phrase identifying which item to cross off "
        "(item text or ordinal like 'first item'). Null for action=read."
    ),
}


METADATA = {
    "name": "todo list",
    "priority": 12,
    "description": (
        "[todo list]\n"
        "Questions about OR edits to Chieh's personal TODO list — errands, "
        "clinic tasks, home chores, student work. Source: a Google Doc "
        "mirrored every 30 min into todo_list_cache.json. Multi-turn: first "
        "turn asks which category (urgent / home / clinic / students); the "
        "user's next reply names the category.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"what's on my todo list\"\n"
        "  - \"what do I need to do today\"\n"
        "  - \"any pending tasks\"\n"
        "  - \"add buy milk to my to-do\"\n"
        "  - \"remove the curtain rods item from my clinic list\"\n"
        "  - \"cross off the first item on my urgent list\"\n"
        "  - \"what errands do I have\"\n\n"
        "Also YES during a todo-list follow-up turn — when Jane just asked "
        "\"which category?\" or listed the categories, the user's next reply "
        "naming any category is a todo_list answer. Examples of valid "
        "follow-up replies:\n"
        "  - \"clinic\"\n"
        "  - \"home\"\n"
        "  - \"urgent\"\n"
        "  - \"students\"\n"
        "  - \"the urgent stuff\"\n"
        "  - \"the clinic stuff please\"\n"
        "  - \"the house one\"\n"
        "  - \"show me the home list\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'todo list' but ARE NOT:\n"
        "  - \"what's on my shopping list\" → 'shopping list' (different list)\n"
        "  - \"what are my ambient project goals\" → 'others' (long-range project planning, not daily errands)\n"
        "  - \"remind me to call x\" → 'timer' or 'others' (reminder, not list add)\n"
        "  - \"what's going on at the clinic today\" → 'others' (ambiguous: could be calendar, not strictly a todo-list query)"
    ),
    "params_schema": PARAMS_SCHEMA,
    "few_shot": [
        ("What's on my todo list?", "todo list:High"),
        ("What do I need to do today?", "todo list:High"),
        ("Any pending tasks?", "todo list:High"),
        ("What's on my to-do?", "todo list:High"),
        ("What errands do I have?", "todo list:High"),
        ("Read me my tasks", "todo list:High"),
        ("What should I do at the clinic?", "todo list:High"),
        ("What do I need to do for home?", "todo list:High"),
        ("What's left for the students?", "todo list:High"),
        ("Anything urgent on my list?", "todo list:High"),
        # Edit intents — add/remove items
        ("Add buy milk to my to-do", "todo list:High"),
        ("Add 'call the plumber' to my home list", "todo list:High"),
        ("Remove the curtain rods item from my clinic list", "todo list:High"),
        ("Cross off the first item on my urgent list", "todo list:High"),
        ("Add a task for students: grade midterms", "todo list:High"),
        ("Delete 'email landlord' from my to-do", "todo list:High"),
        # Contrast cases — NOT todo list
        ("What's on my shopping list?", "shopping list:High"),
        ("Remind me to call Kathia", "timer:Medium"),
        # Ambient project goals → Stage 3, not this handler
        ("What are my ambient project goals?", "others:Low"),
        ("Tell me about the ambient project", "others:Low"),
        ("What's the next step for the ambient project?", "others:Low"),
        ("What am I doing on the ambient project", "others:Low"),
    ],
    "ack": "Checking your TODO list…",
    "escalate_ack": "Let me look at your TODO list a bit more carefully…",
    "escalation_context": _escalation_context,
}
