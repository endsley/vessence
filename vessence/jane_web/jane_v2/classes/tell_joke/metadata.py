"""Tell joke class — user wants Jane to tell a single joke."""

METADATA = {
    "name": "tell joke",
    "priority": 12,
    "description": (
        "[tell joke]\n"
        "User explicitly asks Jane to tell a joke. Handler generates one "
        "short clean joke via the local LLM and returns it. No Opus, no "
        "client tools — just the joke text spoken by TTS.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"tell me a joke\"\n"
        "  - \"say something funny\"\n"
        "  - \"make me laugh\"\n"
        "  - \"got any jokes\"\n"
        "  - \"another joke\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'tell joke' but ARE NOT:\n"
        "  - \"tell Lee a joke\" → 'send message' (proxy SMS to a person)\n"
        "  - \"email Bob a joke\" → 'send email' (proxy email)\n"
        "  - \"what is a joke\" / \"who wrote that joke\" → 'others' (meta question)\n"
        "  - \"this meeting is a joke\" → 'others' (figurative complaint)\n"
        "  - \"no jokes please\" / \"stop with the jokes\" → 'end conversation' (decline)\n"
        "  - \"that's hilarious\" / \"that was actually funny\" → 'others' (reaction)"
    ),
    "few_shot": [
        ("tell me a joke", "tell joke:High"),
        ("got any jokes", "tell joke:High"),
        ("make me laugh", "tell joke:High"),
    ],
    "ack": None,
    "escalate_ack": None,
}
