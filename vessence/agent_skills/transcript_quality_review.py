"""transcript_quality_review.py — nightly transcript quality review.

Two-stage self-improvement job:

  Stage A (Codex):
    1. Collects today's conversation turns from jane_prompt_dump.jsonl
    2. Collects corresponding pipeline events from jane_web.log
    3. Collects client-side events from android_diagnostics.jsonl
    4. Feeds a condensed turn-by-turn summary to Codex CLI
    5. Codex identifies turns where Jane's answer seems odd, off, or wrong
    6. Codex traces logs to explain the root cause of each issue
    7. Writes a structured report to configs/transcript_review_report.md

  Stage B (Claude):
    1. Reads Codex's report
    2. Validates each issue against the actual codebase
    3. For valid issues: implements a fix + writes a test
    4. Appends fix summary to the report

Run manually:
  python agent_skills/transcript_quality_review.py [--date 2026-04-15]

Run as part of nightly self-improvement:
  Added to JOBS list in nightly_self_improve.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

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
CODEX_BIN = "codex"
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/home/chieh/.local/bin/claude")
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
    turns = []
    with path.open() as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = d.get("timestamp", "")
            if not ts.startswith(date_str):
                continue
            msg = d.get("message", "")
            # Strip conversation state header
            if "[END CURRENT CONVERSATION STATE]" in msg:
                msg = msg.split("[END CURRENT CONVERSATION STATE]", 1)[1].strip()
            turns.append({
                "time": ts,
                "session": d.get("session_id", "")[:12],
                "user_msg": msg[:500],
                "mode": d.get("mode", ""),
            })
    return turns


def _load_pipeline_events(date_str: str) -> list[str]:
    """Load today's pipeline-relevant log lines from jane_web.log."""
    path = LOG_DIR / "jane_web.log"
    if not path.exists():
        return []
    relevant = (
        "stage1_classifier", "stage2", "pipeline", "timer handler",
        "resolver", "stage3_escalate", "ERROR", "WARNING",
        "brain", "v2 stage2", "conv_end",
    )
    lines = []
    with path.open() as f:
        for line in f:
            if not line.startswith(date_str):
                continue
            if any(k in line for k in relevant):
                lines.append(line.rstrip()[:300])
    return lines


def _load_android_events(date_str: str) -> list[str]:
    """Load today's key android diagnostic events."""
    path = LOG_DIR / "android_diagnostics.jsonl"
    if not path.exists():
        return []
    # Convert date to ISO prefix for matching
    iso_prefix = date_str + "T"
    relevant_cats = (
        "voice_flow", "tool_handler", "wakeword",
    )
    lines = []
    with path.open() as f:
        for raw in f:
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            ts = d.get("timestamp", "")
            if not ts.startswith(iso_prefix):
                continue
            cat = d.get("category", "")
            if cat not in relevant_cats:
                continue
            msg = d.get("message", "")
            extra = ""
            if cat == "tool_handler":
                extra = f" detail={d.get('detail', '')}"
            elif cat == "voice_flow":
                extra_parts = []
                for k in ("path", "reason", "text_len", "fromVoice"):
                    if k in d:
                        extra_parts.append(f"{k}={d[k]}")
                extra = " " + " ".join(extra_parts)
            lines.append(f"{ts} [{cat}] {msg}{extra}"[:300])
    return lines


def _build_condensed_context(
    turns: list[dict],
    pipeline_events: list[str],
    android_events: list[str],
    max_chars: int = 80_000,
) -> str:
    """Build a condensed context string for Codex, within token budget."""
    sections = []

    # Section 1: user turns
    turn_lines = []
    for t in turns:
        user = t["user_msg"][:300]
        turn_lines.append(f"[{t['time']}] ({t['session']}) {user}")
    sections.append(
        "## User Turns (chronological)\n" + "\n".join(turn_lines)
    )

    # Section 2: pipeline events
    sections.append(
        "## Server Pipeline Events\n" + "\n".join(pipeline_events[-500:])
    )

    # Section 3: android events
    sections.append(
        "## Android Client Events\n" + "\n".join(android_events[-300:])
    )

    combined = "\n\n".join(sections)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n[TRUNCATED]"
    return combined


# ─── Stage A: Codex review ───────────────────────────────────────────────────


