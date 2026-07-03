from agent_skills import janitor_system
from agent_skills.janitor_system_rules import (
    LOG_ACTION_KEEP,
    LOG_ACTION_REMOVE,
    LOG_ACTION_TRUNCATE,
    is_stale_mtime,
    log_cleanup_action,
    should_rotate_log,
    trim_tail_to_line_boundary,
    truncated_log_payload,
)


def test_janitor_system_exposes_rule_helpers():
    assert janitor_system._should_rotate_log is should_rotate_log
    assert janitor_system._is_stale_mtime is is_stale_mtime
    assert janitor_system._log_cleanup_action is log_cleanup_action
    assert janitor_system._trim_tail_to_line_boundary is trim_tail_to_line_boundary
    assert janitor_system._truncated_log_payload is truncated_log_payload


def test_should_rotate_log_uses_strict_max_size_threshold():
    max_mb = 50
    assert not should_rotate_log(50 * 1024 * 1024, max_mb)
    assert should_rotate_log(50 * 1024 * 1024 + 1, max_mb)


def test_log_cleanup_action_removes_stale_truncates_active_large_and_keeps_small():
    cutoff = 1_000.0
    assert log_cleanup_action(mtime=999.9, size_bytes=1, cutoff_ts=cutoff) == LOG_ACTION_REMOVE
    assert log_cleanup_action(mtime=1000.0, size_bytes=1024 * 1024 + 1, cutoff_ts=cutoff) == (
        LOG_ACTION_TRUNCATE
    )
    assert log_cleanup_action(mtime=1000.0, size_bytes=1024 * 1024, cutoff_ts=cutoff) == LOG_ACTION_KEEP
    assert is_stale_mtime(999.9, cutoff)
    assert not is_stale_mtime(1000.0, cutoff)


def test_trim_tail_to_line_boundary_discards_partial_first_line():
    assert trim_tail_to_line_boundary(b"partial\nfull line\n") == b"full line\n"
    assert trim_tail_to_line_boundary(b"already complete enough") == b"already complete enough"
    assert trim_tail_to_line_boundary(b"\nstarts after blank\n") == b"starts after blank\n"


def test_truncated_log_payload_preserves_header_shape_and_trimmed_tail():
    assert truncated_log_payload(
        b"partial\nline two\n",
        keep_bytes=200 * 1024,
        ctime_text="DATE",
    ) == b"--- Truncated at DATE (kept last 200KB) ---\nline two\n"
