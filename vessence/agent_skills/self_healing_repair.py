#!/usr/bin/env python3
"""Autonomous LLM repair runner for self-healing incidents."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import json
import os
import sys
from pathlib import Path

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient/vessence-data")))
LOG_DIR = VESSENCE_DATA_HOME / "logs"
SELF_HEAL_DIR = VESSENCE_DATA_HOME / "self_healing"
REPORT_DIR = SELF_HEAL_DIR / "reports"

sys.path.insert(0, str(VESSENCE_HOME))


@contextlib.contextmanager
def _single_repair_lock():
    SELF_HEAL_DIR.mkdir(parents=True, exist_ok=True)
    path = SELF_HEAL_DIR / "repair.lock"
    with path.open("a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _allowed_project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    configured = os.environ.get("JANE_SELF_HEAL_PROJECT_ROOTS", "")
    allowed = [
        VESSENCE_HOME.resolve(),
        Path("/home/chieh/code/chieh_class_v2").resolve(),
    ]
    for item in configured.split(":"):
        if item.strip():
            allowed.append(Path(item).expanduser().resolve())
    if any(root == base or base in root.parents for base in allowed):
        return root
    raise SystemExit(f"Refusing self-healing outside allowed project roots: {root}")


def _read_text(path: Path, limit: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[-limit:] if len(text) > limit else text


def _collect_log_context(source: str, project_root: Path) -> str:
    chunks: list[str] = []
    candidates = [
        LOG_DIR / "jane_web.log",
        LOG_DIR / "self_healing.jsonl",
        LOG_DIR / "job_queue_runner.log",
        project_root / "PanGPA.log",
    ]
    for path in candidates:
        text = _read_text(path)
        if text:
            chunks.append(f"===== {path} (tail) =====\n{text}")
    return "\n\n".join(chunks)[-24000:]


def _write_incident_update(path: Path, **updates) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(updates)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def _build_prompt(incident: dict, incident_path: Path, project_root: Path) -> str:
    source = incident.get("source", "")
    logs = _collect_log_context(str(source), project_root)
    incident_json = json.dumps(incident, indent=2, sort_keys=True)
    return f"""You are Jane's self-healing repair runner.

Chieh wants Vessence and the education website to be robust and self-healing:
when an error is captured, Jane should inspect it manually, understand the
evidence, and fix the underlying issue when safe.

Incident file: {incident_path}
Project root: {project_root}
Source: {source}

Rules:
- Follow the project instructions in AGENTS.md or CLAUDE.md.
- Query Jane memory if the project instructions require it or if project history matters.
- Diagnose from evidence: read relevant source, logs, configs, and runtime state before explaining a cause.
- Do not revert unrelated dirty work. Preserve user changes.
- Before editing source code, acquire the shared code edit lock:
  `/home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/ambient/vessence/agent_skills/code_lock.py status`
  to inspect it, then use `agent_skills.code_lock.code_edit_lock(...)` around edits.
- Prefer the smallest fix that addresses the captured failure.
- Add or run focused tests when feasible. If tests are blocked, explain exactly why.
- Do not deploy, restart production services, delete data, rotate secrets, or run destructive commands.
- If the issue is transient, external, credential-related, CAPTCHA/MFA-related, or otherwise unsafe to patch automatically, write a clear report and stop.
- If this is a web/UI automation failure, inspect the page, DOM, screenshots, logs, or downloaded artifacts and adapt the flow rather than stopping at a stale selector.

Incident JSON:
```json
{incident_json}
```

Recent logs:
```text
{logs}
```

Complete the repair end to end if safe. Finish with a concise report including:
1. definite cause or evidence checked,
2. files changed,
3. verification commands and results,
4. any remaining risk or blocker.
"""


def run_repair(incident_path: Path) -> str:
    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    project_root = _allowed_project_root(str(incident.get("project_root") or VESSENCE_HOME))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    report_path = REPORT_DIR / f"{started.replace(':', '').replace('-', '')}_{incident.get('id', 'incident')}.md"
    _write_incident_update(
        incident_path,
        status="repair_started",
        repair_started_at=started,
        repair_report_path=str(report_path),
    )

    prompt = _build_prompt(incident, incident_path, project_root)
    try:
        from agent_skills.claude_cli_llm import completion_orchestrator
        output = completion_orchestrator(
            prompt,
            max_tokens=8192,
            timeout=int(os.environ.get("JANE_SELF_HEAL_REPAIR_TIMEOUT_SEC", "1800")),
            cwd=str(project_root),
        )
        status = "repair_finished"
    except Exception as exc:
        output = f"Self-healing repair runner failed before completing:\n\n{type(exc).__name__}: {exc}"
        status = "repair_failed"

    report = (
        f"# Self-Healing Repair Report\n\n"
        f"- Incident: `{incident_path}`\n"
        f"- Project root: `{project_root}`\n"
        f"- Started: `{started}`\n"
        f"- Finished: `{dt.datetime.now(dt.timezone.utc).isoformat()}`\n"
        f"- Status: `{status}`\n\n"
        f"## Runner Output\n\n{output}\n"
    )
    report_path.write_text(report, encoding="utf-8")
    _write_incident_update(
        incident_path,
        status=status,
        repair_finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        repair_report_path=str(report_path),
        repair_output_excerpt=output[:2000],
    )
    return str(report_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incident", required=True)
    args = parser.parse_args()
    incident_path = Path(args.incident).expanduser().resolve()
    with _single_repair_lock():
        report_path = run_repair(incident_path)
    print(f"self-healing repair report: {report_path}")


if __name__ == "__main__":
    main()
