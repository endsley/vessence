"""Parsing and coherence helpers for the send-message handler."""
from __future__ import annotations

import re


# Words that signal a sentence was cut off mid-thought.
DANGLING_ENDINGS = {
    "the", "a", "an", "was", "is", "are", "were", "at", "on", "in",
    "about", "with", "for", "to", "of", "from", "and", "but", "or",
    "that", "which", "who", "when", "where", "how", "if", "so",
    "because", "like", "just", "really", "yeah", "no",
}

FILLER_WORDS = {"uh", "um", "uhh", "umm", "hmm", "hm"}
DEVICE_COMMANDS = ["alexa", "hey siri", "ok google", "hey google"]
WRONG_CLASS_SENTINEL = {"wrong_class": True}


def is_coherent(body: str) -> bool:
    """Rule-based coherence check for voice-to-text SMS bodies."""
    if not body or body == "(none)":
        return True

    words = body.lower().split()
    if not words:
        return False

    if words[-1].rstrip(".,!?") in DANGLING_ENDINGS:
        return False

    if FILLER_WORDS & {word.rstrip(".,!?") for word in words}:
        return False

    body_lower = body.lower()
    for command in DEVICE_COMMANDS:
        if re.search(r"\b" + re.escape(command) + r"\b", body_lower):
            return False

    return True


def has_direct_send_confidence(confidence: object) -> bool:
    return (
        not isinstance(confidence, bool)
        and isinstance(confidence, (int, float))
        and confidence >= 0.80
    )


def parse_extraction(raw: str) -> dict | None:
    """Parse the LLM's structured recipient/body/coherence output."""
    if "WRONG_CLASS" in raw.upper():
        return WRONG_CLASS_SENTINEL

    recipient = body = llm_coherent = None
    for line in raw.strip().splitlines():
        line = line.strip()
        match = re.match(r"RECIPIENT:\s*(.+)", line, re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            continue
        match = re.match(r"BODY:\s*(.+)", line, re.IGNORECASE)
        if match:
            body = match.group(1).strip()
            continue
        match = re.match(r"COHERENT:\s*(.+)", line, re.IGNORECASE)
        if match:
            llm_coherent = match.group(1).strip().lower()
            continue

    if not recipient:
        return None

    body = body or "(none)"
    return {
        "recipient": recipient,
        "body": body,
        "coherent": llm_coherent != "no" and is_coherent(body),
    }


def parse_params_metadata(params: dict) -> tuple[str, dict | None]:
    """Normalize classifier params into send-message metadata.

    Returns a status string plus metadata. Non-ok statuses mean Stage 2 should
    escalate while preserving the handler's reason-specific logging.
    """
    recipient = (params.get("recipient") or "").strip()
    body_text = (params.get("body") or "").strip()
    intent_kind = (params.get("intent_kind") or "").strip().lower()
    if intent_kind == "ask":
        return "ask", None
    if not recipient:
        return "missing_recipient", None
    body = body_text or "(none)"
    return "ok", {
        "recipient": recipient,
        "body": body,
        "coherent": is_coherent(body),
        "confidence": params.get("confidence"),
    }
