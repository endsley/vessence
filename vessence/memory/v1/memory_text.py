"""Text, age, and deduplication helpers for memory retrieval."""

from __future__ import annotations

import datetime


def is_expired(meta: dict) -> bool:
    expires_at = (meta or {}).get("expires_at")
    if not expires_at:
        return False

    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    if isinstance(expires_at, (int, float)):
        return expires_at < now_ts

    try:
        expires_dt = datetime.datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=datetime.timezone.utc)
        return expires_dt.timestamp() < now_ts
    except Exception:
        return False


def is_too_old(meta: dict, max_days: int = 3) -> bool:
    """Return True if the entry is older than max_days. Entries without timestamps pass through."""
    ts_str = (meta or {}).get("timestamp", (meta or {}).get("created_at", ""))
    if not ts_str:
        return False
    try:
        ts = datetime.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 86400
        return age > max_days
    except Exception:
        return False


def age_days(meta: dict) -> float | None:
    ts_str = (meta or {}).get("timestamp", (meta or {}).get("created_at", ""))
    if not ts_str:
        return None
    try:
        ts = datetime.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        return (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 86400
    except Exception:
        return None


def is_none_content(doc: str) -> bool:
    """Return True if the document content is a None/empty sentinel."""
    stripped = (doc or "").strip()
    return stripped in ("None", "none", "", "null", "N/A")


def recency_label(ts_str: str) -> str:
    if not ts_str or ts_str == "Unknown Time":
        return "unknown age"
    try:
        ts = datetime.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        delta = datetime.datetime.now(datetime.timezone.utc) - ts
        secs = delta.total_seconds()
        if secs < 0:
            return "just now"
        if secs < 3600:
            return f"{int(secs // 60)}m ago"
        if secs < 86400:
            return f"{int(secs // 3600)}h ago"
        return f"{int(secs // 86400)}d ago"
    except Exception:
        return "unknown age"


def fmt_memory(doc: str, meta: dict | None) -> str:
    meta = meta or {}
    ts = meta.get("timestamp", meta.get("created_at", ""))
    topic = meta.get("topic", meta.get("source", "General"))
    dist = meta.get("distance")
    age = recency_label(ts) if ts else "unknown age"
    dist_str = f" (Dist: {dist:.4f})" if dist is not None else ""
    return f"[{age}] ({topic}){dist_str}: {doc}"


def extract_content_key(line: str) -> str:
    """Extract the content portion of a formatted memory line for dedup comparison."""
    text = str(line)
    idx = text.rfind("): ")
    if idx != -1:
        text = text[idx + 3 :]
    return " ".join(text.split()).lower()[:120]


def dedupe_fact_lines(lines: list[str], global_seen: set[str] | None = None) -> list[str]:
    """Deduplicate formatted memory lines."""
    local_seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        key = extract_content_key(line)
        if key in local_seen:
            continue
        if global_seen is not None and key in global_seen:
            continue
        local_seen.add(key)
        if global_seen is not None:
            global_seen.add(key)
        deduped.append(line)
    return deduped
