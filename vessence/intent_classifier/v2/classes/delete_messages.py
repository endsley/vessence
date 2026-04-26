"""DELETE_MESSAGES — delete/dismiss SMS messages and notifications.

Every example explicitly mentions text/message/SMS/notification vocabulary.
Generic phrases ("delete them", "yes do it") are intentionally omitted —
they would pull any "delete X" command into this class. The handler
escalates to Stage 3 anyway, so missing a few generic phrasings is fine;
Opus will route them via the broader delegate_opus path.

Adversarial floor (acknowledged 2026-04-25, 14 chroma-only FPs out of 30):
the remaining FPs are shapes chroma (bag-of-words embedding) cannot
disambiguate on its own — questions ("how do I delete texts on android"),
past tense ("I already deleted those"), negation ("don't delete texts
from mom"), and trigger-word collisions in domains with no competing
class ("delete that contact", "delete my whole account", "trash that
note"). These get caught downstream by:
  1. v3's qwen2.5:7b reranker, which sees the description's contrast
     cases in metadata.py and demotes / reroutes mismatched intents.
  2. The handler's escalation to Stage 3 — Opus owns final routing and
     will refuse / redirect (e.g. "I can't delete a contact, only texts").
Comparable FP counts: read_email=17, music_play=16, read_messages=7.
"""

CLASS_NAME = "DELETE_MESSAGES"
NEEDS_LLM = True

EXAMPLES = [
    # Spam / promo deletion — must mention texts/messages/SMS
    "delete the spam texts", "delete those spam texts",
    "delete the spam text messages",
    "get rid of the spam text messages", "dismiss the spam texts",
    "delete the promo text", "delete the promo text messages",
    "get rid of the promo texts", "remove the marketing texts",
    "delete the texts from that 5 digit number",
    "dismiss the SMS from that short code",
    # Sender-scoped deletion
    "delete the messages from x", "delete texts from x",
    "remove the text messages from x", "get rid of x's texts",
    "dismiss the texts from x", "clear the texts from x",
    "delete the last text from x", "delete the latest text from x",
    "remove that text message from x",
    "delete the texts from x about y",
    # Specific-message deletion (always with text/message/SMS noun)
    "delete that text message", "delete that SMS",
    "delete the package text", "remove the delivery text",
    "get rid of that one text",
    "delete the text about my package",
    "dismiss the text message notification",
    "dismiss those text messages",
    # Inbox-wide
    "clear out my text inbox", "delete all my texts",
    "wipe my text messages", "clear my SMS inbox",
    "delete all the unread texts",
    "delete the spam from my text inbox",
    # Notification shade — explicitly text/SMS notifications
    "dismiss the text message notifications",
    "clear the SMS notifications from the shade",
    "get rid of the text message notifications",
]

CONTEXT = """\
The user wants to delete or dismiss text messages / SMS / notifications.
Output exactly:
CLASSIFICATION: DELETE_MESSAGES
SCOPE: <spam | sender | specific | all_recent>
FILTER: <sender name if mentioned, else "none">"""
