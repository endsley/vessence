import json
import subprocess
import threading
from pathlib import Path

from jane.config import ADK_VENV_PYTHON, JANE_SESSION_SUMMARY_DIR, QWEN_QUERY_SCRIPT
from jane.session_summary_helpers import (
    MAX_OPEN_LOOP_CHARS,
    MAX_STATE_CHARS,
    MAX_TOPIC_CHARS,
    MAX_TOPICS,
    build_session_summary_prompt as _build_session_summary_prompt,
    clean_field as _clean_field,
    coerce_summary_json_output as _coerce_summary_json_output,
    extract_json_object as _extract_json_object,
    fallback_summary as _fallback_summary,
    format_session_summary,
    guess_topic_label as _guess_topic_label,
    is_trivial_turn as _is_trivial_turn,
    sanitize_summary as _sanitize_summary,
    strip_system_metadata as _strip_system_metadata,
    summary_path as _summary_path_for_base,
)

_WRITE_LOCK = threading.Lock()


def _summary_path(session_id: str) -> Path:
    return _summary_path_for_base(JANE_SESSION_SUMMARY_DIR, session_id)


def load_session_summary(session_id: str) -> dict:
    path = _summary_path(session_id)
    if not path.exists():
        return {"topics": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"topics": []}
    return _sanitize_summary(data)


# Trivial-turn heuristics: skip the expensive session-summary update for
# short greetings / time queries / acks. These turns add no durable topic
# worth persisting, and each subprocess.run forks a large (~1.4 GB) Python
# process — fork cost + qwen subprocess (90 s timeout) + GIL contention
# during fork was measurably stalling the event loop (investigation
# 2026-04-18, see jane_proxy logs around 18:03:46).
def update_session_summary_async(session_id: str, user_message: str, assistant_message: str) -> None:
    if _is_trivial_turn(user_message, assistant_message):
        # Skip — prevents fork pressure + subprocess overhead on chit-chat.
        return
    thread = threading.Thread(
        target=_update_session_summary,
        args=(session_id, user_message, assistant_message),
        daemon=True,
    )
    thread.start()


def _update_session_summary(session_id: str, user_message: str, assistant_message: str) -> None:
    current = load_session_summary(session_id)
    user_clean = _strip_system_metadata(user_message)[:1500]
    assistant_clean = _strip_system_metadata(assistant_message)[:2500]
    if not user_clean and not assistant_clean:
        return
    prompt = _build_session_summary_prompt(current, user_clean, assistant_clean)

    try:
        result = subprocess.run(
            [ADK_VENV_PYTHON, QWEN_QUERY_SCRIPT, prompt],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except Exception:
        return

    raw = _coerce_summary_json_output(result.stdout or "")
    parsed = _extract_json_object(raw)
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
