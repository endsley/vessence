"""nightly_self_improve.py — orchestrates all self-improvement jobs at 3 AM.

Single cron entry, runs each improvement sequentially. Each job has its
own time budget; if a job exceeds it the orchestrator moves on to the
next. Each job logs to its own section of `configs/self_improve_log.md`.

Add new improvements by appending to the JOBS list at the bottom.

Cron:
  0 3 * * * /home/.../python /home/.../agent_skills/nightly_self_improve.py
"""

from __future__ import annotations

import datetime as dt
import os
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


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with ORCHESTRATOR_LOG.open("a") as f:
        f.write(line + "\n")


def run_job(name: str, script: str, args: list[str], timeout_min: int) -> dict:
    """Run a job script with a time budget. Return summary dict."""
    started = time.time()
    log(f"=== Starting: {name} (timeout={timeout_min}min) ===")

    cmd = [PYTHON, str(VESSENCE_HOME / script)] + args
    log_path = LOG_DIR / f"self_improve_{Path(script).stem}.log"

    try:
        with log_path.open("a") as logf:
            logf.write(f"\n\n===== Run {dt.datetime.now().isoformat()} =====\n")
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
        return {"name": name, "status": status, "elapsed_s": int(elapsed), "log": str(log_path)}
    except subprocess.TimeoutExpired:
        elapsed = time.time() - started
        log(f"=== TIMEOUT: {name} after {elapsed:.0f}s — moving on ===")
        return {"name": name, "status": "timeout", "elapsed_s": int(elapsed), "log": str(log_path)}
    except Exception as e:
        elapsed = time.time() - started
        log(f"=== CRASHED: {name} ({e}) ===")
        return {"name": name, "status": f"crashed: {e}", "elapsed_s": int(elapsed), "log": str(log_path)}


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
                f"All {ok} self-improvement jobs finished cleanly overnight."
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
            "I logged the failures to the orchestrator log for you to "
            "review"
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
    _log_vocal_rollup(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
