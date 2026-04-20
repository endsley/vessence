"""Stage 1 �� ChromaDB embedding classifier.

Pure vector similarity — no LLM call. ~5-50ms per classification.

Takes the raw user prompt, returns (class_name, confidence).
class_name matches the pipeline's class registry keys (lowercase, spaces).
confidence ∈ {"High", "Low"}
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Strip phone-tool result markers and other system prefixes before
# classification. Android prepends [TOOL_RESULT:{json}] to follow-up
# messages so Jane can see what happened on the phone — but the JSON
# blob contains words like "tool", "send", "message" that pollute
# the classifier's signal. The user's actual question comes after.
_TOOL_RESULT_RE = re.compile(r"\[TOOL_RESULT:\{[^}]*\}\]\s*", re.DOTALL)
# Non-greedy match through nested [[CLIENT_TOOL:...]] up to the [END ...] sentinel.
_SYS_PREFIX_RE = re.compile(
    r"\[(SMS SEND REQUEST|PHONE TOOL RESULTS)[^\]]*\].*?\[END\s+[^\]]+\]\s*",
    re.DOTALL | re.IGNORECASE,
)
# Fallback: SMS SEND REQUEST that got truncated without a closing [END...]
_SYS_TAIL_RE = re.compile(
    r"\n*\[(SMS SEND REQUEST|PHONE TOOL RESULTS)[\s\S]*$",
    re.IGNORECASE,
)

# Subject-change prefixes. "change the subject to weather" leaks the verb
# "change" and the filler "subject" into the embedding — the weather signal
# can then lose to sibling classes. Strip the preamble so the classifier
# sees only the new topic ("weather").
_SUBJECT_CHANGE_RE = re.compile(
    r"^\s*(?:"
    r"(?:i(?:'| a)?d\s+like\s+to\s+"
    r"|i\s+would\s+like\s+to\s+"
    r"|i\s+want\s+to\s+"
    r"|i\s+wanna\s+"
    r"|(?:let(?:'| a)?s|lets)\s+"
    r"|can\s+we\s+"
    r"|can\s+you\s+"
    r"|please\s+)?"
    r"(?:change|switch|shift|move|go)\s+(?:the\s+)?(?:subject|topic|conversation)\s+to\s+"
    r"|"
    r"(?:let(?:'| a)?s|lets)\s+(?:talk\s+about|discuss)\s+"
    r"|"
    r"(?:switching|changing)\s+(?:the\s+)?(?:subject|topic)(?:\s+to)?\s+"
    r")",
    re.IGNORECASE,
)

# Common singular/plural normalization to help the classifier recognize the
# canonical class term ("weathers" → "weather"). Only the classes where a
# trailing-s confusion actually hurt Stage 1 in production.
_PLURAL_FIXUPS = {
    r"\bweathers\b": "weather",
}


def _strip_system_markers(prompt: str) -> str:
    """Strip TOOL_RESULT and SMS SEND REQUEST markers so the classifier
    sees only the user's actual words."""
    cleaned = _TOOL_RESULT_RE.sub("", prompt)
    cleaned = _SYS_PREFIX_RE.sub("", cleaned)
    cleaned = _SYS_TAIL_RE.sub("", cleaned)  # truncated leftovers
    cleaned = _SUBJECT_CHANGE_RE.sub("", cleaned, count=1)
    for pat, repl in _PLURAL_FIXUPS.items():
        cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or prompt

# Maturity-based gate thresholds. Precision-first for new classes.
#
# Loose-gate failure = wrong answer (Stage 2 fires on ambiguous prompts
# and produces a silent correctness bug). Tight-gate failure = extra
# latency (Stage 3/Opus handles it correctly, just slower). The cost
# asymmetry favors tight.
#
# A new class defaults to "new" until it proves itself in audit runs or
# Chieh explicitly promotes it. Promotion = move the key into PROVEN_CLASSES.
_GATE_NEW    = {"conf": 0.80, "margin": 0.40}  # 4/5 votes, 2-vote gap
_GATE_PROVEN = {"conf": 0.60, "margin": 0.20}  # 3/5 votes, 1-vote gap
_GATE_STRICT = {"conf": 1.00, "margin": 0.40}  # 5/5 votes (unanimous)

PROVEN_CLASSES = {
    "WEATHER",
    "GREETING",
    "GET_TIME",
    "MUSIC_PLAY",
    "SEND_MESSAGE",
    "TIMER",
    "END_CONVERSATION",  # has its own 0.80 floor below; still "proven"
}

# Classes where a false positive is a loud user-visible disruption
# (Jane reads your texts, dumps your inbox) but a missed call costs only
# latency (Stage 3 still answers correctly). Cost asymmetry → demand
# unanimous votes AND a literal keyword match before firing the handler.
STRICT_CLASSES = {
    "READ_MESSAGES",
    "SYNC_MESSAGES",
    "READ_EMAIL",
    "READ_CALENDAR",
}

