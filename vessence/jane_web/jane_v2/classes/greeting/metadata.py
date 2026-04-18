"""Greeting class — standalone greetings, presence checks, how-are-you."""

METADATA = {
    "name": "greeting",
    "priority": 5,
    "description": (
        "[greeting]\n"
        "User is opening a conversation with a social pleasantry — no task "
        "or question attached. Handler replies conversationally via "
        "qwen2.5:7b and skips Opus entirely.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"hi jane\"\n"
        "  - \"hey\"\n"
        "  - \"good morning\"\n"
        "  - \"hello there\"\n"
        "  - \"how's it going\"\n"
        "  - \"what's up\"\n"
        "  - \"yo\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'greeting' but ARE NOT:\n"
        "  - \"hi, set a 5 minute timer\" → 'timer' (greeting prefix + real task)\n"
        "  - \"hey, what's the weather\" → 'weather' (greeting prefix + real question)\n"
        "  - \"hi jane, tell Kathia I love her\" → 'send message' (greeting prefix + SMS)\n"
        "  - \"how does the greeting handler work\" → 'others' (meta / debug)\n"
        "  - \"ok thanks\" → 'end conversation' (sign-off, not a hello)"
    ),
    "few_shot": [],
    "ack": None,  # Greetings should get immediate response, no "thinking" ack
    "escalate_ack": None,
}
