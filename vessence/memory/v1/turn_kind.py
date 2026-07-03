"""Heuristic turn-kind classifier for short-term memory extraction."""
from __future__ import annotations

import re


# Order matters: more specific patterns first.
TURN_KIND_PATTERNS: list[tuple[str, list[re.Pattern]]] = [
    ("calendar", [
        re.compile(r"\b(calendar|appointment|schedul|meeting|reschedul|book(ing)?|"
                   r"event|reminder)\b", re.I),
        re.compile(r"\[CALENDAR DATA\]"),
    ]),
    ("messages", [
        re.compile(r"\b(text|message|sms|reply|email|msg sent)\b", re.I),
        re.compile(r"\b(tell (?:my |her |him )?\w+|let \w+ know)\b", re.I),
        re.compile(r"\[\[CLIENT_TOOL:(?:contacts\.sms|messages\.|email\.)"),
        re.compile(r"\[EMAIL INBOX DATA\]"),
    ]),
    ("todo", [
        re.compile(r"\b(todo|task list|to[- ]do|grocery|shopping list|reminder list)\b", re.I),
        re.compile(r"\[\[CLIENT_TOOL:todo\."),
    ]),
    ("debugging", [
        re.compile(r"\b(error|crash|stack trace|traceback|exception|bug|broke|broken|"
                   r"failing|fix(ing)? the (bug|crash|error)|root cause|regression)\b", re.I),
    ]),
    ("code", [
        re.compile(r"`[^`\n]{2,}`"),
        re.compile(r"```"),
        re.compile(r"\b(?:function|class|method|module|import|patch|refactor|"
                   r"deploy|commit|merge|alembic|migration)\b", re.I),
        re.compile(r"\.(?:py|js|ts|html|css|sh|json|yaml|toml|md|tsx|jsx)\b"),
        re.compile(r"/[a-z_][a-z0-9_/]*\.[a-z]+", re.I),
    ]),
]


def classify_turn_kind(text: str) -> str:
    """Pick the turn kind with highest pattern hit count, or general."""
    if not text:
        return "general"
    sample = text[:4000]
    best_kind, best_score = "general", 0
    for kind, patterns in TURN_KIND_PATTERNS:
        score = sum(1 for pattern in patterns if pattern.search(sample))
        if score > best_score:
            best_kind, best_score = kind, score
    return best_kind
