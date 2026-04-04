#!/usr/bin/env python3
"""
nightly_audit.py — Periodic code + documentation consistency audit.

Runs every 6 hours via cron, but ONLY if the user is idle. Per run:
  1. Checks if user is idle (no Jane web/CLI activity in the last 15 minutes)
  2. Gathers system state: crontab, skill files, key docs
  3. Asks Jane via the shared automation runner to audit code vs documentation alignment
     and identify improvement opportunities
  4. Saves the report to logs/audits/audit_<datetime>.md
"""

import os
import sys
import json
import subprocess
import datetime
import logging
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import (
    JANE_BRIDGE_ENV, LOGS_DIR, ADK_VENV_PYTHON, VESSENCE_HOME,
)
from jane.automation_runner import AutomationError, run_automation_prompt

# ─── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE         = JANE_BRIDGE_ENV
AUDIT_LOG_DIR    = Path(LOGS_DIR) / "audits"
SKILLS_DIR       = Path(VESSENCE_HOME) / "agent_skills"
CONFIGS_DIR      = Path(VESSENCE_HOME) / "configs"
CRON_JOBS_DOC    = CONFIGS_DIR / "CRON_JOBS.md"
SKILLS_REGISTRY  = CONFIGS_DIR / "SKILLS_REGISTRY.md"
JANE_ARCH        = CONFIGS_DIR / "Jane_architecture.md"
AMBER_ARCH       = CONFIGS_DIR / "Amber_architecture.md"
MEMORY_ARCH      = CONFIGS_DIR / "memory_manage_architecture.md"

LOG_FILE = Path(LOGS_DIR) / "nightly_audit.log"
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [nightly_audit] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(LOG_FILE)],
)
logger = logging.getLogger("nightly_audit")


# ─── Helpers ──────────────────────────────────────────────────────────────────
def read_file(path, max_chars=3000):
    try:
        text = Path(path).read_text()
        if len(text) > max_chars:
            return text[:max_chars] + f"\n... [truncated at {max_chars} chars]"
        return text
    except Exception as e:
        return f"[Error reading {path}: {e}]"


def read_script_body(path, max_lines=200):
    """Read the first max_lines of a script file for audit analysis."""
    try:
        lines = Path(path).read_text().splitlines()[:max_lines]
        return "\n".join(lines)
    except Exception as e:
        return f"[Error reading {path}: {e}]"


# Key scripts whose bodies the audit should inspect for code/doc drift
KEY_SCRIPTS = [
    "agent_skills/janitor_memory.py",
    "agent_skills/janitor_system.py",
    "agent_skills/generate_identity_essay.py",
    "agent_skills/check_for_updates.py",
    "agent_skills/ambient_heartbeat.py",
    "startup_code/regenerate_jane_context.py",
]


def get_crontab():
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        return result.stdout.strip() or "(empty crontab)"
    except Exception as e:
        return f"[Error reading crontab: {e}]"


def get_skill_files():
    return sorted(p.name for p in SKILLS_DIR.glob("*.py") if p.name != "__init__.py")


def get_amber_tool_files():
    amber_tools = Path(VESSENCE_HOME) / "amber" / "tools"
    if amber_tools.exists():
        return sorted(p.name for p in amber_tools.glob("*.py"))
    return []


from agent_skills.cron_utils import send_discord


# Idle detection: user must have no activity for this many seconds
IDLE_THRESHOLD_SECONDS = 900  # 15 minutes

# Files that indicate user activity (modification time = last activity)
ACTIVITY_INDICATORS = [
    Path(LOGS_DIR) / "jane_request_timing.log",  # Jane web chat
    Path(LOGS_DIR) / "jane_web.log",              # Jane web server
]


