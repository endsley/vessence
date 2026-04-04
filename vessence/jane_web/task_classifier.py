"""Classify whether a user message is a 'big task' that should be offloaded to background."""

import re

# Patterns that strongly suggest a big, multi-step task
_BIG_TASK_PATTERNS = [
    # Explicit imperative verbs for implementation work
    r"\b(?:implement|build|create|design|refactor|rewrite|migrate|overhaul|set up|wire up)\b",
    r"\b(?:add .{10,}(?:and|then|also|,))",  # "add X and Y" style compound tasks
    r"\b(?:fix .{10,}(?:and|then|also|,))",   # compound fix requests
    # Multi-step signals
    r"\b(?:step\s*\d|steps?\s*:)",
    r"\b(?:first|then|after that|finally|next)\b.*\b(?:then|after|finally|next)\b",
    # Numbered lists in the message (1. or 1) style)
    r"(?:^|\n)\s*\d+[\.\)]\s+\S",
    # Comma-separated action clauses ("do X, then Y, and Z")
    r"\b(?:and|then|,)\s+(?:write|add|update|fix|refactor|implement|create|build)\b",
    # File-heavy or code-heavy signals
    r"\b(?:across (?:all|every|the) (?:files?|modules?|components?|codebase|call\s*sites?))\b",
    r"\b(?:write tests?|add tests?|run tests?)\b.*\b(?:for|across|every)\b",
    # Long compound sentences with multiple verbs
    r"\b(?:update all|modify all|change all|replace all)\b",
]

# Patterns that suggest a quick query (answer, not action)
_QUICK_QUERY_PATTERNS = [
    r"^(?:what|how|why|when|where|who|which|can you explain|tell me|show me|describe)\b",
    r"^(?:is |are |do |does |did |was |were |has |have |should |would |could )\b",
    r"\?$",  # ends with question mark
]

# Minimum message length to even consider offloading
_MIN_LENGTH_FOR_OFFLOAD = 80

_big_re = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _BIG_TASK_PATTERNS]
_quick_re = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _QUICK_QUERY_PATTERNS]


def classify_task(message: str) -> str:
    """Return 'big' if the message looks like a multi-step implementation task, else 'quick'.

    This is a heuristic — it errs on the side of 'quick' (don't offload unless confident).
    Users can also force offload with an explicit prefix like 'background:' or 'bg:'.
    """
    if not message:
        return "quick"

    stripped = message.strip()

    # Explicit user signal: "background:" or "bg:" prefix
    if re.match(r"^(?:background|bg)\s*:\s*", stripped, re.IGNORECASE):
        return "big"

    # Too short to be a big task
    if len(stripped) < _MIN_LENGTH_FOR_OFFLOAD:
        return "quick"

    # Check for quick-query patterns first (questions are rarely big tasks)
    quick_score = sum(1 for r in _quick_re if r.search(stripped))
    if quick_score >= 2:
        return "quick"

    # Check for big-task patterns
    big_score = sum(1 for r in _big_re if r.search(stripped))

    # Compound signals: long message + multiple sentences + imperative verbs
    sentence_count = len(re.split(r'[.!]\s+', stripped))
    has_code_refs = bool(re.search(r'`[^`]+`|\.py|\.js|\.ts|\.html|\.css', stripped))

    if big_score >= 2:
        return "big"
    if big_score >= 1 and sentence_count >= 4:
        return "big"
    if big_score >= 1 and has_code_refs and len(stripped) > 200:
        return "big"

    return "quick"


def strip_bg_prefix(message: str) -> str:
    """Remove 'background:' or 'bg:' prefix if present."""
    return re.sub(r"^(?:background|bg)\s*:\s*", "", message.strip(), flags=re.IGNORECASE)
