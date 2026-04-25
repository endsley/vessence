"""SEND_EMAIL — compose and send an email via Gmail."""

CLASS_NAME = "SEND_EMAIL"
NEEDS_LLM = True

EXAMPLES = [
    # Imperative send patterns. Recipients and bodies are generic placeholders
    # ("x" = recipient, "y" = subject/body fragment) so no specific name or
    # phrase acquires disproportionate embedding gravity. Diversity is
    # STRUCTURAL — different send verbs, connectors, and the word "email".
    "email x about y",
    "email x",
    "email x saying y",
    "email x that y",
    "send an email to x",
    "send an email to x about y",
    "send an email to x saying y",
    "send x an email",
    "draft an email to x",
    "draft an email to x about y",
    "compose an email to x",
    "write an email to x about y",
    "shoot an email to x",
    "shoot x a quick email",
    "can you email x",
    "can you send an email to x",
    "let x know via email that y",
    # Delete / manage — same class because Opus handles the action after
    # Stage 2's draft-confirm flow.
    "delete that email",
    "delete the email from x",
    "archive the email from x",
    "move x's email to the trash",
    # Bare confirmations — match send_message's pattern. Mid-flow edit/cancel
    # verbs are NOT listed here: they're handled by the pending_action_resolver
    # when an EMAIL_DRAFT_OPEN is active, and adding them to chroma created
    # false positives on unrelated phrases like "forget about the email".
    "yes send it",
    "send it",
    "go ahead and send",
    "confirm and send",
    # Proxy-send "email X a joke/meme/funny thing" — third-party email,
    # NOT a request for Jane to tell the user a joke.
    "email Bob a joke for his birthday",
    "email Lee a funny story",
    "email mom a meme",
]
