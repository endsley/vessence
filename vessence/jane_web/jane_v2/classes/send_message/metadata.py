"""Send message class — text/SMS someone."""

METADATA = {
    "name": "send message",
    "priority": 10,
    "description": (
        "[send message]\n"
        "User wants to send an SMS / text message to another person. Jane "
        "resolves the recipient against contacts/aliases, then either "
        "sends immediately (CLIENT_TOOL:contacts.sms_send_direct) or "
        "escalates to Opus for disambiguation / draft-confirm when the "
        "recipient is ambiguous or the body is garbled.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"tell my wife I'll be 20 minutes late\"\n"
        "  - \"text Kathia that I love her\"\n"
        "  - \"send Sarah a message saying I'm running late\"\n"
        "  - \"let mom know I got home safe\"\n"
        "  - \"message John about tomorrow's meeting\"\n"
        "  - \"shoot Dave a text\"\n\n"
        "Also YES mid-flow during an active SMS draft: \"yes send it\", "
        "\"cancel\", \"make it shorter\", \"change it to say X\" — those "
        "are confirmations / edits within this flow, not new intents.\n\n"
        "Adversarial phrasings that LOOK LIKE 'send message' but ARE NOT:\n"
        "  - \"call my wife\" → 'others' (phone call, NOT SMS)\n"
        "  - \"phone John\" → 'others' (phone call)\n"
        "  - \"send an email to Bob\" → 'others' (email, not SMS)\n"
        "  - \"what did my wife text me\" → 'read messages' (reading incoming, not sending)\n"
        "  - \"read my latest texts\" → 'read messages'\n"
        "  - \"sync my messages\" → 'sync messages' (force-refresh, not send)\n"
        "  - \"tell me a story\" → 'others' (storytelling, nothing to send)"
    ),
    "few_shot": [],
    "ack": None,  # Stage 2 fast-path is quick enough — no interim ack needed
    "escalate_ack": "Let me draft that message…",
}
