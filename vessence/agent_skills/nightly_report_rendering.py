"""Pure rendering helpers for nightly self-improvement reports."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from agent_skills.nightly_report_summaries import bullet


def status_counts(results: list[dict[str, Any]]) -> tuple[int, int, int]:
    ok = sum(1 for result in results if result["status"] == "ok")
    timeout = sum(1 for result in results if result["status"] == "timeout")
    failed = len(results) - ok - timeout
    return ok, timeout, failed


def unique_archive_path(report_dir: Path, started: dt.datetime) -> Path:
    archive_path = report_dir / f"self_improvement_{started.strftime('%Y%m%d_%H%M%S')}.md"
    if not archive_path.exists():
        return archive_path

    base = archive_path.with_suffix("")
    suffix = archive_path.suffix
    counter = 2
    while True:
        candidate = Path(f"{base}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def summary_log_preamble() -> str:
    return (
        "# Nightly Self-Improvement Log\n\n"
        "Each row is one orchestrator run. Columns: job → status → duration.\n\n"
    )


def summary_log_lines(results: list[dict[str, Any]], started: dt.datetime) -> list[str]:
    lines = [f"\n## {started.strftime('%Y-%m-%d %H:%M')}\n"]
    for result in results:
        emoji = {"ok": "✅", "timeout": "⏱️"}.get(result["status"], "❌")
        lines.append(
            f"- {emoji} **{result['name']}** — {result['status']} "
            f"({result['elapsed_s']}s) → `{Path(result['log']).name}`"
        )
    return lines


def tldr_stage_header(index: int, result: dict[str, Any], detail: dict[str, Any]) -> str:
    status_emoji = {"ok": "✓", "timeout": "⏱"}
    mark = status_emoji.get(result["status"], "✗")
    minutes = detail["elapsed_s"] / 60
    return f"- {index}. {mark} {detail['name']} ({minutes:.1f}m)"


def tldr_problem_fix_lines(detail: dict[str, Any]) -> list[str]:
    problems_tldr_list = detail.get("problems_tldr_list") or []
    fixes_tldr_list = detail.get("fixes_tldr_list") or []
    lines: list[str] = []
    if problems_tldr_list:
        lines.append("  - Problems:")
        for problem in problems_tldr_list:
            lines.append(f"    - {problem}")
    if fixes_tldr_list:
        lines.append("  - Fixes:")
        for fix in fixes_tldr_list:
            lines.append(f"    - {fix}")
    if not problems_tldr_list and not fixes_tldr_list:
        lines.append("  - Problems: none detected")
        lines.append("  - Fixes: none applied")
    return lines


def tldr_stage_lines(
    results: list[dict[str, Any]],
    details: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    for idx, (result, detail) in enumerate(zip(results, details), 1):
        lines.append(tldr_stage_header(idx, result, detail))
        lines.extend(tldr_problem_fix_lines(detail))
    return lines


def top_followups(details: list[dict[str, Any]]) -> list[str]:
    followups: list[str] = []
    for detail in details:
        for followup in (detail.get("followups") or [])[:2]:
            followups.append(followup.lstrip("- ").strip())
        if len(followups) >= 3:
            break
    return followups


def concrete_improvements(details: list[dict[str, Any]]) -> list[str]:
    return [
        item
        for detail in details
        for item in detail["improvements"]
        if "No concrete improvement" not in item
    ]


def executive_summary_lines(
    timeout: int,
    failed: int,
    details: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    if failed or timeout:
        lines.append(bullet(f"{timeout + failed} stage(s) need attention because they timed out or exited non-zero."))
    else:
        lines.append(bullet("All stages exited cleanly."))

    improvements = concrete_improvements(details)
    if improvements:
        lines.append(bullet(f"{len(improvements)} concrete improvement/fix signals were found in logs or reports."))
    else:
        lines.append(bullet("No concrete fix signals were found; this run mainly produced audits/reports."))
    return lines


def stage_detail_lines(index: int, detail: dict[str, Any]) -> list[str]:
    minutes = detail["elapsed_s"] / 60
    lines = [
        "",
        f"## Stage {index}: {detail['name']}",
        "",
        f"- Status: `{detail['status']}`",
        f"- Duration: {detail['elapsed_s']}s ({minutes:.1f} min)",
        "",
        "### What It Did",
        "",
        bullet(detail["purpose"]),
        "",
        "### Problems It Found",
        "",
        *detail["problems"],
        "",
        "### Improvements It Made",
        "",
        *detail["improvements"],
        "",
    ]
    if detail.get("followups"):
        lines.extend([
            "### Follow-Up Fixes Recommended",
            "",
            *detail["followups"],
            "",
        ])
    lines.extend([
        "### Evidence Files",
        "",
    ])
    if detail["artifacts"]:
        lines.extend(bullet(path) for path in detail["artifacts"])
    else:
        lines.append(bullet("No artifact path was recorded."))
    return lines