# Hard keyword guard for STRICT_CLASSES. Even unanimous votes don't fire
# the handler unless the cleaned prompt contains one of these substrings.
# Catches embedding drift on prompts like "any updates" or "what came in"
# that semantically resemble training data but lack the literal noun.
_STRICT_KEYWORDS = {
    "READ_MESSAGES": ("text", "message", "msg", "sms", "imessage", "inbox"),
    "SYNC_MESSAGES": ("text", "message", "msg", "sms", "sync"),
    "READ_EMAIL":    ("email", "e-mail", "inbox", "gmail", "mail"),
    "READ_CALENDAR": ("calendar", "agenda", "schedule"),
}

_END_CONVERSATION_RE = re.compile(
    r"^\s*(?:"
    r"(?:ok(?:ay)?\s+)?(?:we(?:'| a)re|were)\s+done|"
    r"(?:ok(?:ay)?\s+)?i(?:'| a)m\s+done|"
    r"(?:ok(?:ay)?\s+)?all\s+done|"
    r"(?:ok(?:ay)?\s+)?(?:that's|that is)\s+(?:all|it)|"
    r"(?:thank\s+you|thanks)(?:\s+(?:jane|bye|goodbye|(?:that's|that is)\s+(?:all|it)))?|"
    r"good\s*bye|bye(?:\s+jane|\s+now)?|"
    r"see\s+(?:you|ya)(?:\s+later)?|talk\s+(?:to\s+you\s+)?later|"
    r"good\s*night(?:\s+jane)?|night\s+jane|night\s+night|"
    r"end\s+(?:conversation|chat)|conversation\s+over|close\s+conversation|"
    r"stop(?:\s+(?:listening|talking|that|right\s+there))?|"
    r"cancel(?:\s+(?:that|it))?|dismiss|"
    r"be\s+quiet|quiet|shut\s+up|silence|shush|enough|that's\s+enough|"
    r"never\s*mind|forget\s+(?:it|about\s+it)|drop\s+it|abort|"
    r"no\s+thanks|nope|nah|not\s+now|skip\s+it|"
    r"go\s+away|leave\s+me\s+alone|"
    r"i(?:'| a)m\s+good|all\s+good|we(?:'| a)re\s+good|all\s+set|"
    r"ok\s+(?:cool|great|thanks(?:\s+bye)?|done)|"
    r"roger(?:\s+that\s+done)?|over\s+and\s+out"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def _gate_for(raw_cls: str) -> dict:
    if raw_cls in STRICT_CLASSES:
        return _GATE_STRICT
    return _GATE_PROVEN if raw_cls in PROVEN_CLASSES else _GATE_NEW


def _strict_keyword_ok(raw_cls: str, cleaned_prompt: str) -> bool:
    """Return True if the prompt contains a required keyword for this strict class.

    Returns True for classes not in _STRICT_KEYWORDS so the gate is
    a no-op for non-strict raw classes. Matches on word boundaries so
    e.g. "schedule" does not fire on "reschedule".
    """
    keywords = _STRICT_KEYWORDS.get(raw_cls)
    if not keywords:
        return True
    lc = cleaned_prompt.lower()
    for k in keywords:
        # Left word-boundary only. Stops "schedule" from firing on
        # "reschedule" while still matching plurals/inflections like
        # "emails", "schedules", "emailing".
        if re.search(r"(?<![a-z])" + re.escape(k), lc):
            return True
    return False


def _end_conversation_phrase_ok(cleaned_prompt: str) -> bool:
    """Only allow END_CONVERSATION for complete ending utterances.

    Single stop words embedded in a real sentence are not enough. For example,
    "I think setting the context window to 1024 is not long enough" contains
    "enough", but it is a technical observation and must go to Stage 3.
    """
    normalized = re.sub(r"\s+", " ", (cleaned_prompt or "").strip())
    normalized = normalized.replace("\u2019", "'").replace("\u2018", "'")
    return bool(_END_CONVERSATION_RE.match(normalized))


# Map ChromaDB uppercase class names → pipeline registry names
_CLASS_MAP = {
    "MUSIC_PLAY":        "music play",
    "WEATHER":           "weather",
    "GREETING":          "greeting",
    "READ_MESSAGES":     "read messages",
    "SEND_MESSAGE":      "send message",
    "SYNC_MESSAGES":     "sync messages",
    "SHOPPING_LIST":     "shopping list",
    "READ_EMAIL":        "read email",
    "READ_CALENDAR":     "read calendar",
    "END_CONVERSATION":  "end conversation",
    "GET_TIME":          "get time",
    "TIMER":             "timer",
    "TODO_LIST":         "todo list",
    "SELF_IMPROVEMENT":  "self improvement",
    "DELEGATE_OPUS":     "others",
    "FORCE_STAGE3":      "others",
}

# Explicit user-invoked escalation phrases. If any of these substrings
# appear in the cleaned prompt, bypass ChromaDB entirely and route to
# Stage 3. This guarantees Chieh's override works even when a sibling
# class's embedding matches loosely. Lowercase comparison.
FORCE_STAGE3_PHRASES = (
    "think deeply",
    "think carefully",
    "think hard about",
    "think this through",
    "really think about",
    "use the big brain",
    "use your full brain",
    "use your deeper reasoning",
    "give this some real thought",
    "escalate this to opus",
    "escalate to the main brain",
    "let the smart one answer",
    "ponder this carefully",
    "reason deeply",
    "actually reason about",
    "use stage 3",
    "stage 3 for this",
    "stage 3 please",
    "route this to stage 3",
    "send this to stage 3",
    "stage three",
    "use stage three",
    "escalate to stage 3",
    "kick this to stage 3",
    "bump to stage 3",
    "go to stage 3",
    "i want stage 3",
    "give me stage 3",
)

# Fallback regex for "think <stuff> deeply/carefully/hard/through" variants where
# an intervening word (e.g. "this", "it", "that one") slips past the literal list.
# Matches: "think this deeply", "think it carefully", "think that one through", etc.
_FORCE_STAGE3_RE = re.compile(
    r"\b(think|reason|ponder)\b[\w\s]{0,20}?\b(deeply|carefully|hard|through|thoroughly)\b",
    re.IGNORECASE,
)

async def classify(
    user_prompt: str,
    session_id: str | None = None,
    timeout: float = 90.0,
) -> tuple[str, str, float]:
    """Classify a user prompt via ChromaDB embedding lookup.

    Returns (class_name, confidence, min_dist). `min_dist` is the cosine
    distance of the top-1 nearest exemplar; callers use it to detect
    "near-identical to a known example" prompts and skip downstream LLM
    gates. On failure returns ("others", "Low", 1.0).

    `session_id` is accepted for forward-compatibility with context-aware
    routing (job 069). Currently the embedding is still prompt-only — the
    session-aware deterministic pre-routing lives in
    ``jane_web.jane_v2.pending_action_resolver`` and runs in the pipeline
    before this function. Keeping the arg here so future context-embedding
    experiments don't require another signature change.
    """
    _ = session_id  # reserved for future context-aware embedding
    cleaned = _strip_system_markers(user_prompt)
    if cleaned != user_prompt:
        logger.info("stage1_classifier: stripped system markers (orig=%d, clean=%d)",
                    len(user_prompt), len(cleaned))

    # Hard phrase override — user explicitly asked for deeper thinking.
    # Bypass ChromaDB so loose embedding matches in sibling classes can't win.
    _lc = cleaned.lower()
    for _p in FORCE_STAGE3_PHRASES:
        if _p in _lc:
            logger.info("stage1_classifier: FORCE_STAGE3 phrase override (%r)", _p)
            return ("others", "Low", 1.0)
    # Regex fallback for variants like "think this deeply" / "reason it through"
    if _FORCE_STAGE3_RE.search(_lc):
        logger.info("stage1_classifier: FORCE_STAGE3 regex override")
        return ("others", "Low", 1.0)

    try:
        from intent_classifier.v2.classifier import stage1_classify
        result = await stage1_classify(cleaned)
    except Exception as e:
        logger.warning("stage1_classifier: ChromaDB classify failed: %s", e)
        return ("others", "Low", 1.0)

    raw_cls = result.get("classification", "DELEGATE_OPUS")
    confidence = result.get("confidence", 0.0)

    cls = _CLASS_MAP.get(raw_cls, "others")
    # If the wrapper doesn't know the class, treat as Low (catch-all).
    # If the classifier returned DELEGATE_OPUS, also Low.
    # END_CONVERSATION gets a tighter confidence gate here, but real
    # error-capture (questions that embed near goodbyes, etc.) lives in
    # Stage 2's _gate_check — that's the three-stage design.
    margin = result.get("margin", 0.0)
    gate = _gate_for(raw_cls)
    if raw_cls == "DELEGATE_OPUS" or cls == "others":
        conf = "Low"
    elif raw_cls == "END_CONVERSATION" and not _end_conversation_phrase_ok(cleaned):
        logger.info(
            "stage1_classifier: END_CONVERSATION phrase guard rejected %r",
            cleaned[:100],
        )
        conf = "Low"
    elif raw_cls == "END_CONVERSATION" and confidence < 0.80:
        # Extra floor: a wrong END_CONVERSATION destroys the session.
        conf = "Low"
    elif confidence < gate["conf"] or margin < gate["margin"]:
        # Below this class's maturity gate → demote so Stage 3 decides.
        conf = "Low"
    elif raw_cls in STRICT_CLASSES and not _strict_keyword_ok(raw_cls, cleaned):
        # Strict-class keyword guard: even a unanimous embedding vote must be
        # backed by a literal keyword. Stops false positives like
        # "any updates from yesterday" → READ_MESSAGES.
        logger.info(
            "stage1_classifier: STRICT %s lacks keyword in %r — demote to Low",
            raw_cls, cleaned[:80],
        )
        conf = "Low"
    else:
        conf = "High"

    min_dist = float(result.get("min_dist", 1.0))
    logger.info(
        "stage1_classifier: %s:%s  (raw=%s conf=%.2f margin=%.2f dist=%.3f lat=%.0fms)",
        cls, conf, raw_cls, confidence,
        result.get("margin", 0.0), min_dist, result.get("latency_ms", 0.0),
    )
    return (cls, conf, min_dist)
