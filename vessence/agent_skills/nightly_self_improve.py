"""nightly_self_improve.py — orchestrate nightly self-improvement jobs.

Single cron entry, currently scheduled for 1:00 AM:

  0 1 * * * /home/chieh/google-adk-env/adk-venv/bin/python \
      /home/chieh/ambient/vessence/agent_skills/nightly_self_improve.py

Jobs run sequentially with per-job time budgets. If one times out or
fails, the orchestrator records that result and continues to the next
job. Each job writes a dedicated log in ``$VESSENCE_DATA_HOME/logs``;
the orchestrator appends a run summary to ``configs/self_improve_log.md``
and emits a vocal rollup. As the final reporting step, it also writes an
easy-to-read stage-by-stage report to
``configs/self_improvement_latest.md`` and archives the same report under
``$VESSENCE_DATA_HOME/reports/self_improvement/``.

Current job registry:
  1. Auto-Commit WIP (pre): commits current local WIP before auditors run.
  2. Dead Code Auditor: finds dead files/functions and safe duplicates.
  3. Code Auditor: generates tests for one whitelisted module and fixes it.
  4. Pipeline Audit (30 prompts): checks recent real prompts through stages 1-3.
  5. Doc Drift Auditor: compares docs/registries with live filesystem/cron state.
  6. Transcript Quality Review: audits real turns against server/client logs.
  7. Memory Janitor: purges, consolidates, and verifies Chroma memory.
  8. Auto-Commit + Push (post): commits and pushes generated fixes/reports.

Add new improvements by appending to the JOBS list below.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
import time
from pathlib import Path

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient/vessence-data")))
PYTHON = "/home/chieh/google-adk-env/adk-venv/bin/python"
LOG_DIR = VESSENCE_DATA_HOME / "logs"
ORCHESTRATOR_LOG = LOG_DIR / "self_improve_orchestrator.log"
SUMMARY_LOG = VESSENCE_HOME / "configs" / "self_improve_log.md"
LATEST_READABLE_REPORT = VESSENCE_HOME / "configs" / "self_improvement_latest.md"
READABLE_REPORT_DIR = VESSENCE_DATA_HOME / "reports" / "self_improvement"


JOB_PURPOSES = {
    "Auto-Commit WIP (pre)": (
        "Captured any existing local work before the auditors ran, so "
        "nightly changes start from a recoverable baseline."
    ),
    "Dead Code Auditor": (
        "Scanned the codebase for dead files, unreferenced functions, and "
        "duplicate function bodies."
    ),
    "Code Auditor": (
        "Picked a whitelisted module for deeper test generation and repair."
    ),
    "Pipeline Audit (30 prompts)": (
        "Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 "
        "to catch routing and response failures."
    ),
    "Doc Drift Auditor": (
        "Compared source-of-truth docs against live cron, class, and file "
        "state to catch stale documentation."
    ),
    "Transcript Quality Review": (
        "Read real user transcripts plus server/client logs to identify "
        "stage-by-stage failures Jane actually experienced."
    ),
    "Memory Janitor": (
        "Cleaned and verified Jane's Chroma memory stores."
    ),
    "Auto-Commit + Push (post)": (
        "Committed and pushed generated fixes and reports after the run."
    ),
}


JOB_ARTIFACTS = {
    "Dead Code Auditor": [VESSENCE_HOME / "configs" / "dead_code_report.md"],
    "Code Auditor": [
        VESSENCE_HOME / "configs" / "auto_audit_log.md",
        VESSENCE_HOME / "configs" / "audit_failures.md",
    ],
    "Pipeline Audit (30 prompts)": [VESSENCE_HOME / "configs" / "pipeline_audit_report.md"],
    "Doc Drift Auditor": [VESSENCE_HOME / "configs" / "doc_drift_report.md"],
    "Transcript Quality Review": [VESSENCE_HOME / "configs" / "transcript_review_report.md"],
}


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with ORCHESTRATOR_LOG.open("a") as f:
        f.write(line + "\n")


def run_job(name: str, script: str, args: list[str], timeout_min: int) -> dict:
    """Run a job script with a time budget. Return summary dict."""
    started_at = dt.datetime.now()
    started = time.time()
    log(f"=== Starting: {name} (timeout={timeout_min}min) ===")

    cmd = [PYTHON, str(VESSENCE_HOME / script)] + args
    log_path = LOG_DIR / f"self_improve_{Path(script).stem}.log"

    try:
        with log_path.open("a") as logf:
            logf.write(f"\n\n===== Run {started_at.isoformat()} =====\n")
            logf.flush()
            r = subprocess.run(
                cmd,
                stdout=logf,
                stderr=subprocess.STDOUT,
                timeout=timeout_min * 60,
                env={**os.environ,
                     "VESSENCE_HOME": str(VESSENCE_HOME),
                     "VESSENCE_DATA_HOME": str(VESSENCE_DATA_HOME),
                     "PYTHONPATH": str(VESSENCE_HOME)},
            )
        elapsed = time.time() - started
        status = "ok" if r.returncode == 0 else f"exit-{r.returncode}"
        log(f"=== Done: {name} ({status}, {elapsed:.0f}s) ===")
        return {
            "name": name,
            "status": status,
            "elapsed_s": int(elapsed),
            "log": str(log_path),
            "started_iso": started_at.isoformat(),
        }
    except subprocess.TimeoutExpired:
        elapsed = time.time() - started
        log(f"=== TIMEOUT: {name} after {elapsed:.0f}s — moving on ===")
        return {
            "name": name,
            "status": "timeout",
            "elapsed_s": int(elapsed),
            "log": str(log_path),
            "started_iso": started_at.isoformat(),
        }
    except Exception as e:
        elapsed = time.time() - started
        log(f"=== CRASHED: {name} ({e}) ===")
        return {
            "name": name,
            "status": f"crashed: {e}",
            "elapsed_s": int(elapsed),
            "log": str(log_path),
            "started_iso": started_at.isoformat(),
        }


def _log_vocal_rollup(results: list[dict]) -> None:
    """Emit a single vocal summary covering the whole orchestrator run.

    This is a roll-up — individual jobs still emit their own detailed
    vocal entries. This gives Jane a way to answer "did the nightly run
    finish cleanly" without her having to aggregate across entries.
    """
    try:
        sys.path.insert(0, str(VESSENCE_HOME))
        from agent_skills.self_improve_log import log_vocal_summary
    except Exception as exc:
        log(f"vocal rollup: could not import self_improve_log: {exc}")
        return

    ok = sum(1 for r in results if r["status"] == "ok")
    failed = [r for r in results if r["status"] != "ok"]
    if not failed:
        log_vocal_summary(
            job="Nightly Orchestrator",
            summary=(
                f"All {ok} self-improvement jobs finished cleanly overnight. "
                f"The readable report is at {LATEST_READABLE_REPORT}."
            ),
            severity="info",
        )
        return

    names = ", ".join(r["name"] for r in failed)
    log_vocal_summary(
        job="Nightly Orchestrator",
        what_was_wrong=(
            f"{len(failed)} of {len(results)} self-improvement jobs had "
            f"trouble overnight: {names}"
        ),
        why_it_mattered=(
            "Self-improvement runs keep the code clean and catch bugs "
            "that users hit — skipped runs let drift accumulate"
        ),
        what_was_done=(
            f"I wrote the readable stage-by-stage report to "
            f"{LATEST_READABLE_REPORT} and logged the failures to the "
            "orchestrator log for review"
        ),
        severity="medium",
    )


def write_summary(results: list[dict], started: dt.datetime) -> None:
    """Append a summary row to configs/self_improve_log.md"""
    SUMMARY_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not SUMMARY_LOG.exists():
        SUMMARY_LOG.write_text(
            "# Nightly Self-Improvement Log\n\n"
            "Each row is one orchestrator run. Columns: job → status → duration.\n\n"
        )
    lines = [f"\n## {started.strftime('%Y-%m-%d %H:%M')}\n"]
    for r in results:
        emoji = {"ok": "✅", "timeout": "⏱️"}.get(r["status"], "❌")
        lines.append(f"- {emoji} **{r['name']}** — {r['status']} ({r['elapsed_s']}s) → `{Path(r['log']).name}`")
    with SUMMARY_LOG.open("a") as f:
        f.write("\n".join(lines) + "\n")


def _read_text(path: Path, *, tail_chars: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except Exception:
        return ""
    if tail_chars and len(text) > tail_chars:
        return text[-tail_chars:]
    return text


def _read_job_log(result: dict, *, tail_chars: int = 12000) -> str:
    raw_log_path = str(result.get("log") or "").strip()
    if not raw_log_path:
        return ""
    log_path = Path(raw_log_path)
    text = _read_text(log_path)
    started_iso = str(result.get("started_iso") or "")
    if started_iso:
        try:
            started_at = dt.datetime.fromisoformat(started_iso)
            ended_at = started_at + dt.timedelta(seconds=int(result.get("elapsed_s") or 0) + 5)
            ts_re = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:,\d+)?")
            start_offset: int | None = None
            end_offset: int | None = None
            offset = 0
            for line in text.splitlines(keepends=True):
                m = ts_re.match(line)
                if m:
                    ts = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    if start_offset is None and started_at <= ts <= ended_at:
                        start_offset = offset
                    elif start_offset is not None and ts > ended_at:
                        end_offset = offset
                        break
                offset += len(line)
            if start_offset is not None:
                text = text[start_offset:end_offset]
                if len(text) > tail_chars:
                    return text[-tail_chars:]
                return text
        except Exception:
            pass
    if started_iso:
        marker = f"===== Run {started_iso}"
        idx = text.rfind(marker)
        if idx == -1:
            marker = f"===== Run {started_iso[:19]}"
            idx = text.rfind(marker)
        if idx != -1:
            text = text[idx:]
            next_idx = text.find("\n\n===== Run ", len(marker))
            if next_idx != -1:
                text = text[:next_idx]
    if len(text) > tail_chars:
        return text[-tail_chars:]
    return text


def _bullet(line: str) -> str:
    clean = re.sub(r"\s+", " ", line.strip())
    return f"- {clean}"


def _first_matching_lines(text: str, patterns: tuple[str, ...], limit: int = 5) -> list[str]:
    matches: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns):
            matches.append(_bullet(line))
        if len(matches) >= limit:
            break
    return matches


def _extract_markdown_bullets(text: str, after_heading: str, limit: int = 5) -> list[str]:
    match = re.search(rf"^{re.escape(after_heading)}.*$", text, flags=re.MULTILINE)
    if not match:
        return []
    out: list[str] = []
    for raw in text[match.end():].splitlines():
        line = raw.strip()
        if line.startswith("## "):
            break
        if line.startswith("- "):
            out.append(_bullet(line[2:]))
        if len(out) >= limit:
            break
    return out


def _extract_field(text: str, field_name: str, limit: int = 4) -> list[str]:
    pattern = re.compile(rf"^\*\*{re.escape(field_name)}:\*\*\s*(.+)$", re.MULTILINE)
    return [_bullet(m.group(1)) for m in pattern.finditer(text)][:limit]


def _summarize_dead_code(report: str, log_tail: str) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    improvements: list[str] = []
    for heading in (
        "Dead files — review needed",
        "Possibly-dead functions",
        "Duplicate function bodies",
    ):
        m = re.search(rf"## {re.escape(heading)} \(([^)]+)\)", report)
        if m:
            problems.append(_bullet(f"{heading}: {m.group(1)}."))
    improvements.extend(_first_matching_lines(
        log_tail,
        (r"auto-deleted", r"Done —"),
        limit=2,
    ))
    return problems, improvements


def _summarize_pipeline(report: str, log_tail: str) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    improvements: list[str] = []
    for label in (
        "Prompts audited",
        "Classification failures",
        "Response failures",
        "Auto-fixes applied",
    ):
        m = re.search(rf"- {re.escape(label)}:\s*\*\*([^*]+)\*\*", report)
        if m:
            target = improvements if label == "Auto-fixes applied" else problems
            target.append(_bullet(f"{label}: {m.group(1)}."))
    problems.extend(_extract_markdown_bullets(report, "## Response failures", limit=4))
    improvements.extend(_first_matching_lines(log_tail, (r"AUTO-FIX:", r"Added exemplar:"), limit=5))
    return problems, improvements


def _summarize_doc_drift(report: str, log_tail: str) -> tuple[list[str], list[str]]:
    problems = _extract_markdown_bullets(report, "## Needs human review", limit=8)
    improvements = _first_matching_lines(
        log_tail,
        (r"auto-fix", r"updated", r"wrote", r"fixed"),
        limit=5,
    )
    return problems, improvements


def _summarize_transcript_review(report: str, log_tail: str) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    improvements: list[str] = []
    severities = [
        sev.upper()
        for sev in re.findall(r"^## Issue \d+ \[([A-Z]+)\]", report, flags=re.MULTILINE | re.IGNORECASE)
    ]
    if severities:
        counts = {sev: severities.count(sev) for sev in sorted(set(severities))}
        summary = ", ".join(f"{count} {sev.lower()}" for sev, count in counts.items())
        problems.append(_bullet(f"Transcript review found {len(severities)} issues: {summary}."))
    problems.extend(_extract_field(report, "Problem", limit=4))
    improvements.extend(_first_matching_lines(
        log_tail,
        (r"Report written", r"self_improve_log: recorded"),
        limit=3,
    ))
    return problems, improvements


def _summarize_generic_log(log_tail: str) -> tuple[list[str], list[str]]:
    problems = _first_matching_lines(
        log_tail,
        (r"\bERROR\b", r"\bWARNING\b", r"failed", r"timeout", r"crash"),
        limit=5,
    )
    improvements = _first_matching_lines(
        log_tail,
        (r"\bDone\b", r"\bCommitted\b", r"\bPushed\b", r"\bWrote\b", r"\brecorded\b", r"\bcleaned\b"),
        limit=5,
    )
    return problems, improvements


def _job_details(result: dict) -> dict:
    name = result["name"]
    raw_log_path = str(result.get("log") or "").strip()
    log_tail = _read_job_log(result)
    problems: list[str] = []
    improvements: list[str] = []
    followups: list[str] = []
    artifacts: list[str] = []

    if result["status"] != "ok":
        problems.append(_bullet(f"Job ended with status `{result['status']}`."))

    for artifact in JOB_ARTIFACTS.get(name, []):
        if artifact.exists():
            artifacts.append(str(artifact))

    if name == "Dead Code Auditor":
        p, i = _summarize_dead_code(_read_text(JOB_ARTIFACTS[name][0]), log_tail)
    elif name == "Pipeline Audit (30 prompts)":
        p, i = _summarize_pipeline(_read_text(JOB_ARTIFACTS[name][0]), log_tail)
    elif name == "Doc Drift Auditor":
        p, i = _summarize_doc_drift(_read_text(JOB_ARTIFACTS[name][0]), log_tail)
    elif name == "Transcript Quality Review":
        transcript_report = _read_text(JOB_ARTIFACTS[name][0])
        p, i = _summarize_transcript_review(transcript_report, log_tail)
        followups = _extract_field(transcript_report, "Suggested fix", limit=4)
    else:
        p, i = _summarize_generic_log(log_tail)

    problems.extend(p)
    improvements.extend(i)
    if raw_log_path:
        artifacts.append(raw_log_path)

    return {
        "name": name,
        "status": result["status"],
        "elapsed_s": result["elapsed_s"],
        "purpose": JOB_PURPOSES.get(name, "Ran this self-improvement stage."),
        "problems": problems or [_bullet("No problems were detected in the available logs/reports.")],
        "improvements": improvements or [_bullet("No concrete improvement was recorded in the available logs/reports.")],
        "followups": followups,
        "artifacts": artifacts,
    }


def write_readable_report(results: list[dict], started: dt.datetime, total_s: float) -> Path:
    """Write the human-readable latest self-improvement report and archive it."""
    READABLE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_READABLE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    details = [_job_details(r) for r in results]

    ok = sum(1 for r in results if r["status"] == "ok")
    timeout = sum(1 for r in results if r["status"] == "timeout")
    failed = len(results) - ok - timeout
    archive_path = READABLE_REPORT_DIR / f"self_improvement_{started.strftime('%Y%m%d_%H%M%S')}.md"
    if archive_path.exists():
        base = archive_path.with_suffix("")
        suffix = archive_path.suffix
        counter = 2
        while True:
            candidate = Path(f"{base}_{counter}{suffix}")
            if not candidate.exists():
                archive_path = candidate
                break
            counter += 1

    lines = [
        "# Most Recent Nightly Self-Improvement",
        "",
        f"- Run started: {started.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Report generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Total runtime: {int(total_s)}s",
        f"- Jobs: {len(results)} total, {ok} ok, {timeout} timeout, {failed} failed",
        f"- Stable latest report path: `{LATEST_READABLE_REPORT}`",
        f"- Archived copy: `{archive_path}`",
        "",
        "## Executive Summary",
        "",
    ]

    if failed or timeout:
        lines.append(_bullet(f"{timeout + failed} stage(s) need attention because they timed out or exited non-zero."))
    else:
        lines.append(_bullet("All stages exited cleanly."))

    concrete_improvements = [
        item
        for detail in details
        for item in detail["improvements"]
        if "No concrete improvement" not in item
    ]
    if concrete_improvements:
        lines.append(_bullet(f"{len(concrete_improvements)} concrete improvement/fix signals were found in logs or reports."))
    else:
        lines.append(_bullet("No concrete fix signals were found; this run mainly produced audits/reports."))

    for idx, detail in enumerate(details, 1):
        minutes = detail["elapsed_s"] / 60
        lines.extend([
            "",
            f"## Stage {idx}: {detail['name']}",
            "",
            f"- Status: `{detail['status']}`",
            f"- Duration: {detail['elapsed_s']}s ({minutes:.1f} min)",
            "",
            "### What It Did",
            "",
            _bullet(detail["purpose"]),
            "",
            "### Problems It Found",
            "",
            *detail["problems"],
            "",
            "### Improvements It Made",
            "",
            *detail["improvements"],
            "",
        ])
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
            lines.extend(_bullet(path) for path in detail["artifacts"])
        else:
            lines.append(_bullet("No artifact path was recorded."))

    report = "\n".join(lines).rstrip() + "\n"
    latest_tmp = LATEST_READABLE_REPORT.with_suffix(LATEST_READABLE_REPORT.suffix + ".tmp")
    archive_tmp = archive_path.with_suffix(archive_path.suffix + ".tmp")
    latest_tmp.write_text(report, encoding="utf-8")
    archive_tmp.write_text(report, encoding="utf-8")
    os.replace(latest_tmp, LATEST_READABLE_REPORT)
    os.replace(archive_tmp, archive_path)
    log(f"Readable self-improvement report written: {LATEST_READABLE_REPORT}")
    log(f"Readable self-improvement report archived: {archive_path}")
    return archive_path


# ── Job registry ─────────────────────────────────────────────────────────────
# Add new self-improvement jobs by appending here. Each entry runs in order.
# Format: (name, script_path_relative_to_VESSENCE_HOME, args_list, timeout_minutes)

JOBS = [
    # Auto-commit daytime WIP BEFORE any self-improvement job touches the
    # tree. Ensures the code auditor can branch off clean, and all jobs
    # see a committed baseline. Without this, accumulated uncommitted
    # changes block the code auditor every night.
    (
        "Auto-Commit WIP (pre)",
        "agent_skills/auto_commit_wip.py",
        [],
        2,
    ),
    # Dead-code auditor runs FIRST so subsequent jobs (and the doc drift
    # auditor) reflect the post-cleanup state. Removing files first avoids
    # tests being generated for code that's about to be deleted.
    (
        "Dead Code Auditor",
        "agent_skills/dead_code_auditor.py",
        [],
        15,
    ),
    (
        "Code Auditor",
        "agent_skills/nightly_code_auditor.py",
        [],
        30,
    ),
    (
        "Pipeline Audit (30 prompts)",
        "agent_skills/pipeline_audit_100.py",
        ["--n", "30"],
        20,
    ),
    # Doc drift auditor runs LAST so it picks up any docs that drifted
    # because of fixes applied by earlier jobs in this same run.
    (
        "Doc Drift Auditor",
        "agent_skills/doc_drift_auditor.py",
        [],
        5,
    ),
    # Transcript quality review: Codex audits yesterday's conversations
    # per-stage (classification, handler, Opus, client), then Claude
    # validates findings and fixes code + writes tests.
    (
        "Transcript Quality Review",
        "agent_skills/transcript_quality_review.py",
        [],
        20,
    ),
    # Memory Janitor runs LAST — purges expired short-term memories,
    # deduplicates long-term entries, archives conversation themes,
    # and cleans stale log files. Uses Claude Opus for dedup merging
    # so it's expensive; once per night is sufficient.
    (
        "Memory Janitor",
        "memory/v1/janitor_memory.py",
        [],
        30,
    ),
    # Auto-commit + push AFTER all self-improvement jobs. This captures
    # any fixes, report files, or code changes the jobs produced, and
    # pushes to the remote so the work isn't lost.
    (
        "Auto-Commit + Push (post)",
        "agent_skills/auto_commit_wip.py",
        ["--push"],
        2,
    ),
    # Future jobs append here. Examples:
    # ("Opener Pool Grower", "agent_skills/grow_ack_openers.py", [], 10),
    # ("Slow Handler Profiler", "agent_skills/profile_handlers.py", [], 5),
]


def main() -> int:
    started = dt.datetime.now()
    log(f"##### Nightly self-improve starting #####")
    results = []
    for name, script, args, budget in JOBS:
        try:
            results.append(run_job(name, script, args, budget))
        except Exception as e:
            log(f"Orchestrator error scheduling {name}: {e}")
            results.append({"name": name, "status": f"orchestrator-error: {e}", "elapsed_s": 0, "log": ""})
    total = (dt.datetime.now() - started).total_seconds()
    log(f"##### Done in {total:.0f}s — {len(results)} jobs #####")
    write_summary(results, started)
    write_readable_report(results, started, total)
    _log_vocal_rollup(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
