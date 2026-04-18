"""Get time class — current time/date queries delegated to phone."""

METADATA = {
    "name": "get time",
    "priority": 10,
    "description": (
        "[get time]\n"
        "User wants the current wall-clock time or date. The handler emits a "
        "client_tool that reads the phone's local clock and speaks the time "
        "aloud via TTS — no server lookup, no weather involved.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"what time is it\"\n"
        "  - \"what's the time right now\"\n"
        "  - \"tell me the time\"\n"
        "  - \"what day is it today\"\n"
        "  - \"what's the date\"\n"
        "  - \"is it morning or afternoon\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'get time' but ARE NOT:\n"
        "  - \"what time did you send that message\" → 'others' (past event reference)\n"
        "  - \"what time is my meeting tomorrow\" → 'others' (calendar lookup)\n"
        "  - \"how long until 5pm\" → 'others' (arithmetic, not clock read)\n"
        "  - \"set a 5 minute timer\" → 'timer' (scheduling, not time query)\n"
        "  - \"the time you told me was wrong\" → 'others' (complaint)\n"
        "  - \"what time is it in tokyo\" → 'others' (non-local time zone, not in phone clock)"
    ),
    "few_shot": [
        ("what time is it", "get time:High"),
        ("what's the current time", "get time:High"),
        ("what day is today", "get time:High"),
    ],
    "ack": None,
    "escalate_ack": None,
}
