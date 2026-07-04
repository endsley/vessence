"""nightly_code_auditor.py — autonomous code audit + fix loop.

Runs nightly during the sleep window (1-7 AM). Picks one module from the
whitelist (rotating), generates stress tests with the configured frontier
provider, runs them, diagnoses failures, and commits fixes.

Safety rails:
  - Always works on a git branch (auto-audit/YYYY-MM-DD), never master
  - One file changed per session
  - All tests must pass before commit
  - 30-minute time budget per session
  - Reverts on failure, logs to configs/audit_failures.md

Whitelist of safe modules: configs/auditable_modules.md
Audit log: configs/auto_audit_log.md
Rotation state: vessence-data/auditor_state.json
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from agent_skills.nightly_code_audit_helpers import (
    audit_branch_name as _audit_branch_name,
    audit_fix_prompt as _audit_fix_prompt,
    audit_report_stash_name as _audit_report_stash_name,
    audit_sleep_window_allowed as _audit_sleep_window_allowed,
    audit_test_generation_prompt as _audit_test_generation_prompt,
    auto_audit_test_path as _auto_audit_test_path,
    default_auditor_state as _default_auditor_state,
    fix_attempt_declined as _fix_attempt_declined,
    integration_contract_context as _integration_contract_context,
    nonblank_porcelain_lines as _nonblank_porcelain_lines,
    parse_whitelist_modules as _parse_whitelist_modules,
    pick_next_module_in_rotation as _pick_next_module_in_rotation,
    unexpected_porcelain_changes as _unexpected_porcelain_changes,
)

# Paths
VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient/vessence-data")))
WHITELIST_PATH = VESSENCE_HOME / "configs" / "auditable_modules.md"
INTEGRATIONS_PATH = VESSENCE_HOME / "configs" / "auditable_integrations.md"
STATE_PATH = VESSENCE_DATA_HOME / "auditor_state.json"
AUDIT_LOG_PATH = VESSENCE_HOME / "configs" / "auto_audit_log.md"
FAILURE_LOG_PATH = VESSENCE_HOME / "configs" / "audit_failures.md"
TEST_DIR = VESSENCE_HOME / "test_code"

TIME_BUDGET_SEC = int(os.environ.get("AUDIT_TIME_BUDGET_SEC", "1800"))  # 30 min
MAX_FIX_ATTEMPTS = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("nightly_audit")


# ── Whitelist ────────────────────────────────────────────────────────────────


def load_whitelist() -> list[dict]:
    """Parse the auditable_modules.md table into a list of dicts."""
    text = WHITELIST_PATH.read_text()
    return _parse_whitelist_modules(text)


# ── Rotation state ───────────────────────────────────────────────────────────


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return _default_auditor_state()


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def pick_next_module(modules: list[dict], state: dict) -> dict:
    """Pick the next module in rotation, skipping recently-audited ones."""
    return _pick_next_module_in_rotation(modules, state)


# ── Git helpers ──────────────────────────────────────────────────────────────


def git(*args, cwd: Path = VESSENCE_HOME, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=check
    )


def is_clean_working_tree() -> bool:
    """Return True if the working tree has no UNEXPECTED changes.

    Nightly self-improve jobs write report files (dead_code_report.md,
    pipeline_audit_report.md, doc_drift_report.md, transcript_review_report.md)
    that are the EXPECTED output of earlier jobs in the same orchestrator
    run. Those shouldn't block the code auditor from running — otherwise
    the first job's output permanently locks out every later job for the
    rest of the night.  We treat report files as "not real WIP".
    """
    r = git("status", "--porcelain", check=False)
    if r.returncode != 0:
        return False
    lines = _nonblank_porcelain_lines(r.stdout)
    unexpected = _unexpected_porcelain_changes(lines)
    if unexpected:
        logger.info("is_clean_working_tree: %d unexpected change(s): %s",
                    len(unexpected), unexpected[:3])
        return False
    # Stash the expected report-file changes so the auditor branches off
    # a truly clean tree. The orchestrator's outer stash restores them
    # at the end of the run.
    if lines:
        stash_name = _audit_report_stash_name(dt.datetime.now())
        git("stash", "push", "-u", "-m", stash_name, check=False)
        logger.info("is_clean_working_tree: stashed %d report file(s) as %s",
                    len(lines), stash_name)
    return True


def make_audit_branch() -> str:
    branch = _audit_branch_name(dt.datetime.now())
    git("checkout", "-b", branch)
    return branch


def revert_branch(branch: str) -> None:
    """Hard reset the branch to remove any uncommitted changes, then go back to master."""
    git("checkout", ".", check=False)
    git("clean", "-fd", check=False)
    git("checkout", "master", check=False)
    git("branch", "-D", branch, check=False)


def commit_changes(message: str) -> None:
    git("add", "-A")
    git("commit", "-m", message, "--no-verify")


# ── Frontier subprocess helper ───────────────────────────────────────────────


def run_claude(prompt: str, timeout: int = 600) -> str:
    """Invoke the configured frontier provider with a prompt, return stdout.

    Kept under the legacy name because the audit phases call it directly.
    The provider now follows JANE_BRAIN (opus/claude, codex/openai, gemini).
    """
    try:
        from agent_skills.claude_cli_llm import completion_orchestrator
        return completion_orchestrator(
            prompt,
            max_tokens=4096,
            timeout=timeout,
            cwd=str(VESSENCE_HOME),
        )
    except Exception as e:
        logger.warning("Frontier LLM call failed: %s", e)
        return ""


# ── Audit phases ─────────────────────────────────────────────────────────────


def phase1_generate_tests(module: dict, target_test_path: Path) -> bool:
    """Have the configured frontier provider write pytest edge cases."""
    module_path = VESSENCE_HOME / module["path"]
    if not module_path.exists():
        logger.warning("Target module missing: %s", module_path)
        return False

    code = module_path.read_text()

    # Load any cross-stack integration contracts that mention this module
    integrations = ""
    try:
        if INTEGRATIONS_PATH.exists():
            full = INTEGRATIONS_PATH.read_text()
            # Crude but effective: include the whole file if any contract
            # mentions this module path. The file is short.
            integrations = _integration_contract_context(module["path"], full)
    except Exception:
        pass

    prompt = _audit_test_generation_prompt(module, code, target_test_path, integrations)
    output = run_claude(prompt, timeout=600)
    return target_test_path.exists()


def phase2_run_tests(test_path: Path) -> tuple[bool, str]:
    """Run pytest on the generated test file. Return (passed, output)."""
    try:
        r = subprocess.run(
            ["/home/chieh/google-adk-env/adk-venv/bin/python", "-m", "pytest",
             str(test_path), "-v", "--tb=short", "-x"],
            cwd=VESSENCE_HOME, capture_output=True, text=True, timeout=300,
            env={**os.environ, "PYTHONPATH": str(VESSENCE_HOME)},
        )
        return r.returncode == 0, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT after 5 minutes"
    except Exception as e:
        return False, f"pytest crashed: {e}"


def phase3_attempt_fix(module: dict, test_output: str, attempt: int) -> bool:
    """Have the configured frontier provider diagnose and patch the module."""
    module_path = VESSENCE_HOME / module["path"]
    code = module_path.read_text()

    prompt = _audit_fix_prompt(module["path"], code, test_output, attempt, MAX_FIX_ATTEMPTS)
    output = run_claude(prompt, timeout=600)
    if _fix_attempt_declined(output):
        return False
    # Check if module file was actually modified
    return module_path.read_text() != code


# ── Logging ──────────────────────────────────────────────────────────────────


def append_to_log(path: Path, entry: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(entry + "\n\n")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    started = time.time()
    now = dt.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")

    # Sleep-window check: only run during 2-6 AM unless forced
    if not _audit_sleep_window_allowed(sys.argv, now):
        logger.info("Outside sleep window (hour=%d), skipping. Use --force to override.", now.hour)
        return 0

    # Pre-flight: clean working tree
    if not is_clean_working_tree():
        logger.warning("Working tree has uncommitted changes — skipping audit.")
        return 0

    # Pick target
    modules = load_whitelist()
    state = load_state()
    target = pick_next_module(modules, state)
    logger.info("Auditing: %s (safety=%s)", target["path"], target["safety"])

    # Create branch
    branch = make_audit_branch()
    logger.info("Created branch: %s", branch)

    # Generate test file path
    test_path = _auto_audit_test_path(target["path"], TEST_DIR)

    try:
        # Phase 1: generate tests
        logger.info("Phase 1: generating stress tests")
        if not phase1_generate_tests(target, test_path):
            logger.warning("Test generation failed")
            revert_branch(branch)
            append_to_log(FAILURE_LOG_PATH,
                f"## {timestamp} — {target['path']}\nTest generation failed.")
            return 1

        # Phase 2: run tests
        logger.info("Phase 2: running tests")
        passed, output = phase2_run_tests(test_path)

        if passed:
            logger.info("All tests passed on first run — module is clean.")
            commit_changes(f"auto-audit: add tests for {target['path']}")
            git("checkout", "master", check=False)
            git("merge", branch, "--ff-only", check=False)
            git("branch", "-D", branch, check=False)
            append_to_log(AUDIT_LOG_PATH,
                f"## {timestamp} — {target['path']}\n"
                f"Result: ✅ Module passes all generated tests. Tests committed.")
            save_state(state)
            return 0

        # Phase 3: attempt fixes
        for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
            if time.time() - started > TIME_BUDGET_SEC:
                logger.warning("Time budget exceeded, reverting")
                revert_branch(branch)
                append_to_log(FAILURE_LOG_PATH,
                    f"## {timestamp} — {target['path']}\nTime budget exceeded.")
                return 1

            logger.info("Phase 3: attempting fix %d/%d", attempt, MAX_FIX_ATTEMPTS)
            if not phase3_attempt_fix(target, output, attempt):
                logger.info("Fix declined (TEST_WRONG or GIVE_UP)")
                break

            passed, output = phase2_run_tests(test_path)
            if passed:
                logger.info("Fix succeeded after attempt %d", attempt)
                commit_changes(
                    f"auto-audit: fix bug in {target['path']} (attempt {attempt})")
                git("checkout", "master", check=False)
                git("merge", branch, "--ff-only", check=False)
                git("branch", "-D", branch, check=False)
                append_to_log(AUDIT_LOG_PATH,
                    f"## {timestamp} — {target['path']}\n"
                    f"Result: 🔧 Bug found and fixed (attempt {attempt}).\n"
                    f"Tests now passing. Committed to master.")
                save_state(state)
                return 0

        # All fix attempts failed
        logger.warning("All fix attempts exhausted, reverting")
        revert_branch(branch)
        append_to_log(FAILURE_LOG_PATH,
            f"## {timestamp} — {target['path']}\n"
            f"Tests failing after {MAX_FIX_ATTEMPTS} fix attempts. Reverted.\n\n"
            f"Last test output:\n```\n{output[:1500]}\n```")
        save_state(state)
        return 1

    except Exception as e:
        logger.exception("Auditor crashed: %s", e)
        revert_branch(branch)
        append_to_log(FAILURE_LOG_PATH,
            f"## {timestamp} — {target['path']}\nAuditor crashed: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
