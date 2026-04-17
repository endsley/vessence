"""Timer class — client-side Android timer (works offline via AlarmManager)."""

METADATA = {
    "name": "timer",
    "priority": 10,
    "description": "",
    "few_shot": [
        ("set a 10 minute timer", "timer:High"),
        ("remind me in an hour", "timer:High"),
        ("cancel my timer", "timer:High"),
        ("what timers do I have", "timer:High"),
    ],
    "ack": "Setting your timer…",
    "escalate_ack": "Let me handle the timer…",
}
