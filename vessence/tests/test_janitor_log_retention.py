from memory.v1.janitor_log_retention import (
    LOG_MAX_AGE_DAYS,
    PROTECTED_LOG_RETENTION_DAYS,
    SELF_IMPROVE_REPORT_MAX_AGE_DAYS,
    is_log_retention_candidate,
    is_protected_log,
    is_self_improve_report,
    retention_seconds,
    should_delete_log_file,
    should_delete_self_improve_report,
)


def test_log_retention_candidates_and_protected_names():
    assert is_log_retention_candidate("jane.log")
    assert is_log_retention_candidate("history.jsonl")
    assert not is_log_retention_candidate("notes.md")
    assert is_protected_log("janitor_consolidation_history.jsonl")
    assert is_protected_log("jane_request_timing.log")
    assert not is_protected_log("ordinary.log")


def test_should_delete_log_file_uses_default_and_protected_cutoffs():
    now_ts = 1_000_000.0
    assert retention_seconds(LOG_MAX_AGE_DAYS) == LOG_MAX_AGE_DAYS * 86400
    old_default = now_ts - ((LOG_MAX_AGE_DAYS + 1) * 86400)
    old_protected = now_ts - ((PROTECTED_LOG_RETENTION_DAYS + 1) * 86400)
    protected_under_default_cutoff = now_ts - ((LOG_MAX_AGE_DAYS + 1) * 86400)

    assert should_delete_log_file("ordinary.log", old_default, now_ts=now_ts, max_age_days=LOG_MAX_AGE_DAYS)
    assert not should_delete_log_file(
        "janitor_consolidation_history.jsonl",
        protected_under_default_cutoff,
        now_ts=now_ts,
        max_age_days=LOG_MAX_AGE_DAYS,
    )
    assert should_delete_log_file(
        "janitor_consolidation_history.jsonl",
        old_protected,
        now_ts=now_ts,
        max_age_days=LOG_MAX_AGE_DAYS,
    )
    assert not should_delete_log_file("ordinary.txt", old_default, now_ts=now_ts, max_age_days=LOG_MAX_AGE_DAYS)


def test_self_improve_report_retention_requires_report_name_and_age():
    now_ts = 1_000_000.0
    old_report = now_ts - ((SELF_IMPROVE_REPORT_MAX_AGE_DAYS + 1) * 86400)
    recent_report = now_ts - ((SELF_IMPROVE_REPORT_MAX_AGE_DAYS - 1) * 86400)

    assert is_self_improve_report("self_improvement_20260702.md")
    assert not is_self_improve_report("self_improvement_20260702.txt")
    assert should_delete_self_improve_report(
        "self_improvement_20260702.md",
        old_report,
        now_ts=now_ts,
        max_age_days=SELF_IMPROVE_REPORT_MAX_AGE_DAYS,
    )
    assert not should_delete_self_improve_report(
        "self_improvement_20260702.md",
        recent_report,
        now_ts=now_ts,
        max_age_days=SELF_IMPROVE_REPORT_MAX_AGE_DAYS,
    )