CODEX_PROMPT_TEMPLATE = """\
You are a quality auditor for "Jane", a 3-stage AI voice assistant pipeline.

The pipeline works like this:
  Stage 1 (Gemma classifier): classifies the user's intent into a category
    (timer, greeting, send message, weather, etc.) with a confidence score.
  Stage 2 (handler): a deterministic handler for that category processes the
    request directly (fast path). If it can't handle it, it escalates.
  Stage 3 (Opus/Claude): full LLM brain handles complex/ambiguous requests.

There is also a pending_action_resolver that runs BEFORE Stage 1: if the
previous turn left a follow-up question pending (Stage 2 or Stage 3), the
next user reply is routed directly to the right handler, bypassing classification.

Below are transcripts and logs from one day of real conversations.

Your job — evaluate EACH STAGE for every turn:

1. **Stage 1 accuracy**: Was the classification correct? Did the user say
   "set a timer" but get classified as "others"? Did "read my messages"
   get classified as "greeting"? Check the `stage1_classifier` log lines.

2. **Stage 2 correctness**: Did the handler produce the right response?
   Did the timer handler parse the duration correctly? Did the SMS handler
   resolve the right contact? Check `timer handler`, `resolver`, handler log lines.

3. **Stage 3 quality**: When Opus handled the turn, was the reply helpful
   and correct? Did Opus hallucinate a tool it doesn't have? Did it promise
   something it can't deliver? Did it set the right tool markers?

4. **Client-side execution**: Did the Android client execute the tool
   correctly? Did STT relaunch? Did the timer actually fire? Check
   android diagnostic events (tool_handler, voice_flow).

5. **Follow-up flow**: When a pending_action was set, did the resolver
   route the next turn correctly? Did the conversation flow naturally?

For each issue found, trace the logs to explain the ROOT CAUSE.
Rate: CRITICAL (user-facing breakage), MEDIUM (degraded UX), LOW (minor).

Output format — emit ONLY a JSON array, no markdown fences, no commentary:

[
  {{
    "turn_time": "2026-04-15 HH:MM:SS",
    "user_msg_snippet": "first 80 chars of user message",
    "issue": "brief description of what went wrong",
    "root_cause": "what the logs reveal about why",
    "severity": "CRITICAL|MEDIUM|LOW",
    "suggested_fix": "concrete code change suggestion",
    "relevant_log_lines": ["line1", "line2"]
  }}
]

If no issues found, return an empty array: []

--- BEGIN TRANSCRIPT + LOGS ---

{context}

--- END TRANSCRIPT + LOGS ---
"""


