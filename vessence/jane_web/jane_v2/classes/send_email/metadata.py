"""Send email class — compose / send / delete email via Gmail API."""

PARAMS_SCHEMA = {
    "to": (
        "string|null — recipient name or email address as the user said it "
        "('Bob', 'alice@example.com', 'my accountant'). Handler resolves names "
        "to addresses. Null means user didn't specify a recipient."
    ),
    "subject": (
        "string|null — explicit subject if the user dictated one. Usually null; "
        "handler infers from the body when missing."
    ),
    "body": (
        "string|null — the message content the user wants sent, in their voice. "
        "Rewrite from third person to first person ('tell Bob I'm late' → "
        "'I'm running late'). Null when the user only named a recipient and "
        "intent without dictating content."
    ),
    "confirm_signal": (
        "enum|null — for follow-up turns confirming/cancelling an open draft. "
        "One of: send | cancel | edit. Null when this is a fresh request, not "
        "a draft response."
    ),
}


METADATA = {
    "name": "send email",
    "priority": 10,
    "description": (
        "[send email]\n"
        "User wants to SEND (or delete) email via their Gmail account. "
        "Handler extracts {to, subject, body} from the user prompt with a "
        "local LLM, reads the draft back, and waits for explicit "
        "confirmation before calling the Gmail API server-side. No CLIENT_TOOL "
        "marker — email is server-side only (not phone-relayed).\n\n"
        "Example phrasings the user might say:\n"
        "  - \"email Bob about tomorrow's meeting\"\n"
        "  - \"send an email to alice@example.com saying I'm running late\"\n"
        "  - \"draft an email to my accountant about the Q3 taxes\"\n"
        "  - \"email Sarah thanking her for dinner\"\n"
        "  - \"shoot a quick email to the team about the outage\"\n"
        "  - \"delete that spam email\" (escalates to Opus — needs message_id)\n"
        "  - \"archive the email from John\" (escalates — needs search + action)\n\n"
        "Also YES mid-flow during an active email draft: \"yes send it\", "
        "\"cancel\", \"change the subject to X\", \"make it shorter\" — those "
        "are confirmations / edits within this flow.\n\n"
        "Adversarial phrasings that LOOK LIKE 'send email' but ARE NOT:\n"
        "  - \"check my email\" → 'read email' (reading, not sending)\n"
        "  - \"any new emails\" → 'read email'\n"
        "  - \"text my wife\" → 'send message' (SMS, not email)\n"
        "  - \"email me the list\" → 'others' (meta: Jane is NOT a recipient)\n"
        "  - \"how does the email tool work\" → 'others' (meta question)"
    ),
    "params_schema": PARAMS_SCHEMA,
    "few_shot": [
        ("email Bob about the Q3 report", "send email:High"),
        ("send an email to alice@example.com saying I'll be late", "send email:High"),
        ("draft an email to my accountant about taxes", "send email:High"),
        ("shoot john a quick email", "send email:High"),
    ],
    "ack": None,
    "escalate_ack": "Let me draft that email…",
    "escalation_context": (
        "[send email escalation context]\n"
        "The full Gmail toolkit is at agent_skills/email_tools.py. Functions: "
        "send_email(to, subject, body), delete_email(message_id), "
        "search_emails(query, limit), read_inbox(limit, query), "
        "read_email(message_id). OAuth refresh is automatic via "
        "agent_skills/email_oauth.refresh_token_if_needed.\n\n"
        "Draft state: check vault_web.recent_turns:get_active_state for a "
        "pending_action with type=EMAIL_DRAFT_OPEN. If present and the user "
        "confirms, call email_tools.send_email() and report 'Sent.'. If the "
        "user asks for an edit, update the draft and read back again.\n\n"
        "Never send an email without explicit user confirmation. Never guess a "
        "recipient address — if only a name is given, ask the user or search "
        "their recent emails for the right To: address."
    ),
}
