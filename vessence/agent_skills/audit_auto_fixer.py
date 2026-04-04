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
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import VESSENCE_HOME, VESSENCE_DATA_HOME, LOGS_DIR

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

# Categories of files that are SAFE to auto-fix
SAFE_EXTENSIONS = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}

# Files/patterns that must NEVER be touched
FORBIDDEN_PATTERNS = [
    "crontab", ".env", "credentials", "secret", "password", "token",
    ".ssh/", ".gnupg/", ".git/",
]


# ── Find latest audit report ────────────────────────────────────────────────
def find_latest_audit_report() -> Path | None:
    """Find the most recent audit report file."""
    if not AUDIT_DIR.exists():
        return None

    # Match both audit_YYYY-MM-DD.md and audit_YYYY-MM-DD_HHMM.md
    reports = sorted(AUDIT_DIR.glob("audit_*.md"), reverse=True)
    # Filter out auto_fix reports
    reports = [r for r in reports if not r.name.startswith("auto_fix_")]
    return reports[0] if reports else None


def find_todays_audit_report() -> Path | None:
    """Find today's audit report specifically."""
    today = datetime.date.today().isoformat()
    if not AUDIT_DIR.exists():
        return None

    # Look for any audit report from today (any timestamp format)
    candidates = sorted(AUDIT_DIR.glob(f"audit_{today}*.md"), reverse=True)
    candidates = [r for r in candidates if not r.name.startswith("auto_fix_")]
    return candidates[0] if candidates else None


# ── Safety checks ────────────────────────────────────────────────────────────
def is_safe_to_modify(filepath: str) -> bool:
    """Check if a file is safe to auto-modify."""
    fp_lower = filepath.lower()

    # Check forbidden patterns
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in fp_lower:
            return False

    # Must have a safe extension
    ext = Path(filepath).suffix.lower()
    if ext not in SAFE_EXTENSIONS:
        return False

    # Must exist
    if not Path(filepath).exists():
        return False

    return True


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

    prompt = f"""You are a code maintenance assistant. Analyze this audit report and produce a JSON array of issues that can be SAFELY auto-fixed.

RULES:
- Only include issues where you can specify an EXACT file path, search text, and replacement text
- The file path must be absolute (starting with {VESSENCE_HOME}/)
- NEVER include crontab modifications
- NEVER include file deletions
- Focus on: wrong paths in docs, stale descriptions, missing imports, wrong variable names
- Category must be one of: "doc_update", "code_fix", "skip"
- Use "skip" for anything risky, ambiguous, or requiring human judgment
- For "skip" items, omit search_text and replacement_text
- Keep it conservative — better to skip than to break something

Output ONLY a JSON array. No markdown fences, no explanation.

Example format:
[
  {{
    "issue": "CRON_JOBS.md uses wrong path prefix",
    "category": "doc_update",
    "file": "{VESSENCE_HOME}/configs/CRON_JOBS.md",
    "fix_description": "Replace old path prefix with correct one",
    "search_text": "old/wrong/path/",
    "replacement_text": "correct/path/"
  }},
  {{
    "issue": "Architecture change requires human review",
    "category": "skip",
    "file": "{VESSENCE_HOME}/jane/config.py",
    "fix_description": "Needs human review — changes user-facing behavior"
  }}
]

AUDIT REPORT:
{report_text}
"""

    try:
        raw = completion(prompt, max_tokens=4096, timeout=120)
    except RuntimeError as e:
        logger.error("LLM call failed: %s", e)
        return []

    # Extract JSON from the response — handle markdown fences and preamble text
    text = raw.strip()

    # Strategy 1: If wrapped in code fences, extract the fenced content
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Strategy 2: Find the first '[' and last ']' to extract the JSON array
    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]

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
    result = {
        "issue": issue.get("issue", "Unknown"),
        "file": issue.get("file", "Unknown"),
        "category": issue.get("category", "unknown"),
        "status": "skipped",
        "reason": "",
    }

    category = issue.get("category", "skip")

    # Skip items marked as skip
    if category == "skip":
        result["reason"] = issue.get("fix_description", "Marked as skip by LLM")
        return result

    filepath = issue.get("file", "")
    search_text = issue.get("search_text", "")
    replacement_text = issue.get("replacement_text", "")

    # Validate required fields
    if not filepath or not search_text or not replacement_text:
        result["reason"] = "Missing file, search_text, or replacement_text"
        return result

    if search_text == replacement_text:
        result["reason"] = "search_text and replacement_text are identical"
        return result

    # Safety check
    if not is_safe_to_modify(filepath):
        result["reason"] = f"File not safe to modify: {filepath}"
        return result

    # Read the file
    try:
        content = Path(filepath).read_text()
    except Exception as e:
        result["reason"] = f"Cannot read file: {e}"
        return result

    # Check if the search text actually exists in the file
    if search_text not in content:
        result["status"] = "not_applicable"
        result["reason"] = "Search text not found in file (may already be fixed)"
        return result

    if dry_run:
        result["status"] = "would_fix"
        result["reason"] = issue.get("fix_description", "")
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
    mode = "DRY RUN" if dry_run else "LIVE"

    lines = [
        f"# Auto-Fix Report — {now.strftime('%Y-%m-%d %H:%M')} ({mode})",
        "",
        f"**Source audit:** `{audit_report_path}`",
        f"**Total issues analyzed:** {len(results)}",
        "",
    ]

    # Partition results
    fixed = [r for r in results if r["status"] in ("fixed", "would_fix")]
    skipped = [r for r in results if r["status"] == "skipped"]
    not_applicable = [r for r in results if r["status"] == "not_applicable"]
    reverted = [r for r in results if r["status"] == "reverted"]

    # Fixed issues table
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

    # Skipped issues
    if skipped:
        lines.append(f"## Skipped ({len(skipped)})")
        lines.append("")
        lines.append("| Issue | Reason |")
        lines.append("|-------|--------|")
        for r in skipped:
            lines.append(f"| {r['issue'][:80]} | {r['reason'][:80]} |")
        lines.append("")

    # Not applicable (already fixed)
    if not_applicable:
        lines.append(f"## Already Fixed / Not Applicable ({len(not_applicable)})")
        lines.append("")
        for r in not_applicable:
            lines.append(f"- {r['issue'][:100]}")
        lines.append("")

    # Reverted
    if reverted:
        lines.append(f"## Reverted ({len(reverted)})")
        lines.append("")
        for r in reverted:
            lines.append(f"- **{r['issue'][:80]}** — {r['reason']}")
        lines.append("")

    return "\n".join(lines)


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
            remaining = issues[len(results):]
            for r in remaining:
                results.append({
                    "issue": r.get("issue", "Unknown"),
                    "file": r.get("file", "Unknown"),
                    "category": r.get("category", "unknown"),
                    "status": "skipped",
                    "reason": f"Circuit breaker: max {MAX_FIXES_PER_RUN} fixes per run",
                })
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
    fixed_count = sum(1 for r in results if r["status"] in ("fixed", "would_fix"))
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    na_count = sum(1 for r in results if r["status"] == "not_applicable")
    reverted_count = sum(1 for r in results if r["status"] == "reverted")

    logger.info(
        "Summary: %d fixed, %d skipped, %d not applicable, %d reverted",
        fixed_count, skipped_count, na_count, reverted_count,
    )


if __name__ == "__main__":
    main()
