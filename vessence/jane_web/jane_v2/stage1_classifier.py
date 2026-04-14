"""Stage 1 �� ChromaDB embedding classifier (replaces gemma4:e2b).

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


def _strip_system_markers(prompt: str) -> str:
    """Strip TOOL_RESULT and SMS SEND REQUEST markers so the classifier
    sees only the user's actual words."""
    cleaned = _TOOL_RESULT_RE.sub("", prompt)
    cleaned = _SYS_PREFIX_RE.sub("", cleaned)
    cleaned = _SYS_TAIL_RE.sub("", cleaned)  # truncated leftovers
    return cleaned.strip() or prompt

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
    "END_CONVERSATION":  "end conversation",
    "GET_TIME":          "get time",
    "DELEGATE_OPUS":     "others",
}


async def classify(user_prompt: str, timeout: float = 90.0) -> tuple[str, str]:
    """Classify a user prompt via ChromaDB embedding lookup.

    Returns (class_name, confidence) to match the pipeline's expected interface.
    On any failure returns ("others", "Low") so the caller falls through to Stage 3.
    """
    cleaned = _strip_system_markers(user_prompt)
    if cleaned != user_prompt:
        logger.info("stage1_classifier: stripped system markers (orig=%d, clean=%d)",
                    len(user_prompt), len(cleaned))
    try:
        from intent_classifier.v2.classifier import stage1_classify
        result = await stage1_classify(cleaned)
    except Exception as e:
        logger.warning("stage1_classifier: ChromaDB classify failed: %s", e)
        return ("others", "Low")

    raw_cls = result.get("classification", "DELEGATE_OPUS")
    confidence = result.get("confidence", 0.0)

    cls = _CLASS_MAP.get(raw_cls, "others")
    # If the wrapper doesn't know the class, treat as Low (catch-all).
    # If the classifier returned DELEGATE_OPUS, also Low.
    # END_CONVERSATION must be very high confidence since it destructively
    # ends the chat with no LLM second opinion (tighter gate than 0.60).
    if raw_cls == "DELEGATE_OPUS" or cls == "others":
        conf = "Low"
    elif raw_cls == "END_CONVERSATION" and confidence < 0.80:
        conf = "Low"
    else:
        conf = "High"

    logger.info(
        "stage1_classifier: %s:%s  (raw=%s conf=%.2f margin=%.2f lat=%.0fms)",
        cls, conf, raw_cls, confidence,
        result.get("margin", 0.0), result.get("latency_ms", 0.0),
    )
    return (cls, conf)
