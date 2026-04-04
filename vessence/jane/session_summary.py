import json
import re
import subprocess
import threading
from pathlib import Path

from jane.config import ADK_VENV_PYTHON, JANE_SESSION_SUMMARY_DIR, QWEN_QUERY_SCRIPT


MAX_TOPICS = 3
MAX_TOPIC_CHARS = 100
MAX_STATE_CHARS = 220
MAX_OPEN_LOOP_CHARS = 160
_WRITE_LOCK = threading.Lock()


def _summary_path(session_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id).strip("._") or "default"
    return Path(JANE_SESSION_SUMMARY_DIR) / f"{safe_id}.json"


def load_session_summary(session_id: str) -> dict:
    path = _summary_path(session_id)
    if not path.exists():
        return {"topics": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"topics": []}
    return _sanitize_summary(data)


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


def update_session_summary_async(session_id: str, user_message: str, assistant_message: str) -> None:
    thread = threading.Thread(
        target=_update_session_summary,
        args=(session_id, user_message, assistant_message),
        daemon=True,
    )
    thread.start()


def _update_session_summary(session_id: str, user_message: str, assistant_message: str) -> None:
    current = load_session_summary(session_id)
    prompt = (
        "Return ONLY valid JSON with this exact schema:\n"
        '{"topics":[{"topic":"...","state":"...","open_loop":"..."}]}\n\n'
        "Task: update the persistent Jane web conversation summary for one session.\n"
        "Keep only the latest 3 distinct central topics from the conversation.\n"
        "Each topic should be compact and durable across stateless web requests.\n"
        "Rules:\n"
        "- Merge related updates into an existing topic instead of creating duplicates.\n"
        "- 'topic' is a short label.\n"
        "- 'state' captures what is currently known, decided, or in progress.\n"
        "- 'open_loop' captures the next unresolved question, risk, or pending step. Leave blank if none.\n"
        "- Prefer concrete names of files, systems, or projects when relevant.\n"
        "- Do not include greetings, filler, or transient chit-chat.\n"
        "- Keep each field short.\n\n"
        f"Current summary JSON:\n{json.dumps(current, ensure_ascii=True)}\n\n"
        f"Latest user message:\n{user_message}\n\n"
        f"Latest Jane response:\n{assistant_message[:2500]}"
    )

    try:
        result = subprocess.run(
            [ADK_VENV_PYTHON, QWEN_QUERY_SCRIPT, prompt],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except Exception:
        return

    parsed = _extract_json_object(result.stdout)
    if parsed is None:
        summary = _fallback_summary(current, user_message, assistant_message)
    else:
        summary = _sanitize_summary(parsed)
        if not summary.get("topics"):
            summary = _fallback_summary(current, user_message, assistant_message)
    path = _summary_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")


def _extract_json_object(text: str) -> dict | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def _sanitize_summary(data: dict) -> dict:
    raw_topics = data.get("topics") if isinstance(data, dict) else []
    topics = []
    seen = set()

    for item in raw_topics or []:
        if not isinstance(item, dict):
            continue
        topic = _clean_field(item.get("topic"), MAX_TOPIC_CHARS)
        state = _clean_field(item.get("state"), MAX_STATE_CHARS)
        open_loop = _clean_field(item.get("open_loop"), MAX_OPEN_LOOP_CHARS)
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


def _clean_field(value: object, limit: int) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _fallback_summary(current: dict, user_message: str, assistant_message: str) -> dict:
    topics = list((current or {}).get("topics") or [])
    seed_text = " ".join(part for part in [user_message, assistant_message] if part).strip()
    seed_text = re.sub(r"\s+", " ", seed_text)
    if not seed_text:
        return _sanitize_summary({"topics": topics})

    first_sentence = re.split(r"(?<=[.!?])\s+", seed_text, maxsplit=1)[0]
    topic_guess = _guess_topic_label(user_message, assistant_message)
    open_loop = ""
    if "next" in assistant_message.lower() or "need to" in assistant_message.lower():
        open_loop = _clean_field(assistant_message, MAX_OPEN_LOOP_CHARS)

    candidate = {
        "topic": topic_guess,
        "state": _clean_field(first_sentence, MAX_STATE_CHARS),
        "open_loop": open_loop,
    }

    merged = [candidate]
    for topic in topics:
        if len(merged) >= MAX_TOPICS:
            break
        if str(topic.get("topic", "")).strip().lower() == topic_guess.lower():
            continue
        merged.append(topic)
    return _sanitize_summary({"topics": merged})


def _guess_topic_label(user_message: str, assistant_message: str) -> str:
    text = f"{user_message} {assistant_message}".lower()
    keyword_map = [
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
    ]
    for needle, label in keyword_map:
        if needle in text:
            return label
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", user_message)
    if words:
        return _clean_field(" ".join(words[:4]).title(), MAX_TOPIC_CHARS)
    return "Current Conversation"
