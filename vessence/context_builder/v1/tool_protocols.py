"""Static client-tool protocol prompt sections for Jane context building."""

PHONE_TOOLS_PROTOCOL = (
    "## Phone Tools (Android only)\n"
    "Emit `[[CLIENT_TOOL:<name>:<json_args>]]` markers to invoke phone-side tools.\n"
    "The proxy strips markers from visible text. On web, phone tools are unavailable.\n\n"
    "### contacts.call\n"
    "`[[CLIENT_TOOL:contacts.call:{\"query\":\"Sarah\"}]]` — resolve relational names\n"
    "(my wife→Sarah) via personal facts. Keep visible text minimal.\n\n"
    "### SMS draft protocol (stateful multi-turn loop)\n"
    "Tools: `contacts.sms_draft` → `contacts.sms_draft_update` → `contacts.sms_send` / `contacts.sms_cancel`\n"
    "- One open draft at a time, 120s expiry\n"
    "- Each draft needs a fresh `draft_id`; reuse it on update/send/cancel\n"
    "- For indirect requests ('tell mom I'm safe'), compose the body yourself\n"
    "- Keep visible text MINIMAL — Android TTS reads the draft body aloud\n"
    "- sms_draft: emit marker only. sms_send: just 'Sent.' sms_draft_update: 'Updated.' + marker\n"
    "- User's next turn: approval→sms_send, edit→sms_draft_update (FULL new body), reject→sms_cancel\n"
    "- NEVER emit sms_send without a prior sms_draft. NEVER send without user approval.\n\n"
    "### messages.read_inbox (preferred for reading texts)\n"
    "Queries SMS database directly. Args: limit (default 20), sender (optional), since_ms (optional).\n"
    "`[[CLIENT_TOOL:messages.read_inbox:{\"sender\":\"Sarah\",\"limit\":10}]]`\n"
    "Results arrive via [PHONE TOOL RESULTS] on next turn. Triage: read personal messages,\n"
    "skip spam/promos/OTPs. Never invent content — quote only what's in the data.\n\n"
    "### messages.fetch_unread (active notifications only)\n"
    "Returns non-dismissed notification messages. Use when user asks specifically about NEW notifications.\n"
    "`[[CLIENT_TOOL:messages.fetch_unread:{\"limit\":20}]]`\n"
    "Prefer read_inbox unless user explicitly asks about unread notifications.\n\n"
    "### timer.set / timer.cancel / timer.list / timer.delete (alarm/reminder)\n"
    "Schedule exact alarms on the phone via AlarmManager — survives Doze, fires offline.\n"
    "`[[CLIENT_TOOL:timer.set:{\"duration_ms\":<int>,\"label\":\"<short>\"}]]`\n"
    "- duration_ms: milliseconds from now (3s = 3000, 5min = 300000, 2hr = 7200000)\n"
    "- label: short phrase the phone TTS speaks when it fires (e.g. \"pasta\", \"laundry\"); empty = generic \"time's up\"\n"
    "`[[CLIENT_TOOL:timer.cancel:{}]]` cancels ALL outstanding timers.\n"
    "`[[CLIENT_TOOL:timer.list:{}]]` returns remaining time for each running timer.\n"
    "`[[CLIENT_TOOL:timer.delete:{\"id\":N}]]` or `{\"index\":N}` or `{\"label\":\"pasta\"}` deletes one.\n"
    "If the user asks for an alarm/timer/reminder and you have a duration, emit timer.set.\n"
    "If duration is missing, ASK for it first and end with [[AWAITING:timer_duration]].\n\n"
    "### sync.force_sms (force message sync)\n"
    "Triggers a full re-sync of the last 14 days of SMS messages from the phone to the server.\n"
    "Use when the user says 'sync my messages', 'resync texts', 'refresh my messages', etc.\n"
    "`[[CLIENT_TOOL:sync.force_sms:{}]]`\n"
    "No args needed. Results arrive via [TOOL_RESULT] on next turn.\n\n"
    "### Tool result feedback\n"
    "Android prepends `[TOOL_RESULT:{json}]` to the next user turn. Statuses:\n"
    "completed→acknowledge, failed→explain, needs_user→ask clarifying question,\n"
    "unsupported→apologize, cancelled→don't re-emit.\n\n"
    "### Safety\n"
    "- Never emit tool markers when intent is ambiguous — ask first\n"
    "- Never include sensitive data (passwords, 2FA) in SMS unless user dictated it\n"
    "- Never emit more than one sms_draft per turn"
)

TOOL_CTX_SMS = (
    "## SMS Tool\n"
    "Emit `[[CLIENT_TOOL:<name>:<json_args>]]` markers. Proxy strips them from visible text.\n\n"
    "Tools: `contacts.sms_draft` → `contacts.sms_draft_update` → `contacts.sms_send` / `contacts.sms_cancel`\n"
    "- One draft at a time, 120s expiry. Each draft needs a fresh `draft_id`.\n"
    "- For indirect requests ('tell mom I'm safe'), compose the body yourself.\n"
    "- Resolve relational names (my wife→Sarah) via personal facts.\n"
    "- Keep visible text MINIMAL — Android TTS reads the draft body aloud.\n"
    "- sms_draft: just emit marker. sms_send: 'Sent.' sms_draft_update: 'Updated.' + marker.\n"
    "- NEVER send without user approval. NEVER emit sms_send without prior sms_draft.\n"
)

TOOL_CTX_CALL = (
    "## Call Tool\n"
    "Emit `[[CLIENT_TOOL:contacts.call:{\"query\":\"ContactName\"}]]` to place a call.\n"
    "Resolve relational names (my wife→Sarah) via personal facts. Keep text minimal.\n"
)

TOOL_CTX_READ_MESSAGES = (
    "## Read Messages\n"
    "Message data has been pre-fetched and included below. Triage: read personal messages,\n"
    "skip spam/promos/OTPs. Never invent content — quote only what's in the data.\n"
    "For specific sender queries, filter and quote only their messages.\n"
)

TOOL_CTX_READ_EMAIL = (
    "## Read Email\n"
    "Email data has been pre-fetched and included below. Summarize for the user:\n"
    "triage important vs spam, quote sender and subject for important ones.\n"
    "Never invent content — only reference what's in the data.\n"
)

CLASSIFICATION_TO_INTENT = {
    "self_handle": ("greeting", None),
    "read_messages": ("data_mode", TOOL_CTX_READ_MESSAGES),
    "read_email": ("data_mode", TOOL_CTX_READ_EMAIL),
    "sync_messages": ("data_mode", None),
    "music_play": ("data_mode", None),
    "delegate_opus": (None, None),
}
