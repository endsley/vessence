#!/usr/bin/env python3
"""daily_code_review.py — Automated daily code review by the AI team.

Checks git for source code changes in the last 24 hours. If changes exist,
sends them to available frontier CLIs (Gemini, Codex, Claude) for review.
Looks for: bugs, performance issues, code bloat, and missed edge cases.

Recommended cron: 3:00 AM daily (after audit_auto_fixer at 2:00 AM)
  0 3 * * * cd $VESSENCE_HOME && $VENV_BIN/python agent_skills/daily_code_review.py >> $VESSENCE_DATA_HOME/logs/daily_code_review.log 2>&1
"""

import datetime
import logging
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skills.daily_code_review_helpers import (
    build_review_question as _build_review_question,
    build_review_report as _build_review_report,
    is_reviewable_file as _is_reviewable_file,
    truncate_file_diff as _truncate_file_diff,
    truncated_files_notice as _truncated_files_notice,
)
from jane.config import VESSENCE_HOME, VESSENCE_DATA_HOME, LOGS_DIR

# ── Setup ────────────────────────────────────────────────────────────────────
LOG_FILE = Path(LOGS_DIR) / "daily_code_review.log"
REVIEW_DIR = Path(VESSENCE_DATA_HOME) / "logs" / "code_reviews"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [daily_code_review] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Only review these file types
REVIEW_EXTENSIONS = {".py", ".kt", ".js", ".ts", ".html", ".sh"}

# Skip these paths
SKIP_PATTERNS = [
    "marketing_site/downloads/",
    "__pycache__/",
    ".gradle/",
    "app/build/",
    "node_modules/",
    "test_code/",
]

# Max diff size to send to reviewers (chars)
MAX_DIFF_CHARS = 8000


def get_changed_files(since_hours: int = 24) -> list[str]:
    """Get list of source files changed in the last N hours via git."""
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since_hours} hours ago", "--name-only", "--pretty=format:"],
            capture_output=True, text=True, cwd=VESSENCE_HOME, timeout=30,
        )
        if result.returncode != 0:
            return []

        files = set()
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if not _is_reviewable_file(line, REVIEW_EXTENSIONS, SKIP_PATTERNS):
                continue
            full_path = Path(VESSENCE_HOME) / line
            if full_path.exists():
                files.add(line)
        return sorted(files)
    except Exception as e:
        logger.error("Failed to get changed files: %s", e)
        return []


def get_diff_summary(files: list[str]) -> str:
    """Get a concise diff of changed files."""
    try:
        result = subprocess.run(
            ["git", "diff", f"HEAD~1", "--stat"],
            capture_output=True, text=True, cwd=VESSENCE_HOME, timeout=30,
        )
        stat = result.stdout.strip()
    except Exception:
        stat = ""

    # Get actual diffs for changed files (truncated)
    diffs = []
    total_chars = 0
    for f in files:
        if total_chars >= MAX_DIFF_CHARS:
            diffs.append(_truncated_files_notice(len(files), len(diffs)))
            break
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "--", f],
                capture_output=True, text=True, cwd=VESSENCE_HOME, timeout=30,
            )
            diff = result.stdout.strip()
            if diff:
                # Truncate individual file diffs
                diff = _truncate_file_diff(diff)
                diffs.append(f"--- {f} ---\n{diff}")
                total_chars += len(diff)
        except Exception:
            continue

    return f"Stats:\n{stat}\n\nDiffs:\n" + "\n\n".join(diffs)


def run_team_review(diff_summary: str, changed_files: list[str]) -> str:
    """Send changes to the AI team for review."""
    from agent_skills.consult_panel import consult_panel

    question = _build_review_question(changed_files)

    return consult_panel(
        question=question,
        context=diff_summary,
        caller="system",  # not any specific brain — system-level review
        mode="review",
    )


def main():
    now = datetime.datetime.now()
    logger.info("=== Daily Code Review — %s ===", now.strftime("%Y-%m-%d %H:%M"))

    # Check for changes
    changed_files = get_changed_files(since_hours=24)
    if not changed_files:
        logger.info("No source code changes in the last 24 hours. Skipping review.")
        return

    logger.info("Found %d changed files: %s", len(changed_files), ", ".join(changed_files[:10]))

    # Get diff summary
    diff_summary = get_diff_summary(changed_files)
    logger.info("Diff summary: %d chars", len(diff_summary))

    # Send to team
    logger.info("Sending to AI team for review...")
    review_result = run_team_review(diff_summary, changed_files)

    # Save review report
    report_path = REVIEW_DIR / f"code_review_{now.strftime('%Y-%m-%d')}.md"
    report_content = _build_review_report(now, changed_files, review_result)
    report_path.write_text(report_content)
    logger.info("Review report saved to %s", report_path)

    # Log summary
    if "No peer models responded" in review_result:
        logger.warning("No AI peers available for review. Report saved but unreviewed.")
    else:
        logger.info("Review complete. Check %s for findings.", report_path)


if __name__ == "__main__":
    main()
