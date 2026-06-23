"""Send email class — compose / send email via Gmail API.

Always escalates to Stage 3 by design. Email work tends to be complicated:
recipient resolution from a name, subject inference, perspective rewriting
('tell Bob I'm late' → 'I'm running late'), and confirmation flows where
the user edits drafts mid-air. qwen2.5:7b can't hold that conversation
reliably, so Opus owns it end-to-end.

Output: Opus drafts, reads back, gets explicit user confirmation, THEN
emits `[[CLIENT_TOOL:email.send:{"from_email":"...","to":"...","subject":"...","body":"..."}]]`
which jane_proxy intercepts and executes server-side via
`agent_skills.email_tools.send_email`. The marker = "send now"; by the time
it arrives the user has already said yes.

Until 2026-04-26 a Stage-2 handler did the draft/confirm flow locally; that
handler was removed when the user asked for all email to skip Stage 2.
"""

import datetime
import logging

_logger = logging.getLogger(__name__)


def _format_email_block(label: str, emails: list[dict]) -> str:
    if not emails:
        return f"{label}\nNone.\n[END]"
    lines = [label]
    for i, e in enumerate(emails, 1):
        sender = (e.get("sender") or "Unknown")[:80]
        subject = (e.get("subject") or "(no subject)")[:120]
        when = (e.get("date") or "").strip()[:40]
        lines.append(f"{i}. [{when}] {sender}")
        lines.append(f"   Subject: {subject}")
    lines.append("[END]")
    return "\n".join(lines)


def _escalation_context() -> str:
    """Inject recent inbox so Opus has context for replies / threading,
    plus the rules of engagement for sending."""
    try:
        from agent_skills.email_oauth import list_gmail_token_users
        accounts = list_gmail_token_users()
    except Exception:
        accounts = []
    account_line = (
        ", ".join(accounts)
        if accounts
        else "no stored Gmail sender tokens yet"
    )

    rules = (
        "[send email escalation context]\n"
        "\n"
        'Tool: [[CLIENT_TOOL:email.send:{"from_email":"<sender>","to":"<addr>","subject":"<subj>","body":"<body>"}]]\n'
        f"  - Available sender accounts: {account_line}.\n"
        "  - from_email: use the Gmail account the user explicitly requested "
        "(for example chieh.t.wu@gmail.com or juliaprocess@gmail.com). If the "
        "user did not specify a sender, omit from_email or use null so the "
        "server uses the default Gmail account.\n"
        "  - to: a real email address. If the user only gave a name, "
        "resolve it (search recent inbox below, ask the user, or skip).\n"
        "  - subject: infer from the body if the user didn't dictate one.\n"
        "  - body: in first person from the user's voice. Rewrite "
        "perspective ('tell Bob I'm late' → 'I'm running late').\n"
        "  - Server moves the message via the Gmail API — no Android relay.\n"
        "\n"
        "Workflow:\n"
        "  1. Draft the email in your reply, read it back with the sender: "
        "'Email from <sender or default Gmail account> to <addr>, subject "
        "\"<subj>\", body \"<body>\". Want me to send it?'\n"
        "  2. WAIT for an explicit yes on the next turn — never emit the "
        "marker until the user confirms.\n"
        "  3. On 'yes' / 'send it' / 'go ahead' — emit the CLIENT_TOOL "
        "marker and reply 'Sent.'\n"
        "  4. On 'no' / 'cancel' — drop the draft, reply 'Cancelled.'\n"
        "  5. On edits ('make it shorter', 'change the subject to X') — "
        "redraft and read back again.\n"
        "\n"
        "NEVER guess a recipient address. If the user gave only a name "
        "and there is no match in the inbox below, ask: 'What's <name>'s "
        "email address?'\n"
        "NEVER guess a non-default sender. If the user asks to send from a "
        "Gmail account that is not listed above, explain that they need to "
        "sign in with that Google account first.\n"
    )

    try:
        from agent_skills.email_tools import read_inbox
    except Exception as e:
        return f"{rules}\n[EMAIL ERROR]\nEmail tools failed to import: {e}\n[END]"

    try:
        recent = read_inbox(limit=15, query="")
        block = _format_email_block(
            "[EMAIL INBOX — recent (for recipient lookup / threading)]",
            recent,
        )
    except RuntimeError as e:
        block = (
            "[EMAIL ERROR]\n"
            f"Gmail not set up: {e}\n"
            "Tell the user they need to sign in with Google on the Vessence "
            "web UI to enable email access.\n[END]"
        )
    except Exception as e:
        _logger.warning("send_email escalation: recent fetch failed: %s", e)
        block = f"[EMAIL INBOX — recent]\nFetch failed: {e}\n[END]"

    footer = (
        f"(Fetched at {datetime.datetime.utcnow().isoformat()}Z. "
        "Use this only as a recipient/address lookup. Do NOT quote inbox "
        "contents to the user unless they asked.)"
    )

    return f"{rules}\n{block}\n\n{footer}"


PARAMS_SCHEMA = {
    "to": (
        "string|null — recipient name or email address as the user said it "
        "('Bob', 'alice@example.com', 'my accountant'). Opus resolves names "
        "to addresses. Null means user didn't specify a recipient."
    ),
    "subject": (
        "string|null — explicit subject if the user dictated one. Usually null; "
        "Opus infers from the body when missing."
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
        "User wants to SEND email via their Gmail account. Opus drafts, "
        "reads back, waits for explicit confirmation, then emits "
        "[[CLIENT_TOOL:email.send:{...}]]. Server intercepts and sends via "
        "Gmail API.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"email Bob about tomorrow's meeting\"\n"
        "  - \"send an email to alice@example.com saying I'm running late\"\n"
        "  - \"draft an email to my accountant about the Q3 taxes\"\n"
        "  - \"email Sarah thanking her for dinner\"\n"
        "  - \"shoot a quick email to the team about the outage\"\n\n"
        "Also YES mid-flow during an active email draft: \"yes send it\", "
        "\"cancel\", \"change the subject to X\", \"make it shorter\" — those "
        "are confirmations / edits within this flow.\n\n"
        "Adversarial phrasings that LOOK LIKE 'send email' but ARE NOT:\n"
        "  - \"check my email\" → 'read email' (reading, not sending)\n"
        "  - \"any new emails\" → 'read email'\n"
        "  - \"delete that email\" → 'delete email' (trash, not send)\n"
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
    "escalation_context": _escalation_context,
}
