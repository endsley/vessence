"""Pure cleanup policy helpers for janitor_system.py."""
from __future__ import annotations


LOG_ACTION_REMOVE = "remove"
LOG_ACTION_TRUNCATE = "truncate"
LOG_ACTION_KEEP = "keep"


def should_rotate_log(size_bytes: int, max_log_size_mb: int) -> bool:
    return size_bytes > (max_log_size_mb * 1024 * 1024)


def is_stale_mtime(mtime: float, cutoff_ts: float) -> bool:
    return mtime < cutoff_ts


def log_cleanup_action(
    *,
    mtime: float,
    size_bytes: int,
    cutoff_ts: float,
    active_large_bytes: int = 1024 * 1024,
) -> str:
    if is_stale_mtime(mtime, cutoff_ts):
        return LOG_ACTION_REMOVE
    if size_bytes > active_large_bytes:
        return LOG_ACTION_TRUNCATE
    return LOG_ACTION_KEEP


def trim_tail_to_line_boundary(tail: bytes) -> bytes:
    newline_index = tail.find(b"\n")
    if newline_index == -1:
        return tail
    return tail[newline_index + 1 :]


def truncated_log_payload(tail: bytes, *, keep_bytes: int, ctime_text: str) -> bytes:
    trimmed = trim_tail_to_line_boundary(tail)
    header = f"--- Truncated at {ctime_text} (kept last {keep_bytes // 1024}KB) ---\n"
    return header.encode() + trimmed
