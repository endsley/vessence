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
    "text x i'm coming soon",
    # Direct concrete phrasings — placeholders alone weren't winning votes for
    # short imperatives like "tell my wife" / "text Lee" (see 2026-04-23 audit:
    # "text Lee I'm running late" was matching READ_MESSAGES on every top-K
    # candidate). Anchoring with a few concrete recipients pulls these to
    # SEND_MESSAGE without overweighting any one name.
    "tell my wife",
    "tell my wife I love her",
    "tell my wife I'll be home soon",
    "text Lee",
    "text Lee I'm running late",
    "tell Lee",
    "tell Lee thanks",
    # Continuation / confirmation to send (no recipient — short replies)
    "sounds good send it", "yeah send it", "go ahead and send it",
    "send it now", "ok send that", "please send that message",
    "yes send it", "send the message", "go ahead and text them",
    # Proxy-send "tell/text/send X a joke/meme/funny thing" — these are
    # SMS to a third party (Lee, Kathia, mom), NOT a request for Jane to
    # tell the user a joke. The presence of a recipient name is what
    # pulls these to SEND_MESSAGE despite the joke/meme/funny words.
    "tell Lee a joke",
    "text Kathia the joke about the chicken",
    "send mom a funny meme",
    "tell Kathia a joke",
    "text Lee the joke I sent you",
    "send Lee something funny",
    "text Bob a meme",
]

CONTEXT = """\
The user wants to TEXT/SMS someone. Never call — SMS only.
Output exactly:
CLASSIFICATION: SEND_MESSAGE
RECIPIENT: <name as said — keep "wife", "mom", "Kathia" literal>
BODY: <message text only>
COHERENT: yes | no   (no = garbled/cut-off/random words)"""
