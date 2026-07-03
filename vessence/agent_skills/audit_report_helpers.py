"""Pure report summary helpers for audit notification scripts."""
from __future__ import annotations

import re
from typing import Any


def extract_notification_brief(report: str, max_chars: int = 2200) -> str:
    text = re.sub(r"^#.*$", "", report, flags=re.MULTILINE).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def extract_health_summary(report: str, max_chars: int = 280) -> str:
    lines = [line.strip() for line in report.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        lowered = line.lower().strip("*# :")
        if lowered != "health summary":
            continue
        summary_lines: list[str] = []
        for next_line in lines[index + 1:]:
            if next_line.startswith("**") or next_line.startswith("#"):
                break
            summary_lines.append(next_line)
            if len(" ".join(summary_lines)) >= max_chars:
                break
        if summary_lines:
            return " ".join(summary_lines)[:max_chars]
    return (lines[0] if lines else "").replace("#", "").strip()[:max_chars]


def audit_announcement_message(*, local_stamp: str, brief: str) -> str:
    return (
        f"**Morning audit summary**\n"
        f"Latest audit run: {local_stamp}\n\n"
        f"{brief}"
    )


def audit_announcement_payload(
    *,
    timestamp: str,
    announcement_id: str,
    message: str,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "type": "queue_progress",
        "id": announcement_id,
        "message": message,
        "final": True,
    }


def audit_notification_state(
    *,
    today: str,
    generated_at: str,
    announcement_id: str,
) -> dict[str, str]:
    return {
        "last_notified_date": today,
        "last_report_generated_at": generated_at,
        "announcement_id": announcement_id,
    }
