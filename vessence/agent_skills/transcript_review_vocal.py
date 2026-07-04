"""Vocal-summary payload helpers for transcript quality review."""
from __future__ import annotations


def vocal_severity_counts(issues: list[dict]) -> dict[str, int]:
    sev_counts = {"CRITICAL": 0, "MEDIUM": 0, "LOW": 0}
    for issue in issues:
        sev = (issue.get("severity") or "LOW").upper()
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
    return sev_counts


def spoken_vocal_severity(sev_counts: dict[str, int]) -> str:
    critical_n = sev_counts.get("CRITICAL", 0)
    medium_n = sev_counts.get("MEDIUM", 0)
    if critical_n > 0:
        return "critical"
    if medium_n > 0:
        return "medium"
    return "low"


def vocal_issue_breakdown(sev_counts: dict[str, int], issue_count: int) -> str:
    pieces = []
    if sev_counts.get("CRITICAL", 0):
        pieces.append(f"{sev_counts['CRITICAL']} critical")
    if sev_counts.get("MEDIUM", 0):
        pieces.append(f"{sev_counts['MEDIUM']} medium")
    low_n = sev_counts.get("LOW", 0)
    if low_n:
        pieces.append(f"{low_n} minor")
    return ", ".join(pieces) if pieces else f"{issue_count} items"


def top_vocal_issue(issues: list[dict]) -> dict:
    return next(
        (issue for issue in issues if (issue.get("severity") or "").upper() == "CRITICAL"),
        None,
    ) or next(
        (issue for issue in issues if (issue.get("severity") or "").upper() == "MEDIUM"),
        issues[0],
    )


def vocal_what_was_wrong(issues: list[dict], breakdown: str) -> str:
    top = top_vocal_issue(issues)
    top_desc = (top.get("issue") or "").strip().rstrip(".")

    if top_desc:
        return (
            f"Reviewing yesterday's conversations I spotted {breakdown} "
            f"issues. The most urgent was: {top_desc}"
        )
    return f"Reviewing yesterday's conversations I spotted {breakdown} issues."


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

    sev_counts = vocal_severity_counts(issues)
    spoken_sev = spoken_vocal_severity(sev_counts)
    breakdown = vocal_issue_breakdown(sev_counts, len(issues))

    return {
        "job": "Transcript Review",
        "what_was_wrong": vocal_what_was_wrong(issues, breakdown),
        "why_it_mattered": "These would have degraded your experience if left alone",
        "what_was_done": (
            "The full details and suggested fixes are in the transcript "
            "review report. Code fixes are disabled unless the job is run "
            "manually with apply-fixes."
        ),
        "severity": spoken_sev,
    }
