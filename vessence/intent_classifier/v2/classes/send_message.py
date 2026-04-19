"""SEND_MESSAGE — text/SMS a person."""

CLASS_NAME = "SEND_MESSAGE"
NEEDS_LLM = True

EXAMPLES = [
    # Recipients AND bodies are stripped to placeholders ("x" = recipient,
    # "y" = body) so no specific name, relationship, or body phrase
    # acquires disproportionate embedding gravity. Diversity is STRUCTURAL
    # — the different send verbs and "saying/that/about/know" connectors —
    # not lexical. This also means narrative sentences like "my wife said
    # she loves me" don't land on any imperative body by accident.
    # Imperative send patterns
    "tell x that y",
    "message x",
    "message x that y",
    "message x about y",
    "text x",
    "text x that y",
    "text x for me",
    "let x know that y",
    "let x know y",
    "send a text to x",
    "send a message to x",
    "send x a text saying y",
    "send x a message saying y",
    "shoot a text to x",
    "can you text x",
    "can you tell x that y",
    # Continuation / confirmation to send (no recipient — short replies)
    "sounds good send it", "yeah send it", "go ahead and send it",
    "send it now", "ok send that", "please send that message",
    "yes send it", "send the message", "go ahead and text them",
]

CONTEXT = """\
The user wants to TEXT/SMS someone. Never call — SMS only.
Output exactly:
CLASSIFICATION: SEND_MESSAGE
RECIPIENT: <name as said — keep "wife", "mom", "Kathia" literal>
BODY: <message text only>
COHERENT: yes | no   (no = garbled/cut-off/random words)"""
