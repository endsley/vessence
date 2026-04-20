"""Read calendar class — check/read Google Calendar events."""

METADATA = {
    "name": "read calendar",
    "priority": 10,
    "description": (
        "[read calendar]\n"
        "User wants Jane to check / read / summarize their Google Calendar. "
        "The server fetches events via the Google Calendar API (server-side, "
        "NOT via the phone). The brain sees a [CALENDAR DATA] block with "
        "events for the requested range and summarizes them.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"what's on my calendar today\"\n"
        "  - \"what's on my calendar tomorrow\"\n"
        "  - \"check my calendar\"\n"
        "  - \"what's my agenda today\"\n"
        "  - \"anything on my calendar this week\"\n"
        "  - \"what do I have on my calendar today\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'read calendar' but ARE NOT:\n"
        "  - \"schedule a meeting with Bob tomorrow\" → 'others' (create event)\n"
        "  - \"cancel my 3pm\" → 'others' (edit event)\n"
        "  - \"move my meeting to tomorrow\" → 'others' (edit event)\n"
        "  - \"tell Kathia I have a meeting today\" → 'send message'\n"
        "  - \"what did we talk about in yesterday's meeting\" → 'others' (memory)\n"
        "  - \"what time is it\" → 'get time'"
    ),
    "few_shot": [],
    "ack": "Checking your calendar…",
    "escalate_ack": "Let me check your calendar…",
}
