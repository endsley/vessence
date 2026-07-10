"""transcript_quality_review.py — nightly transcript quality review.

Two-stage self-improvement job:

  Stage A (automation provider — Codex by default, falls back to Claude/Gemini):
    1. Collects today's conversation turns from jane_prompt_dump.jsonl
    2. Collects corresponding pipeline events from jane_web.log
    3. Collects client-side events from android_diagnostics.jsonl
    4. Feeds a condensed turn-by-turn summary to the automation provider
    5. The model identifies turns where Jane's answer seems odd, off, or wrong
    6. The model traces logs to explain the root cause of each issue
    7. Writes a structured report to configs/transcript_review_report.md

  Stage B (configured frontier provider, manual only with --apply-fixes):
    1. Reads Codex's report
    2. Validates each issue against the actual codebase
    3. For valid issues: implements a fix + writes a test
    4. Appends fix summary to the report

Run manually:
  python agent_skills/transcript_quality_review.py [--date 2026-04-15]
  python agent_skills/transcript_quality_review.py --apply-fixes [--date 2026-04-15]

Run as part of nightly self-improvement:
  Added to JOBS list in nightly_self_improve.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
import time
from pathlib import Path

from agent_skills.transcript_review_format import (
    android_event_line as _android_event_line,
    build_codex_report_markdown,
    build_condensed_context as _build_condensed_context,
    extract_json_array_text as _extract_json_array_text,
    parse_codex_issues as _parse_codex_issues,
    pipeline_event_line as _pipeline_event_line,
    prompt_dump_turn as _prompt_dump_turn,
)
from agent_skills.transcript_review_prompts import (
    CLAUDE_FIX_PROMPT_TEMPLATE,
    CODEX_PROMPT_TEMPLATE,
    build_codex_review_prompt,
    build_frontier_fix_prompt,
)
from agent_skills.transcript_review_sources import (
    load_android_events as _load_android_events_from_path,
    load_pipeline_events as _load_pipeline_events_from_path,
    load_prompt_dump as _load_prompt_dump_from_path,
)
from agent_skills.transcript_review_vocal import build_vocal_summary_payload

VESSENCE_HOME = Path(os.environ.get(
    "VESSENCE_HOME",
    str(Path(__file__).resolve().parents[1]),
))
VESSENCE_DATA_HOME = Path(os.environ.get(
    "VESSENCE_DATA_HOME",
    str(Path.home() / "ambient" / "vessence-data"),
))
LOG_DIR = VESSENCE_DATA_HOME / "logs"
REPORT_PATH = VESSENCE_HOME / "configs" / "transcript_review_report.md"
PYTHON = "/home/chieh/google-adk-env/adk-venv/bin/python"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("transcript_review")


# ─── Data collection ─────────────────────────────────────────────────────────


def _load_prompt_dump(date_str: str) -> list[dict]:
    """Load today's user turns from jane_prompt_dump.jsonl."""
    path = LOG_DIR / "jane_prompt_dump.jsonl"
    if not path.exists():
        log.warning("No prompt dump at %s", path)
        return []
    return _load_prompt_dump_from_path(path, date_str)


def _load_pipeline_events(date_str: str) -> list[str]:
    """Load today's pipeline-relevant log lines from jane_web.log."""
    return _load_pipeline_events_from_path(LOG_DIR / "jane_web.log", date_str)


def _load_android_events(date_str: str) -> list[str]:
    """Load today's key android diagnostic events."""
    return _load_android_events_from_path(LOG_DIR / "android_diagnostics.jsonl", date_str)


# ─── Stage A: Codex review ───────────────────────────────────────────────────


