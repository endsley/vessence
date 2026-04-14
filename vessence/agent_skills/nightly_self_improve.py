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
    (
        "Doc Drift Auditor",
        "agent_skills/doc_drift_auditor.py",
        [],
        5,
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
