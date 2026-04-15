"""Timer Stage 2 handler.

Handles four actions entirely on the Android client via CLIENT_TOOL markers:
  - set    → [[CLIENT_TOOL:timer.set:{"duration_ms": <ms>, "label": "..."}]]
  - cancel → [[CLIENT_TOOL:timer.cancel:{}]]
  - list   → [[CLIENT_TOOL:timer.list:{}]]
  - delete → [[CLIENT_TOOL:timer.delete:{"id"|"index"|"label": ...}]]

The server keeps NO state about scheduled alarms — the phone owns every
timer via AlarmManager so they ring even when offline.

Multi-turn conversation support: when the user says something like "I
want to create a timer" without specifying a duration, this handler
emits a STAGE2_FOLLOWUP pending_action and asks a follow-up question.
The pending_action_resolver routes the user's next reply back to this
handler (bypassing Stage 1) with the collected state in `pending`, so
the exchange feels like one logical turn from the user's perspective.

State machine (SET flow):
  enter(no duration)      → ask duration           [pending: awaiting=duration]
  enter(duration, label)  → fire                   [no pending]
  enter(duration, !label) → ask label              [pending: awaiting=label]
  resume(awaiting=duration, prompt) → parse → ask label OR re-ask
  resume(awaiting=label, prompt)    → parse → fire
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


# ── Follow-up helpers ─────────────────────────────────────────────────────

# The "no label" reply vocabulary — user explicitly opts out of labeling.
_NO_LABEL_REPLIES = {
    "no", "no label", "none", "skip", "nothing", "nope", "nah",
    "no thanks", "no thank you", "don't", "dont", "without a label",
    "without label", "i don't want one", "i don't want a label",
    "just set it", "leave it", "blank",
}

# Phrases that look like a PIVOT away from the timer conversation —
# the user is asking something else mid-flow. The handler bails via
# `abandon_pending` so the pipeline re-classifies the original prompt
# through Stage 1. Kept conservative: only trigger on clear wh-question
# starts + common domain switches.
_PIVOT_PREFIXES = (
    "what's the weather", "whats the weather", "how's the weather",
    "what time is it", "what's the time", "whats the time",
    "read my messages", "check my messages", "check my email",
    "tell ", "text ",  # "tell Kathia...", "text mom..."
    "play ",
)


def _label_from_reply(prompt: str) -> str:
    """Extract a clean label from a follow-up reply. '' means 'no label'."""
    p = prompt.strip()
    if p.lower().strip(".!?,") in _NO_LABEL_REPLIES:
        return ""
    # Strip common polite wrappers: "call it X", "the label is X", "X please"
    for pattern in (
        r"^(?:call\s+it|label\s+it|name\s+it|its\s+called|it's\s+called|the\s+label\s+(?:is|should\s+be)|label:)\s+",
        r"^(?:let's\s+call\s+it\s+|i'd\s+call\s+it\s+|how\s+about\s+)",
    ):
        p = re.sub(pattern, "", p, flags=re.IGNORECASE).strip()
    # Trim trailing politeness
    p = re.sub(r"\s+(?:please|thanks|thank\s+you)\s*[.!?]?\s*$", "", p, flags=re.IGNORECASE).strip()
    p = p.rstrip(".!?,").strip()
    return p[:60]  # cap length


def _looks_like_pivot(prompt: str) -> bool:
    p_lower = prompt.lower().strip()
    return any(p_lower.startswith(pref) for pref in _PIVOT_PREFIXES)


def _expires_at(minutes: int = 2) -> str:
    import datetime as _dt
    return (_dt.datetime.utcnow() + _dt.timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _pending(awaiting: str, data: dict) -> dict:
    """Build a STAGE2_FOLLOWUP pending_action for the timer handler."""
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "timer",
        "status": "awaiting_user",
        "awaiting": awaiting,
        "data": {**data, "awaiting": awaiting},
        "expires_at": _expires_at(),
    }


def _ask_duration(data: dict) -> dict:
    return {
        "text": "Sure — how long should the timer run?",
        "structured": {
            "intent": "timer",
            "entities": {"action": "set", "stage": "await_duration"},
            "pending_action": _pending("duration", data),
        },
    }


def _ask_label(data: dict) -> dict:
    pretty = _pretty_duration(data.get("duration_ms", 0))
    return {
        "text": f"Got it, {pretty}. What should I call this timer? Or say 'no label'.",
        "structured": {
            "intent": "timer",
            "entities": {"action": "set", "stage": "await_label",
                         "duration_ms": data.get("duration_ms")},
            "pending_action": _pending("label", data),
        },
    }


def _fire_set(duration_ms: int, label: str) -> dict:
    args = {"duration_ms": duration_ms, "label": label}
    marker = f"[[CLIENT_TOOL:timer.set:{json.dumps(args, separators=(',', ':'))}]]"
    pretty = _pretty_duration(duration_ms)
    if label:
        # If the label is already a complete sentence-end ("pasta is
        # ready", "bread is done", "time's up"), don't re-append
        # " is ready" — the user already said it.
        ll = label.lower()
        already_terminal = any(ll.endswith(w) for w in
                               ("ready", "done", "up", "finished", "out"))
        if already_terminal:
            spoken = f"Timer set — I'll tell you in {pretty} when {label}."
        else:
            spoken = f"Timer set — I'll let you know when the {label} is ready in {pretty}."
    else:
        spoken = f"Timer set for {pretty}."
    logger.info("timer handler: fire duration_ms=%d label=%r", duration_ms, label)
    return {
        "text": f"{spoken} {marker}",
        "structured": {
            "intent": "timer",
            "entities": {"action": "set", "duration_ms": duration_ms,
                         "label": label or ""},
            # No pending_action — turn is done, Stage 1 resumes next turn.
        },
    }


def _handle_resume(prompt: str, pending: dict) -> dict | None:
    """Called when the pending_action_resolver routes a follow-up reply
    back to us.

    `pending` is the `data` dict we stashed last turn (the pipeline
    passes `pending_data` through, not the whole pending_action record).
    It contains the accumulated state plus an `awaiting` key marking
    what the user's reply is answering.
    """
    if _looks_like_pivot(prompt):
        logger.info("timer handler: pivot detected mid-flow → abandon")
        return {"abandon_pending": True}

    # Treat `pending` directly as the data dict — that's how the
    # dispatcher hands it to us.
    data = dict(pending or {})
    awaiting = data.pop("awaiting", None)

    if awaiting == "duration":
        dur = _parse_duration_ms(prompt)
        # Also try "five" / "one" → 5 / 1 with an implicit minutes unit,
        # since follow-up replies often drop the unit word.
        if dur <= 0:
            m = re.fullmatch(r"\s*(\d+(?:\.\d+)?|\w+)\s*", prompt.strip().lower())
            if m:
                tok = m.group(1)
                try:
                    n = float(tok)
                except ValueError:
                    n = float(_NUM_WORDS.get(tok, 0))
                if n > 0:
                    dur = int(n * 60 * 1000)  # assume minutes
        if dur <= 0:
            # Re-ask once.
            return {
                "text": "I didn't catch that. How long should the timer run? Like '5 minutes'.",
                "structured": {
                    "intent": "timer",
                    "pending_action": _pending("duration", data),
                },
            }
        data["duration_ms"] = dur
        # If we already have a label from earlier, fire; otherwise ask.
        if data.get("label"):
            return _fire_set(dur, data["label"])
        return _ask_label(data)

    if awaiting == "label":
        label = _label_from_reply(prompt)
        dur = int(data.get("duration_ms") or 0)
        if dur <= 0:
            # Shouldn't happen (label is only asked after duration) —
            # but be defensive: fall back to asking for duration.
            return _ask_duration({"label": label})
        return _fire_set(dur, label)

    logger.warning("timer handler: unknown awaiting %r — abandoning", awaiting)
    return {"abandon_pending": True}


def handle(prompt: str, pending: dict | None = None) -> dict | None:
    # ── Resume path: we're mid-conversation with this user ────────────
    if pending:
        return _handle_resume(prompt, pending)

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

    # "Wants a timer, no duration yet" — conversational creation.
    # ("hey Jane I want to create a timer" / "start a timer for me")
    _CREATE_TIMER_WORDS = ("timer", "alarm", "countdown")
    _CREATE_VERBS = ("create", "make", "start", "begin", "set up",
                     "start a", "make me a", "give me a", "need a")
    wants_timer = any(w in p_lower for w in _CREATE_TIMER_WORDS)
    wants_create = any(v in p_lower for v in _CREATE_VERBS)
    if duration_ms <= 0:
        if wants_timer and (wants_create or p_lower.startswith("i ") or "i want" in p_lower):
            logger.info("timer handler: create-timer intent, no duration → ask")
            return _ask_duration({})
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
    # Duration known but no label → ask (user can always say "no label").
    if not label:
        logger.info("timer handler: duration=%d but no label → ask", duration_ms)
        return _ask_label({"duration_ms": duration_ms})
    return _fire_set(duration_ms, label)
