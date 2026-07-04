"""Formatting helpers for transcript quality review."""
from __future__ import annotations

import datetime as dt
import json
import re


PIPELINE_RELEVANT_MARKERS = (
    "stage1_classifier",
    "stage2",
    "pipeline",
    "timer handler",
    "resolver",
    "stage3_escalate",
    "ERROR",
    "WARNING",
    "brain",
    "v2 stage2",
    "conv_end",
)

ANDROID_RELEVANT_CATEGORIES = (
    "voice_flow",
    "tool_handler",
    "wakeword",
)


def strip_prompt_dump_context(message: str) -> str:
    if "[END CURRENT CONVERSATION STATE]" in message:
        message = message.split("[END CURRENT CONVERSATION STATE]", 1)[1].strip()
    return message


def prompt_dump_turn(record: dict, date_str: str) -> dict | None:
    timestamp = record.get("timestamp", "")
    if not timestamp.startswith(date_str):
        return None
    message = strip_prompt_dump_context(record.get("message", ""))
    return {
        "time": timestamp,
        "session": record.get("session_id", "")[:12],
        "user_msg": message[:500],
        "mode": record.get("mode", ""),
    }


def pipeline_event_line(
    line: str,
    date_str: str,
    relevant_markers: tuple[str, ...] = PIPELINE_RELEVANT_MARKERS,
) -> str | None:
    if not line.startswith(date_str):
        return None
    if not any(marker in line for marker in relevant_markers):
        return None
    return line.rstrip()[:300]


def android_event_line(
    record: dict,
    date_str: str,
    relevant_categories: tuple[str, ...] = ANDROID_RELEVANT_CATEGORIES,
) -> str | None:
    iso_prefix = date_str + "T"
    timestamp = record.get("timestamp", "")
    if not timestamp.startswith(iso_prefix):
        return None
    category = record.get("category", "")
    if category not in relevant_categories:
        return None
    message = record.get("message", "")
    extra = ""
    if category == "tool_handler":
        extra = f" detail={record.get('detail', '')}"
    elif category == "voice_flow":
        extra_parts = []
        for key in ("path", "reason", "text_len", "fromVoice"):
            if key in record:
                extra_parts.append(f"{key}={record[key]}")
        extra = " " + " ".join(extra_parts)
    return f"{timestamp} [{category}] {message}{extra}"[:300]


def extract_json_array_text(output: str) -> str | None:
    match = re.search(r"\[[\s\S]*\]", output)
    return match.group() if match else None


def parse_codex_issues(output: str) -> list[dict] | None:
    json_text = extract_json_array_text(output)
    if json_text is None:
        return None
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


def build_condensed_context(
    turns: list[dict],
    pipeline_events: list[str],
    android_events: list[str],
    max_chars: int = 80_000,
) -> str:
    """Build a condensed context string for Codex, within token budget."""
    sections = []

    turn_lines = []
    for turn in turns:
        user = turn["user_msg"][:300]
        turn_lines.append(f"[{turn['time']}] ({turn['session']}) {user}")
    sections.append(
        "## User Turns (chronological)\n" + "\n".join(turn_lines)
    )

    sections.append(
        "## Server Pipeline Events\n" + "\n".join(pipeline_events[-500:])
    )

    sections.append(
        "## Android Client Events\n" + "\n".join(android_events[-300:])
    )

    combined = "\n\n".join(sections)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n[TRUNCATED]"
    return combined


def codex_report_header(date_str: str, generated: dt.datetime) -> str:
    return (
        f"# Transcript Quality Review — {date_str}\n\n"
        f"Generated: {generated.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )


def codex_issue_section(index: int, issue: dict) -> str:
    sev = issue.get("severity", "?")
    parts = [
        (
            f"## Issue {index} [{sev}]\n\n"
            f"**Turn:** {issue.get('turn_time', '?')}\n"
            f"**User said:** {issue.get('user_msg_snippet', '?')}\n\n"
            f"**Problem:** {issue.get('issue', '?')}\n\n"
            f"**Root cause:** {issue.get('root_cause', '?')}\n\n"
            f"**Suggested fix:** {issue.get('suggested_fix', '?')}\n\n"
            f"**Log evidence:**\n"
        )
    ]
    for line in issue.get("relevant_log_lines", []):
        parts.append(f"```\n{line}\n```\n")
    parts.append("\n---\n\n")
    return "".join(parts)


def build_codex_report_markdown(
    issues: list[dict],
    date_str: str,
    *,
    generated_at: dt.datetime | None = None,
) -> str:
    """Render Codex transcript-review findings as Markdown."""
    generated = generated_at or dt.datetime.now()
    header = codex_report_header(date_str, generated)

    if not issues:
        return header + "No issues found. All turns look reasonable.\n"

    return header + "".join(codex_issue_section(i, issue) for i, issue in enumerate(issues, 1))
