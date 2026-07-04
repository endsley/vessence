#!/usr/bin/env python3
"""
audit_auto_fixer.py — Post-audit auto-fix system.

Reads the latest nightly audit report and automatically fixes issues it can
safely handle: documentation drift, wrong paths, missing imports, wrong
filenames in docs, etc.

Safety rules:
  - NEVER modify crontab
  - NEVER delete files
  - CAN fix: undefined variables, wrong paths in docs, missing imports,
    wrong filenames, stale doc content
  - CAN update: documentation files (.md) to match code
  - SKIP and log: anything it's not confident about
  - Always creates a .bak backup before modifying any file

Recommended cron: 01:30 daily (30 min after audit at 01:00)
# 30 1 * * * cd $VESSENCE_HOME && $VENV_BIN/python agent_skills/audit_auto_fixer.py >> $VESSENCE_DATA_HOME/logs/audit_auto_fix.log 2>&1
"""

import argparse
import datetime
import json
import logging
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import VESSENCE_HOME, VESSENCE_DATA_HOME, LOGS_DIR
from agent_skills.audit_auto_fix_prompt import (
    AUDIT_FIX_ANALYSIS_PROMPT_TEMPLATE,
    build_audit_fix_analysis_prompt,
)
from agent_skills.audit_auto_fix_helpers import (
    FORBIDDEN_PATTERNS,
    SAFE_EXTENSIONS,
    circuit_breaker_skip_results as _circuit_breaker_skip_results,
    extract_json_array_text as _extract_json_array_text,
    fix_content_preflight_result as _fix_content_preflight_result,
    fix_issue_preflight_result as _fix_issue_preflight_result,
    generate_fix_report_markdown as _generate_fix_report_markdown,
    initial_fix_result as _initial_fix_result,
    is_safe_auto_fix_path as _is_safe_auto_fix_path,
    latest_audit_report as _latest_audit_report,
    result_status_counts as _result_status_counts,
    todays_audit_report as _todays_audit_report,
)

# ── Constants ────────────────────────────────────────────────────────────────
AUDIT_DIR = Path(VESSENCE_DATA_HOME) / "logs" / "audits"
FIX_REPORT_DIR = AUDIT_DIR  # fix reports go alongside audit reports
MAX_FIXES_PER_RUN = 10      # circuit breaker

LOG_FILE = Path(LOGS_DIR) / "audit_auto_fix.log"
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [audit_auto_fixer] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("audit_auto_fixer")

# ── Find latest audit report ────────────────────────────────────────────────
def find_latest_audit_report() -> Path | None:
    """Find the most recent audit report file."""
    return _latest_audit_report(AUDIT_DIR)


def find_todays_audit_report() -> Path | None:
    """Find today's audit report specifically."""
    return _todays_audit_report(AUDIT_DIR, datetime.date.today())


# ── Safety checks ────────────────────────────────────────────────────────────
def is_safe_to_modify(filepath: str) -> bool:
    """Check if a file is safe to auto-modify."""
    return _is_safe_auto_fix_path(filepath, exists=Path(filepath).exists())


def create_backup(filepath: str) -> str | None:
    """Create a .bak backup of a file before modifying it. Returns backup path."""
    src = Path(filepath)
    if not src.exists():
        return None
    bak = src.with_suffix(src.suffix + ".bak")
    try:
        shutil.copy2(str(src), str(bak))
        return str(bak)
    except Exception as e:
        logger.error("Failed to create backup for %s: %s", filepath, e)
        return None


def verify_python_syntax(filepath: str) -> bool:
    """Verify that a Python file has valid syntax after modification."""
    if not filepath.endswith(".py"):
        return True  # non-Python files pass by default
    try:
        with open(filepath, "r") as f:
            source = f.read()
        compile(source, filepath, "exec")
        return True
    except SyntaxError as e:
        logger.error("Syntax error in %s after fix: %s", filepath, e)
        return False


def restore_from_backup(filepath: str) -> bool:
    """Restore a file from its .bak backup."""
    bak = Path(filepath + ".bak")
    if bak.exists():
        shutil.copy2(str(bak), filepath)
        logger.info("Restored %s from backup", filepath)
        return True
    return False


# ── LLM-powered analysis ────────────────────────────────────────────────────
def analyze_audit_report(report_text: str) -> list[dict]:
    """Ask the LLM to parse the audit report into a structured list of fixable issues.

    Returns a list of dicts, each with:
      - issue: description of the problem
      - category: "doc_update" | "code_fix" | "skip"
      - file: absolute path to the file to fix
      - fix_description: what fix to apply
      - search_text: text to find in the file (for targeted replacement)
      - replacement_text: text to replace it with
    """
    from agent_skills.claude_cli_llm import completion

    prompt = build_audit_fix_analysis_prompt(report_text, VESSENCE_HOME)

    try:
        raw = completion(prompt, max_tokens=4096, timeout=120)
    except RuntimeError as e:
        logger.error("LLM call failed: %s", e)
        return []

    # Extract JSON from the response — handle markdown fences and preamble text
    text = _extract_json_array_text(raw)

    try:
        issues = json.loads(text)
        if not isinstance(issues, list):
            logger.error("LLM returned non-list JSON: %s", type(issues))
            return []
        return issues
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s\nRaw: %s", e, text[:500])
        return []


