"""Send message class — text/SMS someone."""

METADATA = {
    "name": "send message",
    "priority": 10,
    "description": "",
    "few_shot": [],
    "ack": None,  # Stage 2 fast-path is quick enough — no interim ack needed
    "escalate_ack": "Let me draft that message…",
}