def run_codex_review(context: str, timeout: int = 300) -> list[dict]:
    """Invoke Codex CLI to review transcripts. Returns parsed issues list."""
    prompt = CODEX_PROMPT_TEMPLATE.format(context=context)

    log.info("Invoking Codex for transcript review (%d chars context)...",
             len(context))
    try:
        result = subprocess.run(
            [CODEX_BIN, "exec", "-"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(VESSENCE_HOME),
        )
    except subprocess.TimeoutExpired:
        log.error("Codex timed out after %ds", timeout)
        return []
    except FileNotFoundError:
        log.error("Codex binary not found at %s", CODEX_BIN)
        return []

    output = result.stdout.strip()
    if not output:
        log.warning("Codex returned empty output (stderr: %s)",
                    result.stderr[:500] if result.stderr else "none")
        return []

    # Extract JSON array from output (Codex may wrap in markdown fences)
    json_match = re.search(r'\[[\s\S]*\]', output)
    if not json_match:
        log.warning("Could not extract JSON array from Codex output: %s",
                    output[:500])
        return []

    try:
        issues = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        log.warning("Failed to parse Codex JSON: %s — raw: %s",
                    e, output[:500])
        return []

    log.info("Codex found %d issues", len(issues))
    return issues


def _log_vocal_summary_for_review(issues: list[dict], date_str: str) -> None:
    """Emit a single vocal-friendly summary of the review run."""
    try:
        from agent_skills.self_improve_log import log_vocal_summary
    except Exception as exc:
        log.warning("Could not import self_improve_log: %s", exc)
        return

    if not issues:
        log_vocal_summary(
            job="Transcript Review",
            summary=(
                f"I reviewed yesterday's conversations and nothing looked "
                f"off — all turns handled cleanly."
            ),
            severity="info",
        )
        return

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

    # Pick the most severe issue for the user-facing detail
    top = next(
        (i for i in issues if (i.get("severity") or "").upper() == "CRITICAL"),
        None,
    ) or next(
        (i for i in issues if (i.get("severity") or "").upper() == "MEDIUM"),
        issues[0],
    )
    top_desc = (top.get("issue") or "").strip().rstrip(".")

    log_vocal_summary(
        job="Transcript Review",
        what_was_wrong=(
            f"Reviewing yesterday's conversations I spotted {breakdown} "
            f"issues. The most urgent was: {top_desc}"
        ) if top_desc else (
            f"Reviewing yesterday's conversations I spotted {breakdown} "
            f"issues."
        ),
        why_it_mattered=(
            "These would have degraded your experience if left alone"
        ),
        what_was_done=(
            "The full details are in the transcript review report, "
            "and I've queued code fixes for the real ones"
        ),
        severity=spoken_sev,
    )


def write_codex_report(issues: list[dict], date_str: str) -> None:
    """Write Codex's findings to the report file."""
    header = (
        f"# Transcript Quality Review — {date_str}\n\n"
        f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )

    if not issues:
        body = "No issues found. All turns look reasonable.\n"
    else:
        parts = []
        for i, issue in enumerate(issues, 1):
            sev = issue.get("severity", "?")
            parts.append(
                f"## Issue {i} [{sev}]\n\n"
                f"**Turn:** {issue.get('turn_time', '?')}\n"
                f"**User said:** {issue.get('user_msg_snippet', '?')}\n\n"
                f"**Problem:** {issue.get('issue', '?')}\n\n"
                f"**Root cause:** {issue.get('root_cause', '?')}\n\n"
                f"**Suggested fix:** {issue.get('suggested_fix', '?')}\n\n"
                f"**Log evidence:**\n"
            )
            for line in issue.get("relevant_log_lines", []):
                parts.append(f"```\n{line}\n```\n")
            parts.append("\n---\n\n")
        body = "".join(parts)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(header + body, encoding="utf-8")
    log.info("Report written to %s (%d issues)", REPORT_PATH, len(issues))


# ─── Stage B: Claude validation + fix ────────────────────────────────────────


CLAUDE_FIX_PROMPT_TEMPLATE = """\
You are Jane's self-improvement system. The following report was generated by
Codex after reviewing today's conversation transcripts. For each issue:

1. READ the issue description and root cause.
2. VALIDATE: check whether the issue is real by reading the relevant source code.
   If the issue is a false positive (Codex misunderstood), skip it and note why.
3. FIX: for valid issues, implement the smallest correct code change.
4. TEST: write a unit test (in test_code/) that verifies the fix works and
   doesn't break existing functionality. Run the test to confirm it passes.
5. After all fixes, append a "## Fixes Applied" section to the report at
   {report_path} summarizing what you changed.

IMPORTANT:
- Acquire the code edit lock before modifying files:
  python agent_skills/code_lock.py status  (check first)
  Then use the lock context manager in your edits.
- Only fix issues rated CRITICAL or MEDIUM. Log LOW issues but skip fixing.
- Do NOT restart the server — the nightly job runner handles that.
- If you can't fix an issue, document why in the report.

Report contents:

{report_content}
"""


def run_claude_fixes(timeout: int = 600) -> bool:
    """Invoke Claude CLI to validate and fix issues from the report."""
    if not REPORT_PATH.exists():
        log.warning("No report to process at %s", REPORT_PATH)
        return False

    report_content = REPORT_PATH.read_text(encoding="utf-8")
    if "No issues found" in report_content:
        log.info("No issues in report — skipping Claude fixes")
        return True

    prompt = CLAUDE_FIX_PROMPT_TEMPLATE.format(
        report_path=REPORT_PATH,
        report_content=report_content,
    )

    log.info("Invoking Claude to validate and fix %s...", REPORT_PATH.name)
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", "-", "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(VESSENCE_HOME),
        )
    except subprocess.TimeoutExpired:
        log.error("Claude timed out after %ds", timeout)
        return False
    except FileNotFoundError:
        log.error("Claude binary not found at %s", CLAUDE_BIN)
        return False

    output = result.stdout.strip()
    if output:
        log.info("Claude output (%d chars): %s", len(output), output[:500])
    if result.returncode != 0:
        log.warning("Claude exited with code %d: %s",
                    result.returncode, result.stderr[:500] if result.stderr else "")
    return result.returncode == 0


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcript quality review")
    parser.add_argument(
        "--date",
        default=(dt.date.today() - dt.timedelta(days=1)).isoformat(),
        help="Date to review (YYYY-MM-DD). Default: yesterday.",
    )
    parser.add_argument(
        "--skip-fixes",
        action="store_true",
        help="Run Codex review only, skip Claude fixes.",
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
        help="Claude CLI timeout in seconds.",
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

    if args.skip_fixes or not issues:
        return 0

    # Stage B: Claude validation + fixes
    ok = run_claude_fixes(timeout=args.claude_timeout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
