"""Pure parsing helpers for the timer Stage 2 handler."""
from __future__ import annotations

import re


NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "forty-five": 45, "fifty": 50, "sixty": 60, "ninety": 90, "half": 0.5,
}

_HALF_HOUR_RE = re.compile(r"\bhalf\s+(?:an?\s+)?hour\b", re.I)
_AND_HALF_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:and\s*a\s*half|\.5)\s*(hour|hr)s?\b", re.I)
_NUM_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?|\b(?:a|an|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|eleven|twelve|fifteen|twenty|thirty|forty|forty-five|fifty|sixty|"
    r"ninety|half)\b)\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?|h|m|s)\b",
    re.I,
)


def unit_to_ms(value: float, unit: str) -> int:
    unit_name = unit.lower().rstrip("s")
    if unit_name in ("hour", "hr", "h"):
        return int(value * 3600 * 1000)
    if unit_name in ("minute", "min", "m"):
        return int(value * 60 * 1000)
    if unit_name in ("second", "sec", "s"):
        return int(value * 1000)
    return 0


def parse_duration_ms(text: str) -> int:
    """Best-effort duration parser. Returns 0 if nothing parses."""
    lowered = text.lower()

    if _HALF_HOUR_RE.search(lowered):
        return 30 * 60 * 1000

    match = _AND_HALF_RE.search(lowered)
    if match:
        return int((float(match.group(1)) + 0.5) * 3600 * 1000)

    total = 0
    for num_s, unit in _NUM_UNIT_RE.findall(lowered):
        try:
            num = float(num_s)
        except ValueError:
            num = float(NUM_WORDS.get(num_s.lower(), 0))
        total += unit_to_ms(num, unit)
    if total > 0:
        return total

    if re.search(r"\ban?\s+hour\b", lowered):
        return 3600 * 1000
    if re.search(r"\ban?\s+minute\b", lowered):
        return 60 * 1000

    return 0


def parse_followup_duration_ms(text: str) -> int:
    """Parse a timer follow-up duration, allowing bare numbers as minutes."""
    duration_ms = parse_duration_ms(text)
    if duration_ms > 0:
        return duration_ms

    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?|\w+)\s*", text.strip().lower())
    if not match:
        return 0
    token = match.group(1)
    try:
        minutes = float(token)
    except ValueError:
        minutes = float(NUM_WORDS.get(token, 0))
    if minutes <= 0:
        return 0
    return int(minutes * 60 * 1000)


def extract_label(prompt: str) -> str:
    """Grab a short label like 'pasta', 'oven', 'eggs' if mentioned."""
    cleaned = prompt.strip()
    match = re.search(
        r"\bfor\s+(?:the|my)\s+([a-z][a-z\s]{0,30}?)(?:\s+timer\b|[.!?,]|$)",
        cleaned,
        re.I,
    )
    if match:
        return match.group(1).strip()[:40]
    match = re.search(r"\bto\s+([a-z][a-z\s]{0,40}?)(?:[.!?,]|$)", cleaned, re.I)
    if match:
        return match.group(1).strip()[:40]
    match = re.search(
        r"\b\d+\s*(?:hour|hr|minute|min|second|sec)s?\s+([a-z]+)\s+timer\b",
        cleaned,
        re.I,
    )
    if match:
        return match.group(1).strip()[:40]
    return ""


def pretty_duration(ms: int) -> str:
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        base = f"{minutes} minute{'s' if minutes != 1 else ''}"
        return base if sec == 0 else f"{base} {sec} sec"
    hours, remaining_minutes = divmod(minutes, 60)
    if remaining_minutes == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return (
        f"{hours} hour{'s' if hours != 1 else ''} "
        f"{remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
    )


def extract_delete_target(prompt_lower: str) -> dict | None:
    """Detect delete-specific intent and extract which timer to delete."""
    if "timer" not in prompt_lower:
        return None
    verbs = ("delete", "remove", "drop", "get rid of", "scrap")
    if not any(verb in prompt_lower for verb in verbs):
        return None
    if any(word in prompt_lower for word in ("all my timers", "all the timers", "every timer", "all timers")):
        return None
    ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
                "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}
    match = re.search(r"\b(?:the\s+)?(\d+)(?:st|nd|rd|th)?\s*timer\b", prompt_lower)
    if match:
        return {"index": int(match.group(1))}
    match = re.search(r"\btimer\s+(?:number\s+|#)?(\d+)\b", prompt_lower)
    if match:
        return {"id": int(match.group(1))}
    for word, n in ordinals.items():
        if re.search(rf"\b(?:the\s+)?{word}\s+timer\b", prompt_lower):
            return {"index": n}
    match = re.search(
        r"\b(?:delete|remove|drop|scrap)\s+(?:the\s+|my\s+)?([a-z][a-z\s]{1,30}?)\s+timer\b",
        prompt_lower,
    )
    if match:
        label = match.group(1).strip()
        if label and label not in ("a", "an", "that", "this", "my", "the"):
            return {"label": label}
    return None


def parse_delete_phrase(phrase: str) -> dict | None:
    """Parse a `delete_target` phrase from params into the CLIENT_TOOL arg."""
    if not phrase:
        return None
    prompt = phrase.lower().strip()
    ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
                "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}
    match = re.search(r"\btimer\s+(?:number\s+|#)?(\d+)\b", prompt)
    if match:
        return {"id": int(match.group(1))}
    match = re.search(r"\b(?:the\s+)?(\d+)(?:st|nd|rd|th)?\s*timer\b", prompt)
    if match:
        return {"index": int(match.group(1))}
    for word, n in ordinals.items():
        if re.search(rf"\b(?:the\s+)?{word}(?:\s+timer)?\b", prompt):
            return {"index": n}
    match = re.search(
        r"\b(?:the\s+|my\s+)?([a-z][a-z\s]{1,30}?)(?:\s+timer)?$",
        prompt,
    )
    if match:
        label = match.group(1).strip()
        if label and label not in ("a", "an", "that", "this", "my", "the", "timer"):
            return {"label": label}
    return None


_NO_LABEL_REPLIES = {
    "no", "no label", "none", "skip", "nothing", "nope", "nah",
    "no thanks", "no thank you", "don't", "dont", "without a label",
    "without label", "i don't want one", "i don't want a label",
    "just set it", "leave it", "blank",
}


def label_from_reply(prompt: str) -> str:
    """Extract a clean label from a follow-up reply. '' means 'no label'."""
    cleaned = prompt.strip()
    if cleaned.lower().strip(".!?,") in _NO_LABEL_REPLIES:
        return ""
    for pattern in (
        r"^(?:call\s+it|label\s+it|name\s+it|its\s+called|it's\s+called|the\s+label\s+(?:is|should\s+be)|label:)\s+",
        r"^(?:let's\s+call\s+it\s+|i'd\s+call\s+it\s+|how\s+about\s+)",
    ):
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+(?:please|thanks|thank\s+you)\s*[.!?]?\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.rstrip(".!?,").strip()
    return cleaned[:60]


def looks_like_new_timer(prompt: str) -> bool:
    """True if prompt looks like a brand-new timer request during a follow-up."""
    lowered = prompt.lower()
    if parse_duration_ms(prompt) > 0:
        new_timer_signals = ("set ", "start ", "another timer", "new timer",
                             "timer for ", "create ", "make ")
        return any(signal in lowered for signal in new_timer_signals)
    return False
