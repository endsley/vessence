"""Render self-improvement log entries for Stage 3 context injection."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


DEFAULT_VOCAL_LOG_PATH = "$VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl"
DEFAULT_TECH_LOGS = "$VESSENCE_DATA_HOME/logs/self_improve_*.log"
DEFAULT_LATEST_REPORT = "$VESSENCE_HOME/configs/self_improvement_latest.md"


def build_self_improvement_context_block(
    entries: Sequence[dict],
    *,
    log_path: str = DEFAULT_VOCAL_LOG_PATH,
    tech_logs: str = DEFAULT_TECH_LOGS,
    latest_report: str = DEFAULT_LATEST_REPORT,
) -> str:
    if not entries:
        return (
            "\n\n[SELF IMPROVEMENT CONTEXT]\n"
            f"Readable latest report: {latest_report}\n"
            f"Vocal summary log file: {log_path}\n"
            f"Technical job logs: {tech_logs}\n"
            "No recent self-improvement entries found (empty log or "
            "older than 14 days). Tell the user nothing's been logged "
            "yet and the nightly job may not have run recently.\n"
            "[END SELF IMPROVEMENT CONTEXT]"
        )

    by_job = Counter(entry.get("job", "?") for entry in entries)
    lines = ["\n\n[SELF IMPROVEMENT CONTEXT]"]
    lines.append(f"Readable latest report: {latest_report}")
    lines.append(f"Vocal summary log file: {log_path}")
    lines.append(f"Technical job logs: {tech_logs}")
    lines.append(
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
        + ", ".join(f"{job} ({count})" for job, count in by_job.most_common())
        + "."
    )
    lines.append("")
    lines.append("Entries (numbered for drill-down reference):")
    for index, entry in enumerate(entries, 1):
        ts = entry.get("timestamp", "?")
        job = entry.get("job", "?")
        severity = entry.get("severity", "info")
        summary = entry.get("summary", "").strip()
        lines.append(f"{index}. [{ts} | {job} | {severity}] {summary}")
    lines.append("[END SELF IMPROVEMENT CONTEXT]")
    return "\n".join(lines)