def run_codex_review(context: str, timeout: int = 300) -> list[dict]:
    """Run the transcript review prompt through the shared automation runner.

    Defaults to Codex (the automation-runner default) but automatically falls back
    to Claude/Gemini if the primary provider is exhausted or unavailable — see
    ``jane.automation_runner.run_automation_prompt``. Returns parsed issues list;
    returns [] if all providers fail or output can't be parsed.
    """
    from jane.automation_runner import AutomationError, run_automation_prompt

    prompt = build_codex_review_prompt(context)

    log.info("Invoking automation provider for transcript review (%d chars context)...",
             len(context))
    try:
        output = run_automation_prompt(
            prompt,
            timeout_seconds=timeout,
            workdir=str(VESSENCE_HOME),
        ).strip()
    except AutomationError as exc:
        log.error("Transcript review LLM failed (all providers): %s", exc)
        return []

    if not output:
        log.warning("Transcript review returned empty output")
        return []

    # Extract JSON array from output (providers may wrap in markdown fences)
    json_text = _extract_json_array_text(output)
    if json_text is None:
        log.warning("Could not extract JSON array from review output: %s",
                    output[:500])
        return []

    try:
        issues = json.loads(json_text)
    except json.JSONDecodeError as e:
        log.warning("Failed to parse review JSON: %s — raw: %s",
                    e, output[:500])
        return []

    log.info("Transcript review found %d issues", len(issues))
    return issues


def _log_vocal_summary_for_review(issues: list[dict], date_str: str) -> None:
    """Emit a single vocal-friendly summary of the review run."""
    try:
        from agent_skills.self_improve_log import log_vocal_summary
    except Exception as exc:
        log.warning("Could not import self_improve_log: %s", exc)
        return

    log_vocal_summary(**build_vocal_summary_payload(issues))


def write_codex_report(issues: list[dict], date_str: str) -> None:
    """Write Codex's findings to the report file."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(build_codex_report_markdown(issues, date_str), encoding="utf-8")
    log.info("Report written to %s (%d issues)", REPORT_PATH, len(issues))


# ─── Stage B: Frontier validation + fix ──────────────────────────────────────


def run_claude_fixes(timeout: int = 600) -> bool:
    """Invoke the configured frontier provider to validate and fix report issues."""
    if not REPORT_PATH.exists():
        log.warning("No report to process at %s", REPORT_PATH)
        return False

    report_content = REPORT_PATH.read_text(encoding="utf-8")
    if "No issues found" in report_content:
        log.info("No issues in report — skipping frontier fixes")
        return True

    prompt = build_frontier_fix_prompt(REPORT_PATH, report_content)

    log.info("Invoking configured frontier provider to validate and fix %s...", REPORT_PATH.name)
    try:
        from agent_skills.claude_cli_llm import completion_orchestrator
        output = completion_orchestrator(
            prompt,
            max_tokens=4096,
            timeout=timeout,
            cwd=str(VESSENCE_HOME),
        )
    except Exception as exc:
        log.error("Frontier provider failed: %s", exc)
        return False

    output = output.strip()
    if output:
        log.info("Frontier provider output (%d chars): %s", len(output), output[:500])
    return True


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcript quality review")
    parser.add_argument(
        "--date",
        default=(dt.date.today() - dt.timedelta(days=1)).isoformat(),
        help="Date to review (YYYY-MM-DD). Default: yesterday.",
    )
    parser.add_argument(
        "--apply-fixes",
        action="store_true",
        help="After writing the report, run the configured frontier provider to validate issues and apply code fixes.",
    )
    parser.add_argument(
        "--skip-fixes",
        action="store_true",
        help="Run Codex review only, skip frontier-provider fixes. This is the default.",
    )
    parser.add_argument(
        "--codex-timeout",
        type=int,
        default=300,
        help="Codex CLI timeout in seconds.",
    )
    parser.add_argument(
        "--claude-timeout",
        type=int,
        default=600,
        help="Frontier provider timeout in seconds.",
    )
    args = parser.parse_args()

    date_str = args.date
    log.info("=== Transcript Quality Review for %s ===", date_str)

    # Collect data
    turns = _load_prompt_dump(date_str)
    if not turns:
        log.info("No turns found for %s — nothing to review.", date_str)
        return 0

    pipeline_events = _load_pipeline_events(date_str)
    android_events = _load_android_events(date_str)

    log.info("Collected: %d turns, %d pipeline events, %d android events",
             len(turns), len(pipeline_events), len(android_events))

    # Build context
    context = _build_condensed_context(turns, pipeline_events, android_events)

    # Stage A: Codex review
    issues = run_codex_review(context, timeout=args.codex_timeout)
    write_codex_report(issues, date_str)
    _log_vocal_summary_for_review(issues, date_str)

    if args.skip_fixes or not args.apply_fixes or not issues:
        return 0

    # Stage B: frontier-provider validation + fixes (manual --apply-fixes only)
    ok = run_claude_fixes(timeout=args.claude_timeout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
