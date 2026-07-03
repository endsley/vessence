"""Log-retention policy helpers for the memory janitor."""

from __future__ import annotations


LOG_MAX_AGE_DAYS = 21
SELF_IMPROVE_REPORT_MAX_AGE_DAYS = 14
PROTECTED_LOG_RETENTION_DAYS = 90

# Logs that should be kept much longer because they are audit trails/history.
PROTECTED_LOG_PATTERNS = {
    "janitor_consolidation_history",
    "jane_request_timing",
    "jane_writeback_timing",
    "job_queue",
}


def is_log_retention_candidate(filename: str) -> bool:
    return filename.endswith(".log") or filename.endswith(".jsonl")


def is_protected_log(filename: str) -> bool:
    return any(pattern in filename for pattern in PROTECTED_LOG_PATTERNS)


def log_cutoff_timestamp(now_ts: float, *, max_age_days: int, filename: str) -> float:
    retention_days = PROTECTED_LOG_RETENTION_DAYS if is_protected_log(filename) else max_age_days
    return now_ts - (retention_days * 86400)


def should_delete_log_file(filename: str, mtime: float, *, now_ts: float, max_age_days: int) -> bool:
    if not is_log_retention_candidate(filename):
        return False
    return mtime < log_cutoff_timestamp(now_ts, max_age_days=max_age_days, filename=filename)


def is_self_improve_report(filename: str) -> bool:
    return filename.startswith("self_improvement_") and filename.endswith(".md")


def should_delete_self_improve_report(
    filename: str,
    mtime: float,
    *,
    now_ts: float,
    max_age_days: int,
) -> bool:
    return is_self_improve_report(filename) and mtime < now_ts - (max_age_days * 86400)
