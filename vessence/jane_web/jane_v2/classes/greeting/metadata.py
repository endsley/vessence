"""Greeting class — standalone greetings, presence checks, how-are-you."""

METADATA = {
    "name": "greeting",
    "priority": 5,
    "description": "",  # No schema block needed — ChromaDB handles classification
    "few_shot": [],
    "ack": None,  # Greetings should get immediate response, no "thinking" ack
    "escalate_ack": None,
}