def is_user_idle() -> bool:
    """Check if the user is idle by looking at recent Jane activity and active CLI sessions."""
    now = time.time()

    # Check 1: any recent Jane web/CLI activity via log file modification times
    for indicator in ACTIVITY_INDICATORS:
        if indicator.exists():
            mtime = indicator.stat().st_mtime
            if now - mtime < IDLE_THRESHOLD_SECONDS:
                logger.info("User active: %s modified %ds ago", indicator.name, int(now - mtime))
                return False

    # Check 2: is there an active Claude CLI process running (e.g. user chatting on CLI)
    try:
        result = subprocess.run(
            ["pgrep", "-f", "claude.*--print.*-p"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            logger.info("User active: Claude CLI process running")
            return False
    except Exception:
        pass

    # Check 3: is there an active prompt queue item being processed
    try:
        result = subprocess.run(
            ["pgrep", "-f", "prompt_queue_runner"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            logger.info("Skipping: prompt queue runner is active")
            return False
    except Exception:
        pass

    logger.info("User is idle — proceeding with audit")
    return True


def _run_cmd(cmd, fallback='(unavailable)'):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return fallback


def run_audit_and_fix(context: dict) -> str:
    """Run the audit+fix prompt via the shared automation runner.

    The LLM is instructed to:
    1. Diagnose issues (code vs docs, code quality)
    2. Immediately fix all safe issues (Category A/B)
    3. Report what was found, what was fixed, and what needs human review
    """
    prompt = f"""You are performing a periodic technical audit of the Project Vessence AI assistant system.

## YOUR MANDATE
You must NOT just report problems. You must **immediately fix** every issue you find, using the tools available to you (Read, Edit, Write, Bash, Grep, Glob). Only flag issues for human review if they involve security, architecture changes, or deleting user data.

## AUDIT SCOPE
Check these two areas:
1. **Code vs documentation alignment** — Do the docs accurately describe what the code does? Fix anything stale, missing, or wrong.
2. **Code quality** — Fix any obvious bugs, missing error handling, dead code, or stale references.

## FIX RULES
- **Auto-fix immediately:** Stale doc paths, missing cron entries in CRON_JOBS.md, wrong variable names, dead env vars, outdated descriptions.
- **Auto-fix with care:** Cron ordering issues, dead migration scripts (move to archive).
- **Flag for human review (do NOT fix):** Security issues, architecture changes, anything that changes user-facing behavior, anything that deletes user data.
- Before editing any file, read it first. Make targeted edits, not full rewrites.
- After fixing, verify the fix is correct.

## REPORT FORMAT
After fixing everything, produce a report with:
- **Health Summary** (1-2 sentences)
- **Fixed Issues** — table: | Issue | File | Fix Applied |
- **Flagged for Review** — issues you did NOT fix and why
- **Defensive Recommendations** — max 3 suggestions to prevent these issues from recurring

Keep the report under 800 words.

---

## SYSTEM STATE

### Actual crontab:
{context['crontab']}

### agent_skills/ files on disk:
{json.dumps(context['skill_files'], indent=2)}

### amber/tools/ files on disk:
{json.dumps(context['amber_tools'], indent=2)}

### CRON_JOBS.md (documentation):
{context['cron_jobs_doc']}

### SKILLS_REGISTRY.md (documentation):
{context['skills_registry']}

### Jane_architecture.md (excerpt):
{context['jane_arch']}

### memory_manage_architecture.md (excerpt):
{context['memory_arch']}

### Key script bodies (first ~200 lines each):
{context['script_bodies']}
"""
    try:
        # Run in yolo mode so the LLM can actually edit files to fix issues
        old_mode = os.environ.get("JANE_EXECUTION_MODE")
        os.environ["JANE_EXECUTION_MODE"] = "yolo"
        try:
            return run_automation_prompt(
                prompt,
                timeout_seconds=600,  # longer timeout since it's now fixing things too
            )
        finally:
            if old_mode is None:
                os.environ.pop("JANE_EXECUTION_MODE", None)
            else:
                os.environ["JANE_EXECUTION_MODE"] = old_mode
    except AutomationError as e:
        return f"[Audit error: {e}]"


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H%M")
    logger.info(f"Audit triggered at {timestamp}")

    # Load gate: wait until CPU/memory is acceptable
    try:
        from agent_skills.system_load import wait_until_safe
        if not wait_until_safe(max_wait_minutes=15):
            logger.info("System busy — skipping audit this cycle.")
            return
    except Exception:
        pass

    # Idle gate: skip if user is active
    if not is_user_idle():
        logger.info("User is active — skipping audit this cycle.")
        return

    logger.info("User is idle — starting audit")

    # Read key script bodies for deeper code/doc drift detection
    script_bodies_parts = []
    for rel_path in KEY_SCRIPTS:
        full_path = Path(VESSENCE_HOME) / rel_path
        body = read_script_body(full_path, max_lines=200)
        script_bodies_parts.append(f"--- {rel_path} ---\n{body}")
    script_bodies = "\n\n".join(script_bodies_parts)

    context = {
        'crontab':        get_crontab(),
        'skill_files':    get_skill_files(),
        'amber_tools':    get_amber_tool_files(),
        'cron_jobs_doc':  read_file(CRON_JOBS_DOC),
        'skills_registry': read_file(SKILLS_REGISTRY),
        'jane_arch':      read_file(JANE_ARCH),
        'memory_arch':    read_file(MEMORY_ARCH),
        'script_bodies':  script_bodies,
    }

    logger.info("Running audit + fix prompt...")
    report = run_audit_and_fix(context)

    # Save full report with timestamp (multiple runs per day now)
    report_path = AUDIT_LOG_DIR / f"audit_{timestamp}.md"
    report_path.write_text(f"# Audit — {now.strftime('%Y-%m-%d %H:%M')}\n\n{report}\n")
    logger.info(f"Report saved to {report_path}")

    # Log notification
    header = f"Periodic Audit — {now.strftime('%Y-%m-%d %H:%M')}\n"
    send_discord(header + report[:1800])
    logger.info("Audit complete.")


if __name__ == "__main__":
    main()
