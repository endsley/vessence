"""Read email class — check/read email inbox."""

PARAMS_SCHEMA = {
    "filter_sender": (
        "string|null — sender name the user asked about ('did Alice email me'). "
        "Null when the user wants the inbox overview."
    ),
    "unread_only": (
        "bool — true for 'new/unread/any new emails'. false for 'recent emails'."
    ),
    "importance": (
        "enum — one of: any | important. "
        "important when the user said 'important', 'urgent', 'real ones'. "
        "any otherwise."
    ),
    "limit": (
        "int|null — explicit cap ('top 5 emails'). Null = handler default."
    ),
}


METADATA = {
    "name": "read email",
    "priority": 10,
    "description": (
        "[read email]\n"
        "User wants Jane to check / read / summarize their email inbox. "
        "The server fetches emails via the Gmail API (server-side, NOT "
        "via the phone). The brain sees an [EMAIL INBOX DATA] block with "
        "the unread messages and summarizes them by importance.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"check my email\"\n"
        "  - \"any new emails\"\n"
        "  - \"read my email\"\n"
        "  - \"what's in my inbox\"\n"
        "  - \"did Alice email me\"\n"
        "  - \"how many unread emails do I have\"\n"
        "  - \"any important email today\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'read email' but ARE NOT:\n"
        "  - \"send an email to Bob\" → 'others' (Opus composes + sends)\n"
        "  - \"delete all spam emails\" → 'others' (bulk action not supported)\n"
        "  - \"archive the email from Alice\" → 'others'\n"
        "  - \"read my text messages\" → 'read messages' (SMS, not email)\n"
        "  - \"what did Bob say in his last email last week\" → 'others' (needs memory / search)"
    ),
    "params_schema": PARAMS_SCHEMA,
    "few_shot": [],
    "ack": "Checking your email…",
    "escalate_ack": "Let me check your email…",
}
