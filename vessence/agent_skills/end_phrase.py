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

from agent_skills.phrase_matcher import (
    PUNCT_RE as _PUNCT_RE,
    normalize_phrase as _normalize,
    phrase_in_set as _phrase_in_set,
)

# Phrases that unambiguously mean "I'm done with this flow."
# Lowercased + punctuation-stripped before matching.
_END_PHRASES = frozenset({
    "no",
    "nope",
    "nah",
    "no thanks",
    "no thank you",
    "no i'm good",
    "no im good",
    "i'm good",
    "im good",
    "i am good",
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

def is_end(text: str | None) -> bool:
    """True if the user's reply is an unambiguous end-of-conversation phrase."""
    return _phrase_in_set(text, _END_PHRASES)
