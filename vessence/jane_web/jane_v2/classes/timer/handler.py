"""Timer Stage 2 handler.

Handles three actions entirely on the Android client via CLIENT_TOOL markers:
  - set    → [[CLIENT_TOOL:timer.set:{"duration_ms": <ms>, "label": "..."}]]
  - cancel → [[CLIENT_TOOL:timer.cancel:{}]]
  - list   → [[CLIENT_TOOL:timer.list:{}]]

The server keeps NO state. The phone owns every timer via AlarmManager
so alarms ring even when offline. The handler's only job is to parse the
user's phrasing, pick the action + duration, and emit the marker.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# ── action detection ─────────────────────────────────────────────────────────
_CANCEL_WORDS = ("cancel", "stop", "kill", "turn off", "clear", "never mind",
                 "nevermind", "forget the timer", "abort")
_LIST_WORDS = ("what timers", "list", "show my timer", "show me my timer",
               "any timers", "how much time", "how long", "time remaining",
               "time left", "what's on my timer", "do i have any timer",
               "check my timer")

# ── duration parsing ─────────────────────────────────────────────────────────
_NUM_WORDS = {
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


def _unit_to_ms(value: float, unit: str) -> int:
    u = unit.lower().rstrip("s")
    if u in ("hour", "hr", "h"):
        return int(value * 3600 * 1000)
    if u in ("minute", "min", "m"):
        return int(value * 60 * 1000)
    if u in ("second", "sec", "s"):
        return int(value * 1000)
    return 0


def _parse_duration_ms(text: str) -> int:
    """Best-effort duration parser. Returns 0 if nothing parses."""
    t = text.lower()

    # "half an hour" / "half hour"
    if _HALF_HOUR_RE.search(t):
        return 30 * 60 * 1000

    # "2 and a half hours" / "1.5 hours"
    m = _AND_HALF_RE.search(t)
    if m:
        return int((float(m.group(1)) + 0.5) * 3600 * 1000)

    # First <num> <unit> match; also sum multiple (e.g. "1 hour 30 minutes")
    total = 0
    for num_s, unit in _NUM_UNIT_RE.findall(t):
        try:
            num = float(num_s)
        except ValueError:
            num = float(_NUM_WORDS.get(num_s.lower(), 0))
        total += _unit_to_ms(num, unit)
    if total > 0:
        return total

    # Bare "an hour" / "a minute"
    if re.search(r"\ban?\s+hour\b", t):
        return 3600 * 1000
    if re.search(r"\ban?\s+minute\b", t):
        return 60 * 1000

    return 0


def _extract_label(prompt: str) -> str:
    """Grab a short label like 'pasta', 'oven', 'eggs' if mentioned.

    Heuristic: phrases after "for the", "for my", or "to <verb>" are labels.
    """
    p = prompt.strip()
    m = re.search(r"\bfor\s+(?:the|my)\s+([a-z][a-z\s]{0,30}?)(?:\s+timer\b|[.!?,]|$)",
                  p, re.I)
    if m:
        return m.group(1).strip()[:40]
    m = re.search(r"\bto\s+([a-z][a-z\s]{0,40}?)(?:[.!?,]|$)", p, re.I)
    if m:
        return m.group(1).strip()[:40]
    # "5 minute pizza timer" / "20 minute pasta timer"
    m = re.search(r"\b\d+\s*(?:hour|hr|minute|min|second|sec)s?\s+([a-z]+)\s+timer\b",
                  p, re.I)
    if m:
        return m.group(1).strip()[:40]
    return ""


def _pretty_duration(ms: int) -> str:
    s = ms // 1000
    if s < 60:
        return f"{s} second{'s' if s != 1 else ''}"
    m, sec = divmod(s, 60)
    if m < 60:
        base = f"{m} minute{'s' if m != 1 else ''}"
        return base if sec == 0 else f"{base} {sec} sec"
    h, mm = divmod(m, 60)
    if mm == 0:
        return f"{h} hour{'s' if h != 1 else ''}"
    return f"{h} hour{'s' if h != 1 else ''} {mm} minute{'s' if mm != 1 else ''}"


def _extract_delete_target(p_lower: str) -> dict | None:
    """Detect delete-specific intent and extract which timer to delete.

    Returns {"id": N} or {"index": N} or {"label": "pasta"} or None.
    Only fires for ONE specific timer — plural/all falls through to CANCEL.
    """
    if "timer" not in p_lower:
        return None
    verbs = ("delete", "remove", "drop", "get rid of", "scrap")
    if not any(v in p_lower for v in verbs):
        return None
    # "all my timers" / "every timer" → let CANCEL-ALL handle it
    if any(w in p_lower for w in ("all my timers", "all the timers", "every timer",
                                   "all timers")):
        return None
    # "delete the 3rd timer" / "delete timer 3" / "delete the third timer"
    ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
                "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}
    m = re.search(r"\b(?:the\s+)?(\d+)(?:st|nd|rd|th)?\s*timer\b", p_lower)
    if m:
        return {"index": int(m.group(1))}
    m = re.search(r"\btimer\s+(?:number\s+|#)?(\d+)\b", p_lower)
    if m:
        return {"id": int(m.group(1))}
    for word, n in ordinals.items():
        if re.search(rf"\b(?:the\s+)?{word}\s+timer\b", p_lower):
            return {"index": n}
    # "delete the pasta timer" / "delete my oven timer"
    m = re.search(r"\b(?:delete|remove|drop|scrap)\s+(?:the\s+|my\s+)?([a-z][a-z\s]{1,30}?)\s+timer\b",
                  p_lower)
    if m:
        label = m.group(1).strip()
        if label and label not in ("a", "an", "that", "this", "my", "the"):
            return {"label": label}
    return None


_COUNT_PHRASES = (
    "how many timers", "how many timer",
    "number of timers", "count my timers", "count of timers",
)


def handle(prompt: str) -> dict | None:
    p_lower = prompt.lower()

    # COUNT / QUERY — "how many timers do I have"
    # timer.list already returns a count-friendly summary on Android.
    if any(p in p_lower for p in _COUNT_PHRASES):
        marker = "[[CLIENT_TOOL:timer.list:{}]]"
        logger.info("timer handler: count query")
        return {
            "text": f"Let me check. {marker}",
            "structured": {"intent": "timer",
                           "entities": {"action": "count"}},
        }

    # DELETE specific timer (by id / index / label)
    target = _extract_delete_target(p_lower)
    if target is not None:
        tool_args = json.dumps(target, separators=(',', ':'))
        marker = f"[[CLIENT_TOOL:timer.delete:{tool_args}]]"
        descr = (
            f"timer #{target['id']}" if "id" in target
            else f"the {target['label']} timer" if "label" in target
            else f"the #{target['index']} timer"
        )
        logger.info("timer handler: delete %s", target)
        return {
            "text": f"Deleting {descr}. {marker}",
            "structured": {"intent": "timer",
                           "entities": {"action": "delete", **target}},
        }

    # CANCEL (all timers)
    if any(w in p_lower for w in _CANCEL_WORDS) and "timer" in p_lower:
        marker = "[[CLIENT_TOOL:timer.cancel:{}]]"
        logger.info("timer handler: cancel")
        return {
            "text": f"Cancelling your timer. {marker}",
            "structured": {"intent": "timer",
                           "entities": {"action": "cancel"}},
        }

    # LIST — must mention timer/countdown OR use a timer-specific list phrase
    _TIMER_NOUNS = ("timer", "countdown", "ticking")
    _STRICT_LIST = ("what timers", "any timers", "do i have any timer",
                    "check my timer", "show my timer", "show me my timer")
    if (any(w in p_lower for w in _LIST_WORDS)
            and (any(n in p_lower for n in _TIMER_NOUNS)
                 or any(s in p_lower for s in _STRICT_LIST))):
        marker = "[[CLIENT_TOOL:timer.list:{}]]"
        logger.info("timer handler: list")
        return {
            "text": f"Checking your timers. {marker}",
            "structured": {"intent": "timer",
                           "entities": {"action": "list"}},
        }

    # SET
    duration_ms = _parse_duration_ms(prompt)
    if duration_ms <= 0:
        logger.info("timer handler: couldn't parse duration — escalating")
        return None  # let Stage 3 (Opus) figure it out

    # Guard: conversational phrases containing a duration are NOT timer commands
    # ("let me rest for 10 minutes", "I need 5 minutes to think").
    # Require at least one timer-ish trigger word OR a very short utterance.
    _SET_TRIGGERS = ("timer", "alarm", "countdown", "remind", "wake", "buzz",
                     "nudge", "ping", "tell me when", "let me know", "set",
                     "start", "give me", "gimme", "hit me", "time me")
    is_short = len(prompt.split()) <= 4  # "ten minutes", "5 min"
    has_trigger = any(t in p_lower for t in _SET_TRIGGERS)
    if not is_short and not has_trigger:
        logger.info("timer handler: duration found but no timer trigger — escalating")
        return None

    label = _extract_label(prompt)
    args = {"duration_ms": duration_ms, "label": label}
    marker = f"[[CLIENT_TOOL:timer.set:{json.dumps(args, separators=(',', ':'))}]]"
    pretty = _pretty_duration(duration_ms)
    if label:
        spoken = f"Got it, I'll let you know when the {label} is ready in {pretty}."
    else:
        spoken = f"Timer set for {pretty}."
    logger.info("timer handler: set duration_ms=%d label=%r", duration_ms, label)
    return {
        "text": f"{spoken} {marker}",
        "structured": {
            "intent": "timer",
            "entities": {"action": "set", "duration_ms": duration_ms,
                         "label": label or ""},
        },
    }
