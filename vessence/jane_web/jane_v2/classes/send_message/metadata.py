"""Send message class — text/SMS someone."""

PARAMS_SCHEMA = {
    "recipient": (
        "string|null — name or relational alias as the user said it "
        "('Kathia', 'my wife', 'mom'). Handler resolves to a phone number "
        "via contacts/aliases. Null when the user didn't name a recipient."
    ),
    "body": (
        "string|null — the SMS body in the user's voice (FROM the user TO "
        "the recipient). Rewrite perspective: 'tell X I love her' → 'I love "
        "you'; 'let mom know I'm on my way' → 'I'm on my way'; 'ask X what "
        "time' → 'What time are you coming?'. Null when no message content given."
    ),
    "intent_kind": (
        "enum REQUIRED — one of: send | ask. "
        "send = order to deliver a statement (fast-path eligible). "
        "ask = the message is a question to the recipient (use draft + "
        "confirm path because phrasing/timing matters more)."
    ),
    "confirm_signal": (
        "enum|null — for follow-up turns confirming/cancelling an open draft. "
        "One of: send | cancel | edit. Null on fresh requests."
    ),
}


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
    "params_schema": PARAMS_SCHEMA,
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
        "Two send paths (pick ONE per turn):\n"
        "  (a) Direct send (user clearly ordered a send, body unambiguous): emit\n"
        "      [[CLIENT_TOOL:contacts.sms_send_direct:{\"phone_number\":\"<number>\","
        "\"body\":\"<message>\"}]] and reply \"Sent to <name>.\" No confirmation "
        "loop — user already confirmed by phrasing it as an order.\n"
        "  (b) Draft + confirm (user asked you to ASK someone something, or intent "
        "was softer): emit [[CLIENT_TOOL:contacts.sms_draft:{\"phone_number\":"
        "\"<number>\",\"body\":\"<message>\"}]]. In the visible text, read the "
        "draft back AND explicitly end with \"Are you ready to send this message?\" "
        "so the user knows the message has NOT been sent yet. The server "
        "auto-creates a SEND_MESSAGE_DRAFT_OPEN pending_action; when the user "
        "replies \"yes send it\" the resolver fires sms_send.\n"
        "  Example draft read-back: 'To Lee: \"What time will you be there today?\" "
        "Are you ready to send this message?'\n\n"
        "Never emit `]]` in visible text outside of a CLIENT_TOOL marker — "
        "stray `]]` leaks through the strip logic and lands in the user's chat.\n\n"
        "Perspective rewriting: the user speaks TO Jane ABOUT a third person. "
        "Rewrite the body so it reads from the user to the recipient:\n"
        "  - \"tell X I love her\" → body: \"I love you\"\n"
        "  - \"tell X she is beautiful\" → body: \"You are beautiful\"\n"
        "  - \"let mom know I'm on my way\" → body: \"I'm on my way\"\n"
        "  - \"ask X what time she's coming\" → body: \"What time are you coming?\" "
        "(use draft path (b) since this is a question-draft, not a send-and-forget)"
    ),
}
