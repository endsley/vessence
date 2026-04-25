"""End-conversation phrase detection.

Strict matcher for phrases that mean the user wants to end the current
multi-turn flow. Used by handlers in the "repeating-read" pattern (todo,
weather) and the "confirm-or-revise" pattern (sms, email) to recognize
when the user is closing the conversation.

Strict by design: only catches unambiguous closings so we don't
accidentally end a flow when the user types "no" as a revise trigger
(see confirmation.is_no for that).
"""

from __future__ import annotations

import re

# Phrases that unambiguously mean "I'm done with this flow."
# Lowercased + punctuation-stripped before matching.
_END_PHRASES = frozenset({
    "no",
    "nope",
    "nah",
    "no thanks",
    "no thank you",
    "im done",
    "i am done",
    "that's all",
    "thats all",
    "that is all",
    "that's it",
    "thats it",
    "that is it",
    "stop",
    "end",
    "done",
    "cancel",
    "nevermind",
    "never mind",
    "forget it",
    "abort",
    "quit",
    "exit",
    "bye",
    "goodbye",
})

_PUNCT_RE = re.compile(r"[^\w\s']")


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub("", text.strip().lower())


def is_end(text: str | None) -> bool:
    """True if the user's reply is an unambiguous end-of-conversation phrase."""
    if not text:
        return False
    return _normalize(text) in _END_PHRASES
