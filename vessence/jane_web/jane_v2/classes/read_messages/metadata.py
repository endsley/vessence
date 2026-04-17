"""Read messages class — check/read text messages."""

METADATA = {
    "name": "read messages",
    "priority": 10,
    "description": (
        "[read messages]\n"
        "User wants Jane to read incoming SMS / text messages from the "
        "phone inbox. Positive signals: 'read my messages', 'any new "
        "texts?', 'what did X text me?', 'unread messages'.\n"
        "NOT this class: meta questions about a past CONVERSATION turn "
        "with Jane ('the last message you sent me', 'why did your last "
        "reply take so long?') — those are self-reference debugging, "
        "not inbox readback."
    ),
    "few_shot": [
        ("read my messages", "read messages:High"),
        ("any new texts", "read messages:High"),
        ("what did Kathia text me", "read messages:High"),
        ("any unread messages", "read messages:High"),
        ("check my inbox", "read messages:High"),
        ("do I have any new messages", "read messages:High"),
        # Contrast cases — NOT read_messages (meta/debug about Jane's
        # own previous replies, not SMS inbox).
        ("your last message took a while, why?", "others:Low"),
        ("the last message when I asked you took a while", "others:Low"),
        ("why was your last reply so slow", "others:Low"),
        ("why did the last message take so long", "others:Low"),
        ("explain the delay on the last message", "others:Low"),
    ],
    "ack": "Checking your messages…",
    "escalate_ack": "Let me check your messages…",
}
