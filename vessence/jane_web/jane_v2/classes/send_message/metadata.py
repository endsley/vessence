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
    "escalation_context": (
        "[send message escalation context]\n"
        "Contact resolution: search via GET /api/contacts/search?q=<name> to "
        "find phone numbers. Also check contact_aliases table for relational "
        "names (wife, mom, dad).\n\n"
        "Draft state: check vault_web.recent_turns:get_active_state for a "
        "pending_action of type SEND_MESSAGE_DRAFT_OPEN. If one exists, the "
        "user may be confirming, cancelling, or editing an existing draft.\n\n"
        "Sending: use sms_send_direct (not sms_draft flow) when in Stage 3. "
        "Format: [[CLIENT_TOOL:contacts.sms_send_direct:{\"phone_number\":\"<number>\","
        "\"body\":\"<message>\"}]]\n\n"
        "Perspective rewriting: the user speaks TO Jane ABOUT a third person. "
        "Rewrite the body so it reads from the user to the recipient:\n"
        "  - \"tell X I love her\" → body: \"I love you\"\n"
        "  - \"tell X she is beautiful\" → body: \"You are beautiful\"\n"
        "  - \"let mom know I'm on my way\" → body: \"I'm on my way\""
    ),
}
