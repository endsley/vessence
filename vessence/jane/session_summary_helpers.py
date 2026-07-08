"""Pure helpers for Jane session-summary formatting and fallback behavior."""

from __future__ import annotations

import json
import re
from pathlib import Path

from jane.json_scanner import find_json_object_end


MAX_TOPICS = 3
MAX_TOPIC_CHARS = 100
MAX_STATE_CHARS = 220
MAX_OPEN_LOOP_CHARS = 160

TRIVIAL_USER_PATTERNS = (
    # Greetings / sign-offs
    "hi", "hey", "hello", "bye", "goodbye", "good morning", "good night",
    "thanks", "thank you", "ok thanks", "cool thanks",
    # Time / weather / clock queries
    "what time", "what day", "what's the time", "what's the date",
    "what's the weather", "is it raining",
    # One-word acks
    "ok", "yes", "no", "sure", "yeah", "nope",
)

SUMMARY_TOPIC_KEYWORDS = (
    ("ambient migration", "Ambient Migration"),
    ("vessences.com", "Public Site"),
    ("jane.vessences.com", "Jane Public Site"),
    ("memory", "Memory Retrieval"),
    ("token", "Token Saving"),
    ("discord", "Discord"),
    ("vault", "Vault Website"),
    ("amber", "Amber"),
    ("jane", "Jane"),
    ("cron", "Cron Automation"),
)


def summary_path(base_dir: str | Path, session_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id).strip("._") or "default"
    return Path(base_dir) / f"{safe_id}.json"


def format_session_summary(summary: dict) -> str:
    topics = summary.get("topics") or []
    if not topics:
        return ""

    lines = []
    for idx, topic in enumerate(topics[:MAX_TOPICS], start=1):
        title = (topic.get("topic") or "").strip()
        state = (topic.get("state") or "").strip()
        open_loop = (topic.get("open_loop") or "").strip()
        if not (title or state or open_loop):
            continue
        lines.append(f"{idx}. Topic: {title or 'Untitled'}")
        if state:
            lines.append(f"   State: {state}")
        if open_loop:
            lines.append(f"   Open loop: {open_loop}")
    return "\n".join(lines).strip()


def is_trivial_turn(user_message: str, assistant_message: str) -> bool:
    """True if this turn is too small to be worth persisting to session summary."""
    user_text = (user_message or "").strip().lower().rstrip(".?!,")
    if not user_text:
        return True
    if len(user_text) < 35 and any(
        user_text == pattern or user_text.startswith(pattern + " ")
        for pattern in TRIVIAL_USER_PATTERNS
    ):
        return True
    if len(user_text) < 25 and len((assistant_message or "").strip()) < 200:
        return True
    return False


def strip_system_metadata(text: str) -> str:
    """Remove class protocol blocks and system metadata that confuse Qwen."""
    cleaned = re.sub(
        r"\*\*Class Protocol:.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL
    )
    cleaned = re.sub(
        r"<class_protocol[^>]*>.*?</class_protocol>", "", cleaned, flags=re.DOTALL
    )
    cleaned = re.sub(
        r"\[EXTRACTED PARAMS\].*?(?=\n\n|\Z)", "", cleaned, flags=re.DOTALL
    )
    cleaned = re.sub(
        r"\[CURRENT CONVERSATION STATE\].*?\[END CURRENT CONVERSATION STATE\]",
        "", cleaned, flags=re.DOTALL,
    )
    cleaned = re.sub(
        r"\(voice request — .*?\)", "", cleaned, flags=re.DOTALL
    )
    cleaned = re.sub(
        r"\[STANDING BRAIN MODE\].*?(?=\n\n|\Z)", "", cleaned, flags=re.DOTALL
    )
    cleaned = re.sub(
        r"\[Retrieved Memory\].*?(?=\n\n|\Z)", "", cleaned, flags=re.DOTALL
    )
    return cleaned.strip()


def build_session_summary_prompt(current: dict, user_clean: str, assistant_clean: str) -> str:
    return (
        f"Current summary:\n{json.dumps(current, ensure_ascii=True)}\n\n"
        f"Latest user message:\n{user_clean}\n\n"
        f"Latest Jane response:\n{assistant_clean}\n\n"
        "Update the summary above; do not append stale history. Keep max 3 topics. "
        "Merge related updates.\n"
        "Rules: 'topic' = short label. 'state' = current status. For project/work "
        "topics, include the point, scope, and outcome/current status when useful. "
        "If the latest turn changes, replaces, or narrows earlier work, make the "
        "state reflect the newer truth. 'open_loop' = next unresolved step "
        "(blank if none). Keep fields short.\n"
        "Do NOT explain, narrate, or ask questions. "
        "Output ONLY the JSON object, nothing else.\n"
        '```json\n{"topics":['
    )


def coerce_summary_json_output(raw: str) -> str:
    raw = raw or ""
    if not raw.strip().startswith("{"):
        return '{"topics":[' + raw
    return raw


def extract_json_object(text: str) -> dict | None:
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None
    end = find_json_object_end(text, start)
    if end is None:
        return None
    try:
        parsed = json.loads(text[start:end])
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def sanitize_summary(data: dict) -> dict:
    raw_topics = data.get("topics") if isinstance(data, dict) else []
    topics = []
    seen = set()

    for item in raw_topics or []:
        if not isinstance(item, dict):
            continue
        topic = clean_field(item.get("topic"), MAX_TOPIC_CHARS)
        state = clean_field(item.get("state"), MAX_STATE_CHARS)
        open_loop = clean_field(item.get("open_loop"), MAX_OPEN_LOOP_CHARS)
        if not (topic or state or open_loop):
            continue
        dedupe_key = topic.lower() or state.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        topics.append({"topic": topic, "state": state, "open_loop": open_loop})
        if len(topics) >= MAX_TOPICS:
            break

    return {"topics": topics}


def clean_field(value: object, limit: int) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def fallback_summary(current: dict, user_message: str, assistant_message: str) -> dict:
    topics = list((current or {}).get("topics") or [])
    seed_text = " ".join(part for part in [user_message, assistant_message] if part).strip()
    seed_text = re.sub(r"\s+", " ", seed_text)
    if not seed_text:
        return sanitize_summary({"topics": topics})

    first_sentence = re.split(r"(?<=[.!?])\s+", seed_text, maxsplit=1)[0]
    topic_guess = guess_topic_label(user_message, assistant_message)
    open_loop = ""
    if "next" in assistant_message.lower() or "need to" in assistant_message.lower():
        open_loop = clean_field(assistant_message, MAX_OPEN_LOOP_CHARS)

    candidate = {
        "topic": topic_guess,
        "state": clean_field(first_sentence, MAX_STATE_CHARS),
        "open_loop": open_loop,
    }

    merged = [candidate]
    for topic in topics:
        if len(merged) >= MAX_TOPICS:
            break
        if str(topic.get("topic", "")).strip().lower() == topic_guess.lower():
            continue
        merged.append(topic)
    return sanitize_summary({"topics": merged})


def guess_topic_label(user_message: str, assistant_message: str) -> str:
    text = f"{user_message} {assistant_message}".lower()
    for needle, label in SUMMARY_TOPIC_KEYWORDS:
        if needle in text:
            return label
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", user_message)
    if words:
        return clean_field(" ".join(words[:4]).title(), MAX_TOPIC_CHARS)
    return "Current Conversation"
