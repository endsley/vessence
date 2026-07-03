"""Pure helpers for audit_auto_fixer.py."""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any


SAFE_EXTENSIONS = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}

FORBIDDEN_PATTERNS = [
    "crontab",
    ".env",
    "credentials",
    "secret",
    "password",
    "token",
    ".ssh/",
    ".gnupg/",
    ".git/",
]


def is_safe_auto_fix_path(filepath: str, *, exists: bool) -> bool:
    fp_lower = filepath.lower()

    for pattern in FORBIDDEN_PATTERNS:
        if pattern in fp_lower:
            return False

    ext = Path(filepath).suffix.lower()
    if ext not in SAFE_EXTENSIONS:
        return False

    if not exists:
        return False

    return True


def extract_json_array_text(raw: str) -> str:
    text = raw.strip()

    fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]

    return text


def initial_fix_result(issue: dict[str, Any]) -> dict[str, str]:
    return {
        "issue": issue.get("issue", "Unknown"),
        "file": issue.get("file", "Unknown"),
        "category": issue.get("category", "unknown"),
        "status": "skipped",
        "reason": "",
    }


def fix_issue_preflight_result(
    issue: dict[str, Any],
    *,
    safe_to_modify: Callable[[str], bool],
) -> dict[str, str] | None:
    category = issue.get("category", "skip")

    if category == "skip":
        return {
            "status": "skipped",
            "reason": issue.get("fix_description", "Marked as skip by LLM"),
        }

    filepath = issue.get("file", "")
    search_text = issue.get("search_text", "")
    replacement_text = issue.get("replacement_text", "")

    if not filepath or not search_text or not replacement_text:
        return {
            "status": "skipped",
            "reason": "Missing file, search_text, or replacement_text",
        }

    if search_text == replacement_text:
        return {
            "status": "skipped",
            "reason": "search_text and replacement_text are identical",
        }

    if not safe_to_modify(filepath):
        return {
            "status": "skipped",
            "reason": f"File not safe to modify: {filepath}",
        }

    return None


def audit_report_candidates(audit_dir: str | Path, pattern: str = "audit_*.md") -> list[Path]:
    root = Path(audit_dir)
    if not root.exists():
        return []
    return [
        report
        for report in sorted(root.glob(pattern), reverse=True)
        if not report.name.startswith("auto_fix_")
    ]


def latest_audit_report(audit_dir: str | Path) -> Path | None:
    reports = audit_report_candidates(audit_dir)
    return reports[0] if reports else None


def todays_audit_report(audit_dir: str | Path, today: datetime.date | None = None) -> Path | None:
    report_date = (today or datetime.date.today()).isoformat()
    reports = audit_report_candidates(audit_dir, f"audit_{report_date}*.md")
    return reports[0] if reports else None


def partition_fix_results(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "fixed": [r for r in results if r["status"] in ("fixed", "would_fix")],
        "skipped": [r for r in results if r["status"] == "skipped"],
        "not_applicable": [r for r in results if r["status"] == "not_applicable"],
        "reverted": [r for r in results if r["status"] == "reverted"],
    }


def result_status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    partitions = partition_fix_results(results)
    return {
        "fixed": len(partitions["fixed"]),
        "skipped": len(partitions["skipped"]),
        "not_applicable": len(partitions["not_applicable"]),
        "reverted": len(partitions["reverted"]),
    }


def generate_fix_report_markdown(
    audit_report_path: str,
    results: list[dict[str, Any]],
    dry_run: bool,
    *,
    generated_at: datetime.datetime,
) -> str:
    mode = "DRY RUN" if dry_run else "LIVE"

    lines = [
        f"# Auto-Fix Report — {generated_at.strftime('%Y-%m-%d %H:%M')} ({mode})",
        "",
        f"**Source audit:** `{audit_report_path}`",
        f"**Total issues analyzed:** {len(results)}",
        "",
    ]

    partitions = partition_fix_results(results)
    fixed = partitions["fixed"]
    skipped = partitions["skipped"]
    not_applicable = partitions["not_applicable"]
    reverted = partitions["reverted"]

    if fixed:
        verb = "Would Fix" if dry_run else "Fixed"
        lines.append(f"## {verb} ({len(fixed)})")
        lines.append("")
        lines.append("| Issue | File | Fix Applied |")
        lines.append("|-------|------|-------------|")
        for r in fixed:
            fname = Path(r["file"]).name if r["file"] != "Unknown" else "?"
            lines.append(f"| {r['issue'][:80]} | `{fname}` | {r['reason'][:80]} |")
        lines.append("")

    if skipped:
        lines.append(f"## Skipped ({len(skipped)})")
        lines.append("")
        lines.append("| Issue | Reason |")
        lines.append("|-------|--------|")
        for r in skipped:
            lines.append(f"| {r['issue'][:80]} | {r['reason'][:80]} |")
        lines.append("")

    if not_applicable:
        lines.append(f"## Already Fixed / Not Applicable ({len(not_applicable)})")
        lines.append("")
        for r in not_applicable:
            lines.append(f"- {r['issue'][:100]}")
        lines.append("")

    if reverted:
        lines.append(f"## Reverted ({len(reverted)})")
        lines.append("")
        for r in reverted:
            lines.append(f"- **{r['issue'][:80]}** — {r['reason']}")
        lines.append("")

    return "\n".join(lines)
