"""Pure helpers for nightly_code_auditor.py."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any


EXPECTED_REPORT_OUTPUTS = (
    "configs/dead_code_report.md",
    "configs/pipeline_audit_report.md",
    "configs/doc_drift_report.md",
    "configs/transcript_review_report.md",
    "configs/self_improve_log.md",
    "configs/auto_audit_log.md",
    "configs/audit_failures.md",
)


def parse_whitelist_modules(text: str) -> list[dict[str, str]]:
    modules = []
    for line in text.splitlines():
        match = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*(\w+)\s*\|", line)
        if not match:
            continue
        path, spec, safety = match.group(1), match.group(2).strip(), match.group(3)
        if safety in ("safe", "careful"):
            modules.append({"path": path, "spec": spec, "safety": safety})
    return modules


def default_auditor_state() -> dict[str, Any]:
    return {"last_index": -1, "history": []}


def pick_next_module_in_rotation(modules: list[dict], state: dict) -> dict:
    last = state.get("last_index", -1)
    next_idx = (last + 1) % len(modules)
    state["last_index"] = next_idx
    return modules[next_idx]


def audit_sleep_window_allowed(
    argv: list[str],
    now: dt.datetime,
    *,
    force_flag: str = "--force",
    start_hour: int = 1,
    end_hour: int = 7,
) -> bool:
    return force_flag in argv or start_hour <= now.hour < end_hour


def nonblank_porcelain_lines(status_stdout: str) -> list[str]:
    return [line for line in status_stdout.splitlines() if line.strip()]


def porcelain_path(line: str) -> str:
    return line[3:].strip()


def unexpected_porcelain_changes(
    lines: list[str],
    expected_outputs: tuple[str, ...] = EXPECTED_REPORT_OUTPUTS,
) -> list[str]:
    unexpected = []
    for line in lines:
        path = porcelain_path(line)
        if path in expected_outputs:
            continue
        if path.startswith(".git.backup"):
            continue
        unexpected.append(line)
    return unexpected


def audit_report_stash_name(now: dt.datetime) -> str:
    return f"auditor-pre-report-stash-{now.strftime('%Y%m%d-%H%M%S')}"


def audit_branch_name(now: dt.datetime) -> str:
    return f"auto-audit/{now.strftime('%Y-%m-%d-%H%M')}"


def auto_audit_test_path(module_path: str, test_dir: Path) -> Path:
    module_name = Path(module_path).stem
    return test_dir / f"auto_audit_{module_name}.py"


def integration_contract_context(module_path: str, integrations_text: str) -> str:
    if module_path not in integrations_text:
        return ""
    return (
        "\n\nCROSS-STACK INTEGRATION CONTRACTS:\n"
        "This module participates in cross-stack contracts. The full\n"
        "contract file is below — write tests that verify the invariants\n"
        "for any contract where this module is the Producer:\n\n"
        + integrations_text
    )


def audit_test_generation_prompt(
    module: dict[str, str],
    module_code: str,
    target_test_path: Path,
    integrations: str = "",
) -> str:
    return f"""You are auditing a Python module for the Vessence project.

MODULE PATH: {module["path"]}
SPEC SOURCE: {module["spec"]}{integrations}

MODULE CODE:
```python
{module_code[:8000]}
```

Write a comprehensive pytest file at {target_test_path} that includes:

1. **Behavioral tests** — verify documented behavior from docstring/spec
2. **Edge cases** — empty input, malformed input, None, very long input
3. **Integration points** — DB queries, LLM calls (use mocks if needed)
4. **STRUCTURAL INVARIANTS** (CRITICAL — these catch the highest-leverage bugs):
   - If the module has a mapping/lookup table (dict, registry), test that:
     a. No key maps to a value that contradicts other invariants
       (e.g. classifier wrappers must not return "High" confidence with
        a fallback class like "others" — that's a logical contradiction)
     b. Every key referenced elsewhere in the codebase exists in the table
     c. Every value in the table is reachable from at least one input
   - If the module has destructive operations (delete, end_conversation,
     send_message, sms_send_direct, irreversible state changes), test that:
     a. They require a strict confidence threshold (>= 0.80, not just "High")
     b. They cannot fire on borderline / ambiguous input
   - If the module has a class registry / handler dispatch, test that:
     a. Every registered class has a corresponding handler OR is explicitly
        documented as "no handler — escalates"
     b. Every handler returns the documented shape (dict with "text" key)

5. **Each test should be independent and runnable in isolation**

Output ONLY the Python code, no markdown, no explanation. Use `import pytest` and proper pytest fixtures.
Save the file at {target_test_path} using the Write tool. Do not modify the module being tested."""


def audit_fix_prompt(
    module_path: str,
    module_code: str,
    test_output: str,
    attempt: int,
    max_fix_attempts: int,
) -> str:
    return f"""A test you just wrote is failing for module: {module_path}

CURRENT MODULE CODE:
```python
{module_code[:6000]}
```

TEST FAILURE OUTPUT:
```
{test_output[:3000]}
```

ATTEMPT {attempt} of {max_fix_attempts}.

Diagnose the failure. If it's a real bug in the module, fix it by editing
{module_path} using the Edit tool. Make the smallest change possible.
Do NOT modify the test file. Do NOT touch any other module.

If the test itself is wrong (not the module), output: TEST_WRONG
If you can't determine the cause, output: GIVE_UP"""


def fix_attempt_declined(output: str) -> bool:
    return "TEST_WRONG" in output or "GIVE_UP" in output
