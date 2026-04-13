"""Get time class — current time/date queries delegated to phone."""

METADATA = {
    "name": "get time",
    "priority": 10,
    "description": "",
    "few_shot": [
        ("what time is it", "get time:High"),
        ("what's the current time", "get time:High"),
        ("what day is today", "get time:High"),
    ],
    "ack": None,
    "escalate_ack": None,
}
