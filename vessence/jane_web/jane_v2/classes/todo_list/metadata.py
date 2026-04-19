"""todo_list class — classifier metadata."""

import json
import os
from pathlib import Path

_VESSENCE_DATA_HOME = Path(os.environ.get(
    "VESSENCE_DATA_HOME",
    str(Path.home() / "ambient" / "vessence-data"),
))
_TODO_CACHE_PATH = Path(os.environ.get(
    "TODO_CACHE_PATH",
    str(_VESSENCE_DATA_HOME / "todo_list_cache.json"),
))


def _escalation_context() -> str:
    """Inject the cached TODO list and category aliases so Stage 3 (Opus)
    can read/edit the list without re-fetching."""
    try:
        data = _TODO_CACHE_PATH.read_text(encoding="utf-8")
    except Exception:
        data = None

    lines = []
    if data:
        lines.append(f"TODO list cache ({_TODO_CACHE_PATH}):")
        lines.append(data)
    else:
        lines.append("TODO list cache is unavailable (cron may not have run yet).")

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
