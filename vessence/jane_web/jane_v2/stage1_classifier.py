"""Stage 1 �� ChromaDB embedding classifier (replaces gemma4:e2b).

Pure vector similarity — no LLM call. ~5-50ms per classification.

Takes the raw user prompt, returns (class_name, confidence).
class_name matches the pipeline's class registry keys (lowercase, spaces).
confidence ∈ {"High", "Low"}
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

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
    try:
        from intent_classifier.v2.classifier import stage1_classify
        result = await stage1_classify(user_prompt)
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
