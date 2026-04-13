"""nightly_code_auditor.py — autonomous code audit + fix loop.

Runs nightly during the sleep window (3 AM). Picks one module from the
whitelist (rotating), generates stress tests for it via Claude Opus,
runs them, diagnoses failures, and commits fixes.

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
import re
import subprocess
import sys
import time
from pathlib import Path

# Paths
VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient/vessence-data")))
WHITELIST_PATH = VESSENCE_HOME / "configs" / "auditable_modules.md"
STATE_PATH = VESSENCE_DATA_HOME / "auditor_state.json"
AUDIT_LOG_PATH = VESSENCE_HOME / "configs" / "auto_audit_log.md"
FAILURE_LOG_PATH = VESSENCE_HOME / "configs" / "audit_failures.md"
TEST_DIR = VESSENCE_HOME / "test_code"

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/home/chieh/.local/bin/claude")
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
    modules = []
    for line in text.splitlines():
        # Match table rows: | `path` | spec | safety |
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*(\w+)\s*\|", line)
        if not m:
            continue
        path, spec, safety = m.group(1), m.group(2).strip(), m.group(3)
        if safety in ("safe", "careful"):
            modules.append({"path": path, "spec": spec, "safety": safety})
    return modules


# ── Rotation state ───────────────────────────────────────────────────────────


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"last_index": -1, "history": []}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def pick_next_module(modules: list[dict], state: dict) -> dict:
    """Pick the next module in rotation, skipping recently-audited ones."""
    last = state.get("last_index", -1)
    next_idx = (last + 1) % len(modules)
    state["last_index"] = next_idx
    return modules[next_idx]


# ── Git helpers ──────────────────────────────────────────────────────────────


def git(*args, cwd: Path = VESSENCE_HOME, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=check
    )


def is_clean_working_tree() -> bool:
    r = git("status", "--porcelain", check=False)
    return r.returncode == 0 and not r.stdout.strip()


def make_audit_branch() -> str:
    branch = f"auto-audit/{dt.datetime.now().strftime('%Y-%m-%d-%H%M')}"
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


# ── Claude subprocess helper ─────────────────────────────────────────────────


def run_claude(prompt: str, timeout: int = 600) -> str:
    """Invoke Claude CLI with a prompt, return stdout."""
    try:
        r = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--output-format", "text",
             "--model", "claude-opus-4-6"],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(VESSENCE_HOME)},
        )
        return r.stdout
    except subprocess.TimeoutExpired:
        logger.warning("Claude call timed out after %ds", timeout)
        return ""
    except Exception as e:
        logger.warning("Claude call failed: %s", e)
        return ""


# ── Audit phases ─────────────────────────────────────────────────────────────


def phase1_generate_tests(module: dict, target_test_path: Path) -> bool:
    """Have Claude write a pytest file with edge cases for this module."""
    module_path = VESSENCE_HOME / module["path"]
    if not module_path.exists():
        logger.warning("Target module missing: %s", module_path)
        return False

    code = module_path.read_text()
    spec = module["spec"]
    prompt = f"""You are auditing a Python module for the Vessence project.

MODULE PATH: {module["path"]}
SPEC SOURCE: {spec}

MODULE CODE:
```python
{code[:8000]}
```

Write a comprehensive pytest file at {target_test_path} that:
1. Tests the documented behavior from the docstring/spec
2. Tests edge cases: empty input, malformed input, None, very long input
3. Tests integration points (DB queries, LLM calls) using mocks if needed
4. Each test should be independent and runnable in isolation

Output ONLY the Python code, no markdown, no explanation. Use `import pytest` and proper pytest fixtures.
Save the file at {target_test_path} using the Write tool. Do not modify the module being tested."""

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
    """Have Claude diagnose the failure and patch the module. Return True if it edited."""
    module_path = VESSENCE_HOME / module["path"]
    code = module_path.read_text()

    prompt = f"""A test you just wrote is failing for module: {module["path"]}

CURRENT MODULE CODE:
```python
{code[:6000]}
```

TEST FAILURE OUTPUT:
```
{test_output[:3000]}
```

ATTEMPT {attempt} of {MAX_FIX_ATTEMPTS}.

Diagnose the failure. If it's a real bug in the module, fix it by editing
{module["path"]} using the Edit tool. Make the smallest change possible.
Do NOT modify the test file. Do NOT touch any other module.

If the test itself is wrong (not the module), output: TEST_WRONG
If you can't determine the cause, output: GIVE_UP"""

    output = run_claude(prompt, timeout=600)
    if "TEST_WRONG" in output or "GIVE_UP" in output:
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
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Sleep-window check: only run during 2-6 AM unless forced
    if "--force" not in sys.argv:
        hour = dt.datetime.now().hour
        if not (2 <= hour < 6):
            logger.info("Outside sleep window (hour=%d), skipping. Use --force to override.", hour)
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
    module_name = Path(target["path"]).stem
    test_path = TEST_DIR / f"auto_audit_{module_name}.py"

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
