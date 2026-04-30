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
    # "email X about deleting/removing/cleaning Y" — the topic of the email
    # mentions deletion but the imperative is SEND, not delete. Without these
    # exemplars the chroma vote pulls them into DELETE_EMAIL on the "email"
    # + "delete" trigger overlap.
    "email x about deleting y",
    "email x about removing y",
    "email x a list of y to delete",
    "send x an email about cleaning up y",
    "draft an email to x about deleting y",
    # Meeting / scheduling topics. Without these, "email Bob about
    # tomorrow's meeting" pulls toward DELEGATE_OPUS ("add a meeting
    # tomorrow") and TIMER on the bge-small embedding because the
    # meeting/time tokens dominate.
    "email x about the meeting",
    "email x about tomorrow's meeting",
    "email x about the y meeting",
    "email x about the meeting at y",
    "email x about the schedule",
    "send x an email about the meeting",
    "draft an email to x about the meeting",
    "email x about y at y", "email x about scheduling y",
    # NOTE: delete/archive/trash imperatives live in DELETE_EMAIL — keeping
    # them here would pull email-deletion intents into the send class and
    # waste a draft turn before Opus rerouted.
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
