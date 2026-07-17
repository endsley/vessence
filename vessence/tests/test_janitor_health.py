import datetime as dt
import json

from memory.v1.janitor_health import (
    build_health_report,
    match_orchestrator_to_details,
    parse_janitor_log,
    parse_self_improve_log,
    render_markdown,
)


def test_parse_self_improve_log_extracts_memory_janitor_rows():
    text = """
# Nightly Self-Improvement Log

## 2026-07-14 23:30

- ✅ **Code Auditor** — ok (0s) → `self_improve_nightly_code_auditor.log`
- ✅ **Memory Janitor** — ok (1s) → `self_improve_janitor_memory.log`

## 2026-07-15 23:30

- ⏱️ **Memory Janitor** — timeout (3600s) → `self_improve_janitor_memory.log`
"""

    runs = parse_self_improve_log(text)

    assert [run.status for run in runs] == ["ok", "timeout"]
    assert runs[0].run_at == dt.datetime(2026, 7, 14, 23, 30)
    assert runs[1].elapsed_s == 3600


def test_parse_janitor_log_classifies_completed_skipped_and_incomplete_runs():
    text = """
===== Run 2026-07-09T01:22:06.832849 =====
INFO:memory_janitor:backfill: window archival result: {'status': 'nothing-new', 'watermark': 7313}
INFO:memory_janitor:Purged 5 expired entries from short_term_memory.
INFO:memory_janitor:Memory verification: 20 checked, 0 stale, 0 fixed
INFO:memory_janitor:Janitor finished. Reduced 0 facts (0 merges), deleted 0 stale/junk rows and 0 duplicate rows, normalized 0 long-term rows.

===== Run 2026-07-11T23:48:40.268542 =====
WARNING:memory_janitor:System stressed — skipping janitor this cycle: swap already active: 38.5% > 10.0%

===== Run 2026-07-12T23:49:25.035912 =====
INFO:memory_janitor:backfill: window archival result: {'status': 'started'}
"""

    runs = parse_janitor_log(text)

    assert [run.effective_status for run in runs] == ["completed", "skipped", "incomplete"]
    assert runs[0].expired_purged == 5
    assert runs[0].verification_checked == 20
    assert runs[0].verification_stale == 0
    assert runs[0].vectors_reduced == 0
    assert runs[0].duplicate_deleted == 0
    assert runs[0].archival_status == "nothing-new"
    assert "swap already active" in runs[1].skip_reason


def test_match_orchestrator_to_details_uses_post_orchestrator_window():
    summaries = parse_self_improve_log(
        """
## 2026-07-14 23:30
- ✅ **Memory Janitor** — ok (1s) → `self_improve_janitor_memory.log`
## 2026-07-15 23:30
- ✅ **Memory Janitor** — ok (1s) → `self_improve_janitor_memory.log`
"""
    )
    details = parse_janitor_log(
        """
===== Run 2026-07-15T00:06:33.649752 =====
WARNING:memory_janitor:System stressed — skipping janitor this cycle: swap already active: 32.1% > 10.0%
===== Run 2026-07-16T00:07:19.913657 =====
WARNING:memory_janitor:System stressed — skipping janitor this cycle: swap already active: 47.1% > 10.0%
"""
    )

    matched, unmatched = match_orchestrator_to_details(summaries, details)

    assert not unmatched
    assert [run.effective_status for run in matched] == ["skipped", "skipped"]
    assert matched[0].detail_started_at == dt.datetime(2026, 7, 15, 0, 6, 33, 649752)
    assert matched[1].detail_started_at == dt.datetime(2026, 7, 16, 0, 7, 19, 913657)


def test_build_health_report_and_render_are_fast_log_only(tmp_path):
    vessence_home = tmp_path / "vessence"
    data_home = tmp_path / "vessence-data"
    (vessence_home / "configs").mkdir(parents=True)
    (data_home / "logs").mkdir(parents=True)
    (vessence_home / "configs" / "self_improve_log.md").write_text(
        """
## 2026-07-09 01:00
- ✅ **Memory Janitor** — ok (782s) → `self_improve_janitor_memory.log`
## 2026-07-15 23:30
- ✅ **Memory Janitor** — ok (1s) → `self_improve_janitor_memory.log`
"""
    )
    (data_home / "logs" / "self_improve_janitor_memory.log").write_text(
        """
===== Run 2026-07-09T01:22:06.832849 =====
INFO:memory_janitor:Purged 5 expired entries from short_term_memory.
INFO:memory_janitor:Memory verification: 20 checked, 0 stale, 0 fixed
INFO:memory_janitor:Janitor finished. Reduced 0 facts (0 merges), deleted 0 stale/junk rows and 0 duplicate rows, normalized 0 long-term rows.
===== Run 2026-07-16T00:07:19.913657 =====
WARNING:memory_janitor:System stressed — skipping janitor this cycle: swap already active: 47.1% > 10.0%
"""
    )
    (data_home / "logs" / "janitor_report.json").write_text(
        json.dumps(
            {
                "last_run": "2026-07-09T01:32:22.504756",
                "vectors_reduced": 0,
                "merges_performed": 0,
                "forgettable_memories_purged": 5,
                "long_term_normalization": {"reviewed": 24, "rewritten": 0, "split": 0},
            }
        )
    )

    report = build_health_report(
        vessence_home=vessence_home,
        data_home=data_home,
        runs=2,
        now=dt.datetime(2026, 7, 16, 8, 0),
    )
    rendered = render_markdown(report)

    assert report.counts == {"completed": 1, "skipped": 1}
    assert report.orchestrator_counts == {"ok": 2}
    assert report.last_completed_report["age_hours"] == 174.5
    assert "Effective outcomes: 1 completed, 1 skipped." in rendered
    assert "swap already active" in rendered
    assert "Last full janitor report: 2026-07-09T01:32:22.504756" in rendered
