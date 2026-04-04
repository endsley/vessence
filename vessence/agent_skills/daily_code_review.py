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
            ext = Path(line).suffix
            if ext not in REVIEW_EXTENSIONS:
                continue
            if any(skip in line for skip in SKIP_PATTERNS):
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
            diffs.append(f"\n... and {len(files) - len(diffs)} more files (truncated)")
            break
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "--", f],
                capture_output=True, text=True, cwd=VESSENCE_HOME, timeout=30,
            )
            diff = result.stdout.strip()
            if diff:
                # Truncate individual file diffs
                if len(diff) > 2000:
                    diff = diff[:2000] + "\n... (truncated)"
                diffs.append(f"--- {f} ---\n{diff}")
                total_chars += len(diff)
        except Exception:
            continue

    return f"Stats:\n{stat}\n\nDiffs:\n" + "\n\n".join(diffs)


def run_team_review(diff_summary: str, changed_files: list[str]) -> str:
    """Send changes to the AI team for review."""
    from agent_skills.consult_panel import consult_panel

    question = (
        f"Daily code review: {len(changed_files)} files changed in the last 24 hours. "
        f"Files: {', '.join(changed_files[:20])}\n\n"
        "Review the diffs below. Focus on:\n"
        "1. Bugs and logic errors\n"
        "2. Free speed wins — optimizations that are obviously faster with zero quality tradeoff (do NOT suggest changes that sacrifice correctness or readability for speed)\n"
        "3. Code bloat — dead code, duplicate logic, unnecessary abstractions\n"
        "4. Token waste — ONLY flag genuinely wasted tokens (duplicate data, unused context, redundant LLM calls). NEVER suggest reducing tokens if it would degrade memory quality, capability, or response speed\n"
        "5. Security issues\n"
        "6. Missing edge cases\n\n"
        "Be concise. Only report actual problems, not style preferences. "
        "NEVER suggest speed improvements that compromise quality or correctness."
    )

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
    report_content = (
        f"# Daily Code Review — {now.strftime('%Y-%m-%d')}\n\n"
        f"**Files reviewed:** {len(changed_files)}\n"
        f"**Files:** {', '.join(changed_files)}\n\n"
        f"---\n\n"
        f"{review_result}\n"
    )
    report_path.write_text(report_content)
    logger.info("Review report saved to %s", report_path)

    # Log summary
    if "No peer models responded" in review_result:
        logger.warning("No AI peers available for review. Report saved but unreviewed.")
    else:
        logger.info("Review complete. Check %s for findings.", report_path)


if __name__ == "__main__":
    main()
