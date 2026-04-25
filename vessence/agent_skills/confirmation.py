"""Yes/no confirmation parser for confirm-or-revise handlers.

Used by send_message and email handlers when prompting the user to
confirm a draft. Distinct from end_phrase.is_end():
  - is_yes("yes")        → True   (confirm and proceed)
  - is_no("no")          → True   (revise; NOT an end signal)
  - end_phrase.is_end("cancel") → True (abort the whole flow)

CONFIRM-OR-REVISE check order (do NOT reorder — see note below):
  1. is_yes(reply)              → execute the action + conversation_end
  2. is_no(reply)               → ask for revision
  3. end_phrase.is_end(reply)   → cancel + conversation_end
  4. else                       → abandon_pending + force_stage3

Why this order: "no" is in BOTH is_no's set (revise) AND end_phrase's set
(unambiguous closing — bare "no" answers "anything else?"-style prompts).
In a confirm-or-revise prompt ("Should I send it?"), "no" almost always
means "no, change it" not "no, abort". Checking is_no FIRST keeps that
intent. Users who actually want to abort say "cancel"/"nevermind"/"stop",
which are in end_phrase but not in is_no — so rule 3 still catches them.
"""

from __future__ import annotations

import re

_PUNCT_RE = re.compile(r"[^\w\s']")

_YES_PHRASES = frozenset({
    "yes",
    "yep",
    "yeah",
    "yup",
    "ya",
    "y",
    "sure",
    "ok",
    "okay",
    "go",
    "go ahead",
    "send",
    "send it",
    "do it",
    "confirm",
    "confirmed",
    "correct",
    "right",
    "yes please",
    "yep please",
})

_NO_PHRASES = frozenset({
    "no",
    "nope",
    "nah",
    "n",
    "wrong",
    "not quite",
    "not really",
    "not yet",
    "hold on",
    "wait",
    "let me revise",
    "revise",
    "change it",
    "redo",
})


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub("", text.strip().lower())


def is_yes(text: str | None) -> bool:
    if not text:
        return False
    return _normalize(text) in _YES_PHRASES


def is_no(text: str | None) -> bool:
    """True if user said no — meaning revise, NOT cancel.

    Note: 'no' is ambiguous between revise and end. In confirm-or-revise
    handlers, treat is_no as 'revise' (the more specific intent). True
    end-of-conversation should use a stronger phrase like 'cancel' or
    'nevermind' (see end_phrase.is_end).
    """
    if not text:
        return False
    return _normalize(text) in _NO_PHRASES
