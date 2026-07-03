"""Vocal-summary payload helpers for transcript quality review."""
from __future__ import annotations


def build_vocal_summary_payload(issues: list[dict]) -> dict:
    if not issues:
        return {
            "job": "Transcript Review",
            "summary": (
                "I reviewed yesterday's conversations and nothing looked "
                "off — all turns handled cleanly."
            ),
            "severity": "info",
        }

    sev_counts = {"CRITICAL": 0, "MEDIUM": 0, "LOW": 0}
    for issue in issues:
        sev = (issue.get("severity") or "LOW").upper()
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    critical_n = sev_counts.get("CRITICAL", 0)
    medium_n = sev_counts.get("MEDIUM", 0)

    if critical_n > 0:
        spoken_sev = "critical"
    elif medium_n > 0:
        spoken_sev = "medium"
    else:
        spoken_sev = "low"

    pieces = []
    if critical_n:
        pieces.append(f"{critical_n} critical")
    if medium_n:
        pieces.append(f"{medium_n} medium")
    low_n = sev_counts.get("LOW", 0)
    if low_n:
        pieces.append(f"{low_n} minor")

    breakdown = ", ".join(pieces) if pieces else f"{len(issues)} items"

    top = next(
        (issue for issue in issues if (issue.get("severity") or "").upper() == "CRITICAL"),
        None,
    ) or next(
        (issue for issue in issues if (issue.get("severity") or "").upper() == "MEDIUM"),
        issues[0],
    )
    top_desc = (top.get("issue") or "").strip().rstrip(".")

    if top_desc:
        what_was_wrong = (
            f"Reviewing yesterday's conversations I spotted {breakdown} "
            f"issues. The most urgent was: {top_desc}"
        )
    else:
        what_was_wrong = (
            f"Reviewing yesterday's conversations I spotted {breakdown} "
            f"issues."
        )

    return {
        "job": "Transcript Review",
        "what_was_wrong": what_was_wrong,
        "why_it_mattered": "These would have degraded your experience if left alone",
        "what_was_done": (
            "The full details and suggested fixes are in the transcript "
            "review report. Code fixes are disabled unless the job is run "
            "manually with apply-fixes."
        ),
        "severity": spoken_sev,
    }