# ── Apply fixes ──────────────────────────────────────────────────────────────
def apply_fix(issue: dict, dry_run: bool = False) -> dict:
    """Apply a single fix. Returns a result dict with status and details."""
    result = _initial_fix_result(issue)

    preflight = _fix_issue_preflight_result(issue, safe_to_modify=is_safe_to_modify)
    if preflight is not None:
        result.update(preflight)
        return result

    filepath = issue.get("file", "")
    search_text = issue.get("search_text", "")
    replacement_text = issue.get("replacement_text", "")

    # Read the file
    try:
        content = Path(filepath).read_text()
    except Exception as e:
        result["reason"] = f"Cannot read file: {e}"
        return result

    content_preflight = _fix_content_preflight_result(issue, content, dry_run=dry_run)
    if content_preflight is not None:
        result.update(content_preflight)
        return result

    # Create backup
    backup_path = create_backup(filepath)
    if backup_path is None:
        result["reason"] = "Failed to create backup"
        return result

    # Apply the fix
    try:
        new_content = content.replace(search_text, replacement_text)
        Path(filepath).write_text(new_content)
    except Exception as e:
        restore_from_backup(filepath)
        result["reason"] = f"Failed to write fix: {e}"
        return result

    # Verify syntax for Python files
    if filepath.endswith(".py") and not verify_python_syntax(filepath):
        restore_from_backup(filepath)
        result["status"] = "reverted"
        result["reason"] = "Fix introduced syntax error — reverted from backup"
        return result

    result["status"] = "fixed"
    result["reason"] = issue.get("fix_description", "Fix applied successfully")
    result["backup"] = backup_path
    logger.info("Fixed: %s in %s", issue.get("issue", "?"), filepath)
    return result


# ── Report generation ────────────────────────────────────────────────────────
def generate_fix_report(
    audit_report_path: str,
    results: list[dict],
    dry_run: bool,
) -> str:
    """Generate a markdown fix report."""
    now = datetime.datetime.now()
    return _generate_fix_report_markdown(
        audit_report_path,
        results,
        dry_run,
        generated_at=now,
    )


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Post-audit auto-fixer: reads nightly audit reports and fixes safe issues."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and report but do not modify any files.",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Path to a specific audit report to process (default: today's latest).",
    )
    parser.add_argument(
        "--any-date",
        action="store_true",
        help="Use the latest audit report regardless of date (instead of today only).",
    )
    args = parser.parse_args()

    # Load gate: wait until CPU/memory is acceptable
    try:
        from agent_skills.system_load import wait_until_safe
        if not wait_until_safe(max_wait_minutes=10):
            logger.info("System busy — skipping auto-fixer this cycle.")
            return
    except Exception:
        pass

    now = datetime.datetime.now()
    logger.info("audit_auto_fixer started at %s (dry_run=%s)", now.isoformat(), args.dry_run)

    # Find the audit report
    if args.report:
        report_path = Path(args.report)
        if not report_path.exists():
            logger.error("Specified report not found: %s", args.report)
            sys.exit(1)
    elif args.any_date:
        report_path = find_latest_audit_report()
    else:
        report_path = find_todays_audit_report()

    if report_path is None:
        logger.info("No audit report found for today. Exiting.")
        sys.exit(0)

    logger.info("Processing audit report: %s", report_path)

    # Read the report
    try:
        report_text = report_path.read_text()
    except Exception as e:
        logger.error("Failed to read audit report: %s", e)
        sys.exit(1)

    if len(report_text.strip()) < 50:
        logger.info("Audit report is too short (likely empty/error). Skipping.")
        sys.exit(0)

    # Analyze with LLM
    logger.info("Sending audit report to LLM for analysis...")
    issues = analyze_audit_report(report_text)
    logger.info("LLM returned %d issues", len(issues))

    if not issues:
        logger.info("No actionable issues found. Exiting.")
        # Still write a report so we know it ran
        fix_report = generate_fix_report(str(report_path), [], args.dry_run)
        report_out = FIX_REPORT_DIR / f"auto_fix_{now.strftime('%Y-%m-%d')}.md"
        report_out.write_text(fix_report)
        sys.exit(0)

    # Apply fixes (with circuit breaker)
    results = []
    fix_count = 0

    for issue in issues:
        if fix_count >= MAX_FIXES_PER_RUN:
            logger.warning("Circuit breaker: reached %d fixes, stopping.", MAX_FIXES_PER_RUN)
            results.extend(
                _circuit_breaker_skip_results(
                    issues,
                    result_count=len(results),
                    max_fixes_per_run=MAX_FIXES_PER_RUN,
                )
            )
            break

        result = apply_fix(issue, dry_run=args.dry_run)
        results.append(result)

        if result["status"] in ("fixed", "would_fix"):
            fix_count += 1

    # Generate and save fix report
    fix_report = generate_fix_report(str(report_path), results, args.dry_run)
    report_out = FIX_REPORT_DIR / f"auto_fix_{now.strftime('%Y-%m-%d')}.md"
    report_out.write_text(fix_report)
    logger.info("Fix report saved to %s", report_out)

    # Summary
    counts = _result_status_counts(results)

    logger.info(
        "Summary: %d fixed, %d skipped, %d not applicable, %d reverted",
        counts["fixed"], counts["skipped"], counts["not_applicable"], counts["reverted"],
    )


if __name__ == "__main__":
    main()
