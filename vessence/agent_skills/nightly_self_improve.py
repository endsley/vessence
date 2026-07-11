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
  2. Code Auditor: generates tests for one whitelisted module and fixes it.
     Runs FIRST after the pre-commit because it requires a clean tree.
  3. Dead Code Auditor: finds dead files/functions and safe duplicates.
  4. Pipeline Audit (30 prompts): checks recent real prompts through stages 1-3
     in report-only mode.
  5. Doc Drift Auditor: compares docs/registries with live filesystem/cron state.
  6. Transcript Quality Review: audits real turns against server/client logs
     in report-only mode.
  7. Memory Janitor: purges, consolidates, and verifies Chroma memory.
  8. Auto-Commit + Push (post): commits and pushes generated fixes/reports.

Add new improvements by appending to the JOBS list below.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

from agent_skills.nightly_log_reader import (
    read_job_log as _read_job_log,
    read_text as _read_text,
)
from agent_skills.nightly_report_rendering import (
    executive_summary_lines as _executive_summary_lines,
    stage_detail_lines as _stage_detail_lines,
    status_counts as _status_counts,
    summary_log_lines as _summary_log_lines,
    summary_log_preamble as _summary_log_preamble,
    tldr_stage_lines as _tldr_stage_lines,
    top_followups as _top_followups,
    unique_archive_path as _unique_archive_path,
)
from agent_skills.nightly_report_summaries import (
    bullet as _bullet,
    condense_tldr_items as _condense_tldr_items,
    extract_field as _extract_field,
    summarize_dead_code as _summarize_dead_code,
    summarize_doc_drift as _summarize_doc_drift,
    summarize_generic_log as _summarize_generic_log,
    summarize_pipeline as _summarize_pipeline,
    summarize_transcript_review as _summarize_transcript_review,
)

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
        "to catch routing and response failures. Runs report-only during "
        "nightly self-improvement; classifier exemplar auto-fixes require "
        "a separate manual --apply-fixes run."
    ),
    "Doc Drift Auditor": (
        "Compared source-of-truth docs against live cron, class, and file "
        "state to catch stale documentation."
    ),
    "Transcript Quality Review": (
        "Read real user transcripts plus server/client logs to identify "
        "stage-by-stage failures Jane actually experienced. Runs report-only "
        "during nightly self-improvement; code fixes require a separate "
        "manual --apply-fixes run."
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


def run_job(name: str, script: str, args: list[str], timeout_min: int | None) -> dict:
    """Run a job script with an optional time budget. Return summary dict."""
    started_at = dt.datetime.now()
    started = time.time()
    timeout_label = "none" if timeout_min is None else f"{timeout_min}min"
    timeout_s = None if timeout_min is None else timeout_min * 60
    log(f"=== Starting: {name} (timeout={timeout_label}) ===")

    cmd = [PYTHON, str(VESSENCE_HOME / script)] + args
    log_path = LOG_DIR / f"self_improve_{Path(script).stem}.log"

    try:
        with log_path.open("a") as logf:
            logf.write(f"\n\n===== Run {started_at.isoformat()} =====\n")
            logf.flush()
            _env = {**os.environ,
                    "VESSENCE_HOME": str(VESSENCE_HOME),
                    "VESSENCE_DATA_HOME": str(VESSENCE_DATA_HOME),
                    "PYTHONPATH": str(VESSENCE_HOME)}
            
            # Special handling for Memory Janitor: add TensorRT lib path
            if script == "memory/v1/janitor_memory.py":
                tensorrt_lib_path = Path(PYTHON).parent.parent / "lib" / "python3.13" / "site-packages" / "tensorrt_libs"
                if tensorrt_lib_path.is_dir():
                    current_ld_library_path = _env.get("LD_LIBRARY_PATH", "")
                    _env["LD_LIBRARY_PATH"] = f"{tensorrt_lib_path}:{current_ld_library_path}".strip(":")
                    log(f"Injected LD_LIBRARY_PATH for Memory Janitor: {_env['LD_LIBRARY_PATH']}")

            r = subprocess.run(
                cmd,
                stdout=logf,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
                env=_env,
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
        SUMMARY_LOG.write_text(_summary_log_preamble())
    lines = _summary_log_lines(results, started)
    with SUMMARY_LOG.open("a") as f:
        f.write("\n".join(lines) + "\n")


REPORT_SUMMARY_JOBS = {
    "Dead Code Auditor",
    "Pipeline Audit (30 prompts)",
    "Doc Drift Auditor",
    "Transcript Quality Review",
}


def existing_job_artifacts(name: str) -> list[str]:
    return [
        str(artifact)
        for artifact in JOB_ARTIFACTS.get(name, [])
        if artifact.exists()
    ]


def primary_job_report_text(name: str) -> str:
    artifacts = JOB_ARTIFACTS.get(name, [])
    return _read_text(artifacts[0]) if artifacts else ""


def job_output_summary(
    name: str,
    report_text: str,
    log_tail: str,
) -> tuple[list[str], list[str], list[str]]:
    followups: list[str] = []
    if name == "Dead Code Auditor":
        problems, improvements = _summarize_dead_code(report_text, log_tail)
    elif name == "Pipeline Audit (30 prompts)":
        problems, improvements = _summarize_pipeline(report_text, log_tail)
    elif name == "Doc Drift Auditor":
        problems, improvements = _summarize_doc_drift(report_text, log_tail)
    elif name == "Transcript Quality Review":
        problems, improvements = _summarize_transcript_review(report_text, log_tail)
        followups = _extract_field(report_text, "Suggested fix", limit=4)
    else:
        problems, improvements = _summarize_generic_log(log_tail)
    return problems, improvements, followups


def _job_details(result: dict) -> dict:
    name = result["name"]
    raw_log_path = str(result.get("log") or "").strip()
    log_tail = _read_job_log(result)
    problems: list[str] = []
    improvements: list[str] = []

    if result["status"] != "ok":
        problems.append(_bullet(f"Job ended with status `{result['status']}`."))

    artifacts = existing_job_artifacts(name)
    report_text = primary_job_report_text(name) if name in REPORT_SUMMARY_JOBS else ""
    p, i, followups = job_output_summary(name, report_text, log_tail)
    problems.extend(p)
    improvements.extend(i)
    if raw_log_path:
        artifacts.append(raw_log_path)

    # Compact lists for the TL;DR block at the top of the report — the user
    # wants "list of problems you found and the fix you applied" as the
    # minimum info, so we emit up to 3 of each per stage, truncated.
    problems_tldr_list = _condense_tldr_items(
        problems,
        skip_prefixes=("Job ended with status",),
    )
    fixes_tldr_list = _condense_tldr_items(
        improvements,
        skip_prefixes=("No concrete improvement",),
    )

    return {
        "name": name,
        "status": result["status"],
        "elapsed_s": result["elapsed_s"],
        "purpose": JOB_PURPOSES.get(name, "Ran this self-improvement stage."),
        "problems": problems or [_bullet("No problems were detected in the available logs/reports.")],
        "improvements": improvements or [_bullet("No concrete improvement was recorded in the available logs/reports.")],
        "followups": followups,
        "artifacts": artifacts,
        "problems_tldr_list": problems_tldr_list,
        "fixes_tldr_list": fixes_tldr_list,
    }


def write_readable_report(results: list[dict], started: dt.datetime, total_s: float) -> Path:
    """Write the human-readable latest self-improvement report and archive it."""
    READABLE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_READABLE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    details = [_job_details(r) for r in results]

    ok, timeout, failed = _status_counts(results)
    archive_path = _unique_archive_path(READABLE_REPORT_DIR, started)

    # TL;DR block — designed so anyone (or an assistant) can read the first
    # ~40 lines and give a full-picture answer without scanning the whole
    # report. Per stage: header line, then indented "Problems:" and "Fixes:"
    # sub-lists (each capped at 3 items, truncated to ~160 chars).
    tldr_stage_lines = _tldr_stage_lines(results, details)
    top_followups = _top_followups(details)

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
        "## TL;DR",
        "",
        *tldr_stage_lines,
        "",
    ]
    if top_followups:
        lines.append("**Top follow-ups:**")
        lines.append("")
        for f in top_followups[:3]:
            lines.append(f"- {f}")
        lines.append("")

    lines.extend([
        "## Executive Summary",
        "",
    ])
    lines.extend(_executive_summary_lines(timeout, failed, details))

    for idx, detail in enumerate(details, 1):
        lines.extend(_stage_detail_lines(idx, detail))

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
# Format: (name, script_path_relative_to_VESSENCE_HOME, args_list, timeout_minutes_or_None)

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
    # Code Auditor runs BEFORE Dead Code Auditor. It needs a clean working
    # tree (it skips itself otherwise), so it must run right after the
    # pre-commit above, before any later stage modifies files. Swapping
    # these two fixes the "skipped: uncommitted changes" pattern that
    # happened every night while Dead Code Auditor ran first and deleted
    # files before Code Auditor got its turn.
    (
        "Code Auditor",
        "agent_skills/nightly_code_auditor.py",
        [],
        30,
    ),
    (
        "Dead Code Auditor",
        "agent_skills/dead_code_auditor.py",
        [],
        15,
    ),
    (
        "Pipeline Audit (30 prompts)",
        "agent_skills/pipeline_audit_100.py",
        ["--n", "30", "--no-fixes"],
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
    # per-stage (classification, handler, Opus, client). Nightly runs are
    # report-only; Claude validation/fixes require a manual --apply-fixes run.
    (
        "Transcript Quality Review",
        "agent_skills/transcript_quality_review.py",
        ["--skip-fixes"],
        20,
    ),
    # Memory Janitor runs LAST — purges expired short-term memories,
    # deduplicates long-term entries, archives conversation themes,
    # and cleans stale log files. Uses the configured frontier provider for
    # dedup merging, so it's expensive; once per night is sufficient.
    (
        "Memory Janitor",
        "memory/v1/janitor_memory.py",
        [],
        120,
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
