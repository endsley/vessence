"""Timer class — client-side Android timer (works offline via AlarmManager)."""

METADATA = {
    "name": "timer",
    "priority": 10,
    "description": (
        "[timer]\n"
        "User wants to set, cancel, list, or delete a phone timer. The "
        "phone owns every alarm via AlarmManager; Jane emits CLIENT_TOOL "
        "markers and Android handles scheduling (timers ring even "
        "offline). Multi-turn: if duration or label is missing, Jane asks "
        "a follow-up; the reply fills in the slot.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"set a 5 minute timer\"\n"
        "  - \"start a 10-minute timer called pasta\"\n"
        "  - \"remind me in an hour\"\n"
        "  - \"timer for 30 minutes\"\n"
        "  - \"cancel my timer\"\n"
        "  - \"list my timers\"\n"
        "  - \"delete the pasta timer\"\n\n"
        "Also YES during a timer follow-up turn:\n"
        "  - after \"how long should the timer run?\" → \"five minutes\", "
        "\"an hour\", \"2 and a half minutes\" are timer duration answers\n"
        "  - after \"what should I call this timer?\" → \"pasta\", "
        "\"bread\", \"no label\" are timer label answers\n\n"
        "Adversarial phrasings that LOOK LIKE 'timer' but ARE NOT:\n"
        "  - \"what time is it\" → 'get time' (clock, not timer)\n"
        "  - \"how long until 5pm\" → 'others' (arithmetic / calendar)\n"
        "  - \"schedule a meeting for 3pm tomorrow\" → 'others' (calendar)\n"
        "  - \"remind me to call mom tomorrow\" → 'others' (day-scale reminder, not short timer)\n"
        "  - \"stop\" (said mid-conversation) → 'end conversation' (sign-off, not cancel-timer)"
    ),
    "few_shot": [
        ("set a 10 minute timer", "timer:High"),
        ("remind me in an hour", "timer:High"),
        ("cancel my timer", "timer:High"),
        ("what timers do I have", "timer:High"),
    ],
    "ack": "Setting your timer…",
    "escalate_ack": "Let me handle the timer…",
    "escalation_context": (
        "[timer escalation context]\n"
        "Timer actions: set, cancel, list, delete.\n\n"
        "Duration parsing: natural language like \"5 minutes\", \"an hour "
        "and a half\", \"90 seconds\". Convert to milliseconds.\n\n"
        "Timers are phone-side (Android AlarmManager) — they ring even "
        "offline. Use CLIENT_TOOL markers; the server keeps NO timer state.\n\n"
        "CLIENT_TOOL formats:\n"
        "  Set:    [[CLIENT_TOOL:timer.set:{\"duration_ms\":<ms>,\"label\":\"...\"}]]\n"
        "  Cancel: [[CLIENT_TOOL:timer.cancel:{}]]\n"
        "  List:   [[CLIENT_TOOL:timer.list:{}]]\n"
        "  Delete: [[CLIENT_TOOL:timer.delete:{\"label\":\"...\"}]] or "
        "[[CLIENT_TOOL:timer.delete:{\"index\":<n>}]]"
    ),
}
