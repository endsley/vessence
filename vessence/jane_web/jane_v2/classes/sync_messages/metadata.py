"""Sync messages class — force SMS re-sync from device."""

METADATA = {
    "name": "sync messages",
    "priority": 10,
    "description": "",
    "few_shot": [],
    "ack": None,  # Stage 2 fast-path is instant — no interim ack needed
    "escalate_ack": None,
}
