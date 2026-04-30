"""DELETE_EMAIL — delete/trash/dismiss email messages via Gmail.

Every example explicitly mentions email vocabulary (email/inbox/gmail/promo
mail/spam mail) so the chroma vote separates cleanly from DELETE_MESSAGES
(which guards on text/SMS/notification vocabulary). Generic "delete it"
phrasings are intentionally omitted — they would suck in any "delete X"
command. The handler escalates to Stage 3 anyway, so any borderline
phrasing routes through Opus regardless.

Mirror of DELETE_MESSAGES's structure, but for the Gmail surface.

Adversarial floor (acknowledged 2026-04-26, 21 chroma-only FPs out of 30 —
high but consistent with the DELETE_MESSAGES pattern): the remaining FPs
are shapes chroma (bag-of-words embedding) cannot disambiguate on its own:
  - Questions ("how do I delete an email on my phone",
    "what's the best way to clear my email inbox").
  - Past tense ("I already deleted that email", "I deleted the spam").
  - Negation ("don't delete the email from my doctor",
    "remind me not to delete the receipt email").
  - Adjacent-intent verbs that share email+spam vocabulary but a different
    action: unsubscribe, archive-but-not-delete, mark-as-spam, block-sender,
    report-phishing, search-my-email-for-X, forward-then-delete.
  - Account-level ("delete my gmail account", "deactivate my email account")
    — different scope from message deletion.
  - Contact deletion ("delete my contact for that email address") — wrong
    object, but chroma sees the email tokens.

These get caught downstream by:
  1. v3's qwen2.5:7b reranker, which sees the contrast cases listed in
     `jane_v2/classes/delete_email/metadata.py::description` (unsubscribe →
     others, archive → others, mark as read → others, etc.) and demotes /
     reroutes mismatched intents.
  2. The handler's escalation to Stage 3 — there is no Stage-2 handler for
     delete_email, so EVERY classification routes through Opus, who refuses
     or redirects on bad matches (e.g. past tense "I already deleted that"
     gets a contextual "Got it, anything else?" instead of a destructive
     action).
Comparable FP counts: read_email=17, music_play=16, delete_messages=14.
"""

CLASS_NAME = "DELETE_EMAIL"
NEEDS_LLM = True

EXAMPLES = [
    # Spam / promo deletion — must mention email/inbox/gmail
    "delete the spam emails", "delete those spam emails",
    "delete all the spam in my email",
    "trash the spam emails", "dismiss the spam mail",
    "get rid of the junk email", "delete the junk mail",
    "trash all the junk in my inbox",
    "clean up my spam folder",
    "empty my spam folder",
    "delete everything in spam",
    "trash everything in my spam folder",
    # Promotional email deletion
    "delete the promo emails", "trash the promotional emails",
    "delete the marketing emails", "get rid of the promo email",
    "trash the marketing junk in my inbox",
    "delete the promotional mail from x",
    "delete the promo email from x",
    "trash that promo email from x",
    "trash the macy's promo email",
    "delete that promo from best buy",
    "get rid of the marketing emails from x",
    # Sender-scoped email deletion
    "delete the email from x",
    "delete x's email",
    "trash the email from x",
    "remove the email from x",
    "get rid of the emails from x",
    "delete the latest email from x",
    "delete the last email from x",
    # Specific-email deletion
    "delete that email", "delete this email",
    "trash that email", "delete that one email",
    "get rid of that email",
    "delete the email about y",
    "trash the email about my package",
    "delete the email about the receipt",
    "delete the receipt email",
    # Inbox-wide / archive-style
    "clear out my email inbox",
    "delete all my unread emails",
    "wipe my email inbox",
    # Move-to-trash phrasings
    "move that email to trash",
    "move x's email to the trash",
    "send that email to trash",
    "archive the email from x",
]

CONTEXT = """\
The user wants to delete or trash email messages.
Output exactly:
CLASSIFICATION: DELETE_EMAIL
SCOPE: <spam | promotions | sender | specific | all_recent>
FILTER: <sender name if mentioned, else "none">"""
