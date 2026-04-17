"""todo_list class — classifier metadata."""


METADATA = {
    "name": "todo list",
    "priority": 12,
    "description": (
        "[todo list]\n"
        "Questions about OR edits to Chieh's personal TODO list — errands, "
        "clinic tasks, home chores, student work. "
        "- Source: a Google Doc mirrored every 30 min by a cron job into "
        "$VESSENCE_DATA_HOME/todo_list_cache.json\n"
        "- Read AND write: can read items back, and add/remove items "
        "via the Google Docs API.\n"
        "- Flow: first turn asks which category the user wants; the "
        "pending_action routes the next reply back to this handler.\n"
        "- DOES NOT handle: shopping list (its own class), general "
        "scheduling, or 'Ambient project goals' — Ambient goals are a "
        "separate project-planning topic that escalates to Stage 3, "
        "NOT this fast personal-errand readback."
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
}
