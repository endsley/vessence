"""Text, age, and deduplication helpers for memory retrieval."""

from __future__ import annotations

import datetime


def parse_memory_datetime(value: object) -> datetime.datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed
    except Exception:
        return None


def _metadata_timestamp(meta: dict) -> object:
    return (meta or {}).get("timestamp", (meta or {}).get("created_at", ""))


def is_expired(meta: dict) -> bool:
    expires_at = (meta or {}).get("expires_at")
    if not expires_at:
        return False

    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    if isinstance(expires_at, (int, float)):
        return expires_at < now_ts

    expires_dt = parse_memory_datetime(expires_at)
    if expires_dt is None:
        return False
    return expires_dt.timestamp() < now_ts


def is_too_old(meta: dict, max_days: int = 3) -> bool:
    """Return True if the entry is older than max_days. Entries without timestamps pass through."""
    ts = parse_memory_datetime(_metadata_timestamp(meta))
    if ts is None:
        return False
    age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 86400
    return age > max_days


def age_days(meta: dict) -> float | None:
    ts = parse_memory_datetime(_metadata_timestamp(meta))
    if ts is None:
        return None
    return (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 86400


def is_none_content(doc: str) -> bool:
    """Return True if the document content is a None/empty sentinel."""
    stripped = (doc or "").strip()
    return stripped in ("None", "none", "", "null", "N/A")


def recency_label(ts_str: str) -> str:
    if not ts_str or ts_str == "Unknown Time":
        return "unknown age"
    ts = parse_memory_datetime(ts_str)
    if ts is None:
        return "unknown age"
    delta = datetime.datetime.now(datetime.timezone.utc) - ts
    secs = delta.total_seconds()
    if secs < 0:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


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
