"""Render self-improvement log entries for Stage 3 context injection."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


DEFAULT_VOCAL_LOG_PATH = "$VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl"
DEFAULT_TECH_LOGS = "$VESSENCE_DATA_HOME/logs/self_improve_*.log"
DEFAULT_LATEST_REPORT = "$VESSENCE_HOME/configs/self_improvement_latest.md"
SELF_IMPROVEMENT_CONTEXT_END = "[END SELF IMPROVEMENT CONTEXT]"


def _context_header_lines(*, log_path: str, tech_logs: str, latest_report: str) -> list[str]:
    return [
        "\n\n[SELF IMPROVEMENT CONTEXT]",
        f"Readable latest report: {latest_report}",
        f"Vocal summary log file: {log_path}",
        f"Technical job logs: {tech_logs}",
    ]


def _job_category_summary(entries: Sequence[dict]) -> str:
    by_job = Counter(entry.get("job", "?") for entry in entries)
    return ", ".join(f"{job} ({count})" for job, count in by_job.most_common())


def _entry_reference_line(index: int, entry: dict) -> str:
    ts = entry.get("timestamp", "?")
    job = entry.get("job", "?")
    severity = entry.get("severity", "info")
    summary = entry.get("summary", "").strip()
    return f"{index}. [{ts} | {job} | {severity}] {summary}"


def _empty_context_lines(*, log_path: str, tech_logs: str, latest_report: str) -> list[str]:
    lines = _context_header_lines(
        log_path=log_path,
        tech_logs=tech_logs,
        latest_report=latest_report,
    )
    lines.append(
        "No recent self-improvement entries found (empty log or "
        "older than 14 days). Tell the user nothing's been logged "
        "yet and the nightly job may not have run recently."
    )
    lines.append(SELF_IMPROVEMENT_CONTEXT_END)
    return lines


def _voice_response_style_message(entries: Sequence[dict]) -> str:
    return (
        "RESPONSE STYLE — CRITICAL. The user is on voice and doesn't "
        "want a long recital. Your reply should be CONVERSATIONAL:\n"
        "  0) When the user asks for the most recent self-improvement "
        "or asks what happened last night, read the readable latest "
        "report first if exact per-stage details are needed.\n"
        "  1) Open with a one-sentence headline: how many changes in "
        "total and roughly what categories (e.g. 'I logged 7 changes "
        "overnight — mostly transcript review fixes plus a couple doc "
        "tweaks').\n"
        "  2) Ask which one the user wants to hear about, offering by "
        "NUMBER: 'want me to walk through number 3, the timer bug?'\n"
        "  3) Do NOT enumerate every entry. Do NOT read timestamps, "
        "job names, severity labels, or file paths aloud. Do NOT use "
        "bullet points or lists — speak it like a friend giving a "
        "quick update.\n"
        "  4) If the user asks for 'number N', jump to entry N below "
        "and speak its summary conversationally (one to three "
        "sentences).\n"
        "  5) If the user asks about a specific topic (timers, "
        "transcripts, etc.), filter to matching entries and apply "
        "the same short-headline-plus-offer pattern.\n\n"
        f"Total entries in context window: {len(entries)} "
        f"(most recent first). Job categories: "
        + _job_category_summary(entries)
        + "."
    )


def _numbered_entry_reference_lines(entries: Sequence[dict]) -> list[str]:
    lines = ["", "Entries (numbered for drill-down reference):"]
    lines.extend(_entry_reference_line(index, entry) for index, entry in enumerate(entries, 1))
    lines.append(SELF_IMPROVEMENT_CONTEXT_END)
    return lines


def build_self_improvement_context_block(
    entries: Sequence[dict],
    *,
    log_path: str = DEFAULT_VOCAL_LOG_PATH,
    tech_logs: str = DEFAULT_TECH_LOGS,
    latest_report: str = DEFAULT_LATEST_REPORT,
) -> str:
    if not entries:
        return "\n".join(_empty_context_lines(
            log_path=log_path,
            tech_logs=tech_logs,
            latest_report=latest_report,
        ))

    lines = _context_header_lines(
        log_path=log_path,
        tech_logs=tech_logs,
        latest_report=latest_report,
    )
    lines.append(_voice_response_style_message(entries))
    lines.extend(_numbered_entry_reference_lines(entries))
    return "\n".join(lines)
