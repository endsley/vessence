"""Fast health summaries for the nightly memory janitor.

This module intentionally reads only small text/JSON artifacts.  It does not
import ChromaDB or janitor_memory.py, so Jane can answer "how did the memory
janitor do recently?" without waking the memory stack or spelunking logs by
hand.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

SUMMARY_HEADING_RE = re.compile(r"^## (?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*$")
MEMORY_JANITOR_LINE_RE = re.compile(
    r"^- .*?\*\*Memory Janitor\*\*\s+—\s+"
    r"(?P<status>.+?)\s+\((?P<elapsed>\d+)s\)\s+→\s+`(?P<log>[^`]+)`"
)
JANITOR_RUN_HEADER_RE = re.compile(
    r"^===== Run (?P<stamp>\d{4}-\d{2}-\d{2}T[\d:\.\-+]+) =====\s*$",
    re.MULTILINE,
)
SKIP_RE = re.compile(
    r"(?:WARNING|INFO):memory_janitor:(?P<reason>System (?:stressed|busy) — skipping janitor this cycle:? ?[^\n]*)"
)
PURGED_EXPIRED_RE = re.compile(r"Purged (?P<count>\d+) expired entries from short_term_memory")
VERIFY_RE = re.compile(
    r"Memory verification: (?P<checked>\d+) checked, (?P<stale>\d+) stale, (?P<fixed>\d+) fixed"
)
FINISH_RE = re.compile(
    r"Janitor finished\. Reduced (?P<reduced>\d+) facts \((?P<merges>\d+) merges\), "
    r"deleted (?P<junk>\d+) (?:known junk rows|stale/junk rows)"
    r"(?: and (?P<dupes>\d+) duplicate rows)?, normalized (?P<normalized>\d+) long-term rows\."
)
ARCHIVAL_STATUS_RE = re.compile(r"backfill: window archival result: .*['\"]status['\"]:\s*['\"](?P<status>[^'\"]+)")


@dataclass(frozen=True)
class OrchestratorJanitorRun:
    """Memory Janitor row from configs/self_improve_log.md."""

    run_at: dt.datetime
    status: str
    elapsed_s: int
    log_name: str


@dataclass(frozen=True)
class JanitorLogRun:
    """One self_improve_janitor_memory.log run block."""

    started_at: dt.datetime
    effective_status: str
    skip_reason: str | None = None
    expired_purged: int | None = None
    verification_checked: int | None = None
    verification_stale: int | None = None
    verification_fixed: int | None = None
    vectors_reduced: int | None = None
    merges_performed: int | None = None
    junk_deleted: int | None = None
    duplicate_deleted: int | None = None
    normalized_long_term: int | None = None
    archival_status: str | None = None


@dataclass(frozen=True)
class MatchedJanitorRun:
    """A nightly orchestrator row plus the matching janitor log block."""

    run_at: dt.datetime
    orchestrator_status: str
    elapsed_s: int
    effective_status: str
    detail_started_at: dt.datetime | None = None
    skip_reason: str | None = None
    expired_purged: int | None = None
    verification_checked: int | None = None
    verification_stale: int | None = None
    verification_fixed: int | None = None
    vectors_reduced: int | None = None
    merges_performed: int | None = None
    junk_deleted: int | None = None
    duplicate_deleted: int | None = None
    normalized_long_term: int | None = None
    archival_status: str | None = None


@dataclass(frozen=True)
class HealthReport:
    """Structured report returned by :func:`build_health_report`."""

    generated_at: dt.datetime
    window_label: str
    counts: dict[str, int]
    orchestrator_counts: dict[str, int]
    runs: list[MatchedJanitorRun]
    last_completed_report: dict[str, Any] | None
    unmatched_detail_runs: list[JanitorLogRun]
    sources: dict[str, str]


def _parse_datetime(value: str) -> dt.datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return parsed


def _fmt_dt(value: dt.datetime | None) -> str:
    if value is None:
        return "unknown"
    return value.strftime("%Y-%m-%d %H:%M")


def _none_if_missing(path: Path) -> str:
    return str(path) if path.exists() else f"{path} (missing)"


def parse_self_improve_log(text: str) -> list[OrchestratorJanitorRun]:
    """Extract Memory Janitor rows from the nightly summary markdown."""
    current_run_at: dt.datetime | None = None
    runs: list[OrchestratorJanitorRun] = []
    for line in text.splitlines():
        heading = SUMMARY_HEADING_RE.match(line)
        if heading:
            current_run_at = _parse_datetime(heading.group("stamp"))
            continue
        if current_run_at is None:
            continue
        row = MEMORY_JANITOR_LINE_RE.match(line)
        if row:
            runs.append(
                OrchestratorJanitorRun(
                    run_at=current_run_at,
                    status=row.group("status").strip(),
                    elapsed_s=int(row.group("elapsed")),
                    log_name=row.group("log"),
                )
            )
    return runs


def _last_int_match(pattern: re.Pattern[str], text: str, group: str) -> int | None:
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    return int(matches[-1].group(group))


def _parse_detail_block(started_at: dt.datetime, block: str) -> JanitorLogRun:
    skip = SKIP_RE.search(block)
    finish = FINISH_RE.search(block)
    verify = list(VERIFY_RE.finditer(block))
    archival = ARCHIVAL_STATUS_RE.search(block)

    if skip:
        effective_status = "skipped"
        skip_reason = skip.group("reason").strip()
    elif finish:
        effective_status = "completed"
        skip_reason = None
    elif "Traceback (most recent call last)" in block or "ERROR:memory_janitor:" in block:
        effective_status = "error"
        skip_reason = None
    else:
        effective_status = "incomplete"
        skip_reason = None

    latest_verify = verify[-1] if verify else None
    return JanitorLogRun(
        started_at=started_at,
        effective_status=effective_status,
        skip_reason=skip_reason,
        expired_purged=_last_int_match(PURGED_EXPIRED_RE, block, "count"),
        verification_checked=int(latest_verify.group("checked")) if latest_verify else None,
        verification_stale=int(latest_verify.group("stale")) if latest_verify else None,
        verification_fixed=int(latest_verify.group("fixed")) if latest_verify else None,
        vectors_reduced=int(finish.group("reduced")) if finish else None,
        merges_performed=int(finish.group("merges")) if finish else None,
        junk_deleted=int(finish.group("junk")) if finish else None,
        duplicate_deleted=int(finish.group("dupes") or 0) if finish else None,
        normalized_long_term=int(finish.group("normalized")) if finish else None,
        archival_status=archival.group("status") if archival else None,
    )


def parse_janitor_log(text: str) -> list[JanitorLogRun]:
    """Extract run-level health from self_improve_janitor_memory.log."""
    matches = list(JANITOR_RUN_HEADER_RE.finditer(text))
    runs: list[JanitorLogRun] = []
    for index, match in enumerate(matches):
        block_start = match.end()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        started_at = _parse_datetime(match.group("stamp"))
        runs.append(_parse_detail_block(started_at, text[block_start:block_end]))
    return runs


def _detail_to_match(summary: OrchestratorJanitorRun, detail: JanitorLogRun | None) -> MatchedJanitorRun:
    if detail is None:
        effective = summary.status if summary.status != "ok" else "unknown"
        return MatchedJanitorRun(
            run_at=summary.run_at,
            orchestrator_status=summary.status,
            elapsed_s=summary.elapsed_s,
            effective_status=effective,
        )

    return MatchedJanitorRun(
        run_at=summary.run_at,
        orchestrator_status=summary.status,
        elapsed_s=summary.elapsed_s,
        effective_status=detail.effective_status,
        detail_started_at=detail.started_at,
        skip_reason=detail.skip_reason,
        expired_purged=detail.expired_purged,
        verification_checked=detail.verification_checked,
        verification_stale=detail.verification_stale,
        verification_fixed=detail.verification_fixed,
        vectors_reduced=detail.vectors_reduced,
        merges_performed=detail.merges_performed,
        junk_deleted=detail.junk_deleted,
        duplicate_deleted=detail.duplicate_deleted,
        normalized_long_term=detail.normalized_long_term,
        archival_status=detail.archival_status,
    )


def match_orchestrator_to_details(
    summaries: Iterable[OrchestratorJanitorRun],
    details: Iterable[JanitorLogRun],
    *,
    window_hours: int = 12,
) -> tuple[list[MatchedJanitorRun], list[JanitorLogRun]]:
    """Match each summary row to the janitor log block that ran after it."""
    detail_runs = sorted(details, key=lambda item: item.started_at)
    used_detail_indexes: set[int] = set()
    matched: list[MatchedJanitorRun] = []

    for summary in sorted(summaries, key=lambda item: item.run_at):
        deadline = summary.run_at + dt.timedelta(hours=window_hours)
        detail_index: int | None = None
        for index, detail in enumerate(detail_runs):
            if index in used_detail_indexes:
                continue
            if summary.run_at <= detail.started_at <= deadline:
                detail_index = index
                break
        if detail_index is None:
            matched.append(_detail_to_match(summary, None))
            continue
        used_detail_indexes.add(detail_index)
        matched.append(_detail_to_match(summary, detail_runs[detail_index]))

    unmatched = [detail for index, detail in enumerate(detail_runs) if index not in used_detail_indexes]
    return matched, unmatched


def _select_summaries(
    summaries: list[OrchestratorJanitorRun],
    *,
    now: dt.datetime,
    runs: int | None,
    days: int | None,
) -> tuple[list[OrchestratorJanitorRun], str]:
    ordered = sorted(summaries, key=lambda item: item.run_at)
    if runs is not None:
        return ordered[-runs:], f"last {runs} orchestrated run(s)"

    if days is None:
        days = 7
    cutoff_date = (now.date() - dt.timedelta(days=max(days - 1, 0)))
    selected = [item for item in ordered if item.run_at.date() >= cutoff_date]
    return selected, f"since {cutoff_date.isoformat()}"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except FileNotFoundError:
        return ""


def _last_completed_report(path: Path, now: dt.datetime) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None

    last_run_raw = payload.get("last_run")
    last_run_dt: dt.datetime | None = None
    age_hours: float | None = None
    if isinstance(last_run_raw, str):
        try:
            last_run_dt = _parse_datetime(last_run_raw)
            age_hours = round((now - last_run_dt).total_seconds() / 3600, 1)
        except Exception:
            pass

    normalization = payload.get("long_term_normalization") or {}
    return {
        "last_run": last_run_raw,
        "age_hours": age_hours,
        "vectors_reduced": payload.get("vectors_reduced"),
        "merges_performed": payload.get("merges_performed"),
        "forgettable_memories_purged": payload.get("forgettable_memories_purged"),
        "known_junk_deleted": payload.get("known_junk_deleted"),
        "exact_duplicate_deleted": payload.get("exact_duplicate_deleted"),
        "normalization_reviewed": normalization.get("reviewed"),
        "normalization_rewritten": normalization.get("rewritten"),
        "normalization_split": normalization.get("split"),
    }


def build_health_report(
    *,
    vessence_home: Path,
    data_home: Path,
    runs: int | None = 7,
    days: int | None = None,
    now: dt.datetime | None = None,
) -> HealthReport:
    """Build a fast report from summary markdown + janitor text log."""
    now = now or dt.datetime.now()
    summary_path = vessence_home / "configs" / "self_improve_log.md"
    janitor_log_path = data_home / "logs" / "self_improve_janitor_memory.log"
    janitor_report_path = data_home / "logs" / "janitor_report.json"

    summaries = parse_self_improve_log(_read_text(summary_path))
    selected_summaries, window_label = _select_summaries(summaries, now=now, runs=runs, days=days)
    details = parse_janitor_log(_read_text(janitor_log_path))
    matched, unmatched = match_orchestrator_to_details(selected_summaries, details)

    if selected_summaries:
        start = selected_summaries[0].run_at
        end = selected_summaries[-1].run_at + dt.timedelta(hours=12)
        unmatched = [item for item in unmatched if start <= item.started_at <= end]

    return HealthReport(
        generated_at=now,
        window_label=window_label,
        counts=dict(Counter(item.effective_status for item in matched)),
        orchestrator_counts=dict(Counter(item.orchestrator_status for item in matched)),
        runs=matched,
        last_completed_report=_last_completed_report(janitor_report_path, now),
        unmatched_detail_runs=unmatched,
        sources={
            "self_improve_log": _none_if_missing(summary_path),
            "janitor_log": _none_if_missing(janitor_log_path),
            "janitor_report": _none_if_missing(janitor_report_path),
        },
    )


def _dict_with_iso_datetimes(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_dict_with_iso_datetimes(item) for item in value]
    if isinstance(value, dict):
        return {key: _dict_with_iso_datetimes(item) for key, item in value.items()}
    return value


def report_to_dict(report: HealthReport) -> dict[str, Any]:
    """Return a JSON-serializable report dictionary."""
    return _dict_with_iso_datetimes(asdict(report))


def _count_phrase(counts: dict[str, int]) -> str:
    if not counts:
        return "no runs found"
    order = ["completed", "skipped", "timeout", "error", "incomplete", "unknown"]
    pieces = [f"{counts[key]} {key}" for key in order if counts.get(key)]
    pieces.extend(f"{value} {key}" for key, value in sorted(counts.items()) if key not in order)
    return ", ".join(pieces)


def _run_metric_suffix(run: MatchedJanitorRun) -> str:
    if run.skip_reason:
        return f" — {run.skip_reason}"
    bits: list[str] = []
    if run.expired_purged is not None:
        bits.append(f"purged={run.expired_purged}")
    if run.verification_checked is not None:
        bits.append(
            "verified="
            f"{run.verification_checked}/{run.verification_stale or 0} stale/"
            f"{run.verification_fixed or 0} fixed"
        )
    if run.vectors_reduced is not None:
        bits.append(f"reduced={run.vectors_reduced}")
    if run.merges_performed is not None:
        bits.append(f"merges={run.merges_performed}")
    if run.normalized_long_term is not None:
        bits.append(f"normalized={run.normalized_long_term}")
    if run.archival_status:
        bits.append(f"archival={run.archival_status}")
    return " — " + ", ".join(bits) if bits else ""


def render_markdown(report: HealthReport) -> str:
    """Render a concise human-readable health report."""
    lines = [f"Memory janitor health ({report.window_label})"]
    lines.append(f"- Effective outcomes: {_count_phrase(report.counts)}.")
    lines.append(f"- Orchestrator statuses: {_count_phrase(report.orchestrator_counts)}.")

    last = report.last_completed_report
    if last and last.get("last_run"):
        age = last.get("age_hours")
        age_text = f", {age:.1f}h old" if isinstance(age, (int, float)) else ""
        lines.append(
            "- Last full janitor report: "
            f"{last['last_run']}{age_text}; "
            f"purged={last.get('forgettable_memories_purged')}, "
            f"merges={last.get('merges_performed')}, "
            f"reduced={last.get('vectors_reduced')}, "
            f"normalization_reviewed={last.get('normalization_reviewed')}."
        )
    else:
        lines.append("- Last full janitor report: unavailable.")

    if report.runs:
        lines.append("")
        lines.append("Recent orchestrated runs:")
        for run in reversed(report.runs):
            detail_start = f", detail {_fmt_dt(run.detail_started_at)}" if run.detail_started_at else ""
            lines.append(
                f"- {_fmt_dt(run.run_at)}: orchestrator={run.orchestrator_status} "
                f"({run.elapsed_s}s), effective={run.effective_status}{detail_start}"
                f"{_run_metric_suffix(run)}"
            )
    else:
        lines.append("")
        lines.append("Recent orchestrated runs: none found in self_improve_log.md.")

    if report.unmatched_detail_runs:
        lines.append("")
        lines.append("Unmatched janitor log blocks in this window:")
        for detail in reversed(report.unmatched_detail_runs[-5:]):
            suffix = f" — {detail.skip_reason}" if detail.skip_reason else ""
            lines.append(f"- {_fmt_dt(detail.started_at)}: {detail.effective_status}{suffix}")

    lines.append("")
    lines.append("Sources:")
    for label, path in report.sources.items():
        lines.append(f"- {label}: {path}")
    return "\n".join(lines)


def default_vessence_home() -> Path:
    return Path(os.environ.get("VESSENCE_HOME", Path(__file__).resolve().parents[2]))


def default_data_home() -> Path:
    return Path(os.environ.get("VESSENCE_DATA_HOME", Path.home() / "ambient" / "vessence-data"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize recent memory janitor performance quickly.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--runs", type=int, default=7, help="number of latest orchestrated runs to include")
    group.add_argument("--days", type=int, help="calendar-day window to include instead of latest runs")
    parser.add_argument("--vessence-home", type=Path, default=default_vessence_home())
    parser.add_argument("--data-home", type=Path, default=default_data_home())
    parser.add_argument("--json", action="store_true", help="emit structured JSON instead of markdown")
    args = parser.parse_args(argv)

    runs = None if args.days is not None else args.runs
    report = build_health_report(
        vessence_home=args.vessence_home,
        data_home=args.data_home,
        runs=runs,
        days=args.days,
    )
    if args.json:
        print(json.dumps(report_to_dict(report), indent=2, sort_keys=True))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
