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

from jane_web.jane_v2.stage1_prompt_cleaning import (
    strip_stage1_system_markers as _strip_system_markers,
)

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
    "TIMER",
    "CLINIC_SCHEDULES_INFO",
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


def _clinic_schedule_ok(cleaned_prompt: str) -> bool:
    """Keep first-person personal schedule phrasing out of clinic routing."""
    lc = cleaned_prompt.lower()
    if "my schedule" not in lc:
        return True
    return any(k in lc for k in ("clinic", "patient", "patients", "kathia", "her schedule"))


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
    "BUILD_APK":         "others",
    "MUSIC_PLAY":        "music play",
    "WEATHER":           "weather",
    "GREETING":          "greeting",
    "READ_MESSAGES":     "read messages",
    "SEND_MESSAGE":      "send message",
    "SYNC_MESSAGES":     "sync messages",
    "SHOPPING_LIST":     "shopping list",
    "DELETE_MESSAGES":   "delete messages",
    "READ_EMAIL":        "read email",
    "SEND_EMAIL":        "send email",
    "DELETE_EMAIL":      "delete email",
    "READ_CALENDAR":     "read calendar",
    "CLINIC_SCHEDULES_INFO": "clinic schedules info",
    "END_CONVERSATION":  "end conversation",
    "GET_TIME":          "get time",
    "TIMER":             "timer",
    "TODO_LIST":         "todo list",
    "DO_MATH":           "do math",
    "TELL_JOKE":         "tell joke",
    "WEB_AUTOMATION":    "web_automation",
    "SELF_IMPROVEMENT":  "self improvement",
    "NATIONALGRID BILLS": "nationalgrid bills",
    "NATIONALGRID_BILLS": "nationalgrid bills",
    "RESTART_SERVER":    "others",
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


def _force_stage3_override(cleaned_prompt: str) -> str | None:
    lc = (cleaned_prompt or "").lower()
    for phrase in FORCE_STAGE3_PHRASES:
        if phrase in lc:
            return phrase
    if _FORCE_STAGE3_RE.search(lc):
        return "__regex__"
    return None


def _classification_confidence(
    raw_cls: str,
    cls: str,
    confidence: float,
    margin: float,
    cleaned_prompt: str,
) -> str:
    gate = _gate_for(raw_cls)
    if raw_cls == "DELEGATE_OPUS" or cls == "others":
        return "Low"
    if raw_cls == "END_CONVERSATION" and not _end_conversation_phrase_ok(cleaned_prompt):
        logger.info(
            "stage1_classifier: END_CONVERSATION phrase guard rejected %r",
            cleaned_prompt[:100],
        )
        return "Low"
    if raw_cls == "END_CONVERSATION" and confidence < 0.80:
        # Extra floor: a wrong END_CONVERSATION destroys the session.
        return "Low"
    if raw_cls == "CLINIC_SCHEDULES_INFO" and not _clinic_schedule_ok(cleaned_prompt):
        logger.info(
            "stage1_classifier: CLINIC_SCHEDULES_INFO rejected personal schedule phrasing %r",
            cleaned_prompt[:100],
        )
        return "Low"
    if confidence < gate["conf"] or margin < gate["margin"]:
        # Below this class's maturity gate → demote so Stage 3 decides.
        return "Low"
    if raw_cls in STRICT_CLASSES and not _strict_keyword_ok(raw_cls, cleaned_prompt):
        # Strict-class keyword guard: even a unanimous embedding vote must be
        # backed by a literal keyword. Stops false positives like
        # "any updates from yesterday" → READ_MESSAGES.
        logger.info(
            "stage1_classifier: STRICT %s lacks keyword in %r — demote to Low",
            raw_cls, cleaned_prompt[:80],
        )
        return "Low"
    return "High"


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
    override = _force_stage3_override(cleaned)
    if override and override != "__regex__":
        logger.info("stage1_classifier: FORCE_STAGE3 phrase override (%r)", override)
        return ("others", "Low", 1.0)
    if override == "__regex__":
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
    conf = _classification_confidence(raw_cls, cls, confidence, margin, cleaned)

    min_dist = float(result.get("min_dist", 1.0))
    logger.info(
        "stage1_classifier: %s:%s  (raw=%s conf=%.2f margin=%.2f dist=%.3f lat=%.0fms)",
        cls, conf, raw_cls, confidence,
        result.get("margin", 0.0), min_dist, result.get("latency_ms", 0.0),
    )
    return (cls, conf, min_dist)
