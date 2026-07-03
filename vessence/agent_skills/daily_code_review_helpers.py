"""Pure helpers for daily_code_review.py."""

from __future__ import annotations

import datetime as dt
from pathlib import Path


def is_reviewable_file(
    path: str,
    review_extensions: set[str],
    skip_patterns: list[str],
) -> bool:
    if Path(path).suffix not in review_extensions:
        return False
    return not any(skip in path for skip in skip_patterns)


def truncate_file_diff(diff: str, max_chars: int = 2000) -> str:
    if len(diff) > max_chars:
        return diff[:max_chars] + "\n... (truncated)"
    return diff


def truncated_files_notice(total_files: int, emitted_diff_count: int) -> str:
    return f"\n... and {total_files - emitted_diff_count} more files (truncated)"


def build_review_question(changed_files: list[str]) -> str:
    dash = "\u2014"
    return (
        f"Daily code review: {len(changed_files)} files changed in the last 24 hours. "
        f"Files: {', '.join(changed_files[:20])}\n\n"
        "Review the diffs below. Focus on:\n"
        "1. Bugs and logic errors\n"
        f"2. Free speed wins {dash} optimizations that are obviously faster with zero quality tradeoff (do NOT suggest changes that sacrifice correctness or readability for speed)\n"
        f"3. Code bloat {dash} dead code, duplicate logic, unnecessary abstractions\n"
        f"4. Token waste {dash} ONLY flag genuinely wasted tokens (duplicate data, unused context, redundant LLM calls). NEVER suggest reducing tokens if it would degrade memory quality, capability, or response speed\n"
        "5. Security issues\n"
        "6. Missing edge cases\n\n"
        "Be concise. Only report actual problems, not style preferences. "
        "NEVER suggest speed improvements that compromise quality or correctness."
    )


def build_review_report(
    now: dt.datetime,
    changed_files: list[str],
    review_result: str,
) -> str:
    dash = "\u2014"
    return (
        f"# Daily Code Review {dash} {now.strftime('%Y-%m-%d')}\n\n"
        f"**Files reviewed:** {len(changed_files)}\n"
        f"**Files:** {', '.join(changed_files)}\n\n"
        f"---\n\n"
        f"{review_result}\n"
    )
