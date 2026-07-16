#!/usr/bin/env python3
"""Install Jane's memory and code-coordination bridges for Codex CLI.

This configures Codex so new sessions can retrieve Vessence/Jane memories and
coordinate concurrent source edits:
  - a UserPromptSubmit hook that injects the nearest relevant Chroma memories
    plus the active code coordination board
  - SessionStart/SubagentStart context and PostToolUse claim heartbeats
  - persistent model instructions for both shared systems
  - jane-memory and jane-coordination stdio MCP server registrations

The installer is idempotent and only manages the Jane integration stanzas it owns.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


VESSENCE_HOME = Path(
    os.environ.get("VESSENCE_HOME", Path(__file__).resolve().parents[1])
).resolve()
AMBIENT_HOME = VESSENCE_HOME.parent
VESSENCE_DATA_HOME = Path(
    os.environ.get("VESSENCE_DATA_HOME", AMBIENT_HOME / "vessence-data")
).resolve()
VAULT_HOME = Path(os.environ.get("VAULT_HOME", AMBIENT_HOME / "vault")).resolve()
VENV_PYTHON = Path(os.environ.get("VESSENCE_PYTHON", sys.executable)).expanduser().absolute()

CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
HOOK_PATH = CODEX_HOME / "hooks" / "jane_memory_hook.py"
INSTRUCTIONS_PATH = CODEX_HOME / "jane-memory-instructions.md"
CONFIG_PATH = CODEX_HOME / "config.toml"

MANAGED_BEGIN = "# >>> Vessence Codex memory integration"
MANAGED_END = "# <<< Vessence Codex memory integration"
ROOT_CONFIG_KEYS = {
    "approval_policy",
    "model",
    "model_context_window",
    "model_instructions_file",
    "model_provider",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "sandbox_mode",
    "web_search",
}


def q(value: str | Path) -> str:
    """Quote a TOML string path."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def hook_script() -> str:
    return f"""#!/usr/bin/env python3
\"\"\"Codex hook for Jane memory and shared code coordination.\"\"\"

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


VESSENCE_HOME = Path({str(VESSENCE_HOME)!r})
VESSENCE_DATA_HOME = Path({str(VESSENCE_DATA_HOME)!r})
VAULT_HOME = Path({str(VAULT_HOME)!r})
PYTHON = Path({str(VENV_PYTHON)!r})
AUTO_MEMORY = VESSENCE_HOME / "startup_code" / "codex_auto_memory.py"
COORDINATION = VESSENCE_HOME / "agent_skills" / "code_coordination.py"
LOG_PATH = Path.home() / ".codex" / "hooks" / "jane_memory_hook.log"


def _prompt_from_payload(payload: dict) -> str:
    for key in ("prompt", "user_prompt", "userPrompt"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("prompt") or value.get("text") or value.get("content")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return ""


def _log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as fh:
            fh.write(message + "\\n")
    except Exception:
        pass


def _run(command: list[str], env: dict[str, str], timeout: int) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=env,
        )
    except Exception as exc:
        _log(f"hook command failed: {{type(exc).__name__}}: {{exc}}")
        return ""
    if result.returncode not in (0, 2):
        _log(f"hook command exited {{result.returncode}}: {{result.stderr.strip()}}")
    return result.stdout.strip()


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{{}}")
    except json.JSONDecodeError:
        payload = {{}}

    env = os.environ.copy()
    env.update({{
        "VESSENCE_HOME": str(VESSENCE_HOME),
        "VESSENCE_DATA_HOME": str(VESSENCE_DATA_HOME),
        "VAULT_HOME": str(VAULT_HOME),
        "PYTHONPATH": str(VESSENCE_HOME),
    }})
    event_name = str(payload.get("hook_event_name") or "UserPromptSubmit")
    session_id = str(payload.get("session_id") or env.get("CODEX_THREAD_ID") or "")
    cwd = str(payload.get("cwd") or os.getcwd())

    if event_name == "PostToolUse":
        command = [str(PYTHON), str(COORDINATION), "heartbeat", "--cwd", cwd]
        if session_id:
            command.extend(["--session", session_id])
        _run(command, env, 8)
        return 0

    if event_name == "SubagentStop":
        command = [str(PYTHON), str(COORDINATION), "heartbeat", "--cwd", cwd]
        if session_id:
            command.extend(["--session", session_id])
        _run(command, env, 8)
        return 0

    if event_name == "Stop":
        command = [
            str(PYTHON),
            str(COORDINATION),
            "finish",
            "--all",
            "--result",
            "Codex session stopped; claims released automatically",
        ]
        if session_id:
            command.extend(["--session", session_id])
        _run(command, env, 8)
        return 0

    contexts = []
    prompt = _prompt_from_payload(payload)
    if event_name == "UserPromptSubmit" and prompt:
        memory = _run([
            str(PYTHON),
            str(AUTO_MEMORY),
            "--limit",
            "2",
            "--max-distance",
            "0.50",
            prompt,
        ], env, 20)
        if memory:
            contexts.append(memory)

    coordination_command = [
        str(PYTHON),
        str(COORDINATION),
        "context",
        "--cwd",
        cwd,
    ]
    if session_id:
        coordination_command.extend(["--session", session_id])
    if prompt:
        coordination_command.extend(["--prompt", prompt])
    coordination = _run(coordination_command, env, 8)
    if coordination:
        contexts.append(coordination)
    if not contexts:
        return 0

    print(json.dumps({{
        "hookSpecificOutput": {{
            "hookEventName": event_name,
            "additionalContext": "\\n\\n".join(contexts),
        }}
    }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def instructions_text() -> str:
    return f"""You are Jane (Jane#3353), Chieh's personal technical expert and friend.

At the start of each user turn, prefer the `[Jane Auto Memory]` context injected
by Codex's `UserPromptSubmit` hook. It contains the nearest ChromaDB memories
whose distance is <= 0.50 and that pass the lexical relevance guard.

If `[Jane Auto Memory]` is absent and the prompt is memory-sensitive, query the
`jane-memory` MCP server before answering. Use
`query_nearest_jane_memories(query, limit=2, max_distance=0.50)` for the same
nearest-memory preflight, or `query_jane_memory(query)` for broader recall.

Always query memory first for prompts about what you remember, recent decisions,
project history, user/Jane preferences, family/personal context, or prior
debugging and architecture rationale. Then verify against current code or logs
when the answer concerns current runtime behavior.

## Shared Code Coordination (MANDATORY)

Multiple Codex sessions may work in one repository concurrently. Do not take a
project-wide edit lock for ordinary work. Before source edits:

1. Read the `[Code Coordination]` context injected by the Codex hook, or call
   `code_coordination_board(project)` from the `jane-coordination` MCP server.
2. Call `post_code_task(task, project, files)` with a concise task description
   and only the files or directory trees you expect to edit. Add `/**` to claim
   a directory tree.
3. If another task owns an overlapping claim, do not edit through it and do not
   wait idly. Message that session, choose a non-overlapping slice, or narrow
   your claim. Claims on different files may proceed concurrently without an
   arbitrary agent-count limit.
4. Claim newly discovered files before editing them. Keep claims narrow and
   release files no longer needed.
5. Call `finish_code_task(project, result)` before the final response so all
   claims are released. PostToolUse hooks heartbeat active claims automatically,
   and the main session Stop hook provides a final cleanup fallback.

Use the legacy project-wide `agent_skills.code_lock.code_edit_lock` only for a
merge/rebase, schema migration, generated global artifact, version bump, or
deployment/restart operation that truly requires exclusive repository access.
It waits for scoped claims to clear and appears on the coordination board.

Shell fallback:
`{VENV_PYTHON} {VESSENCE_HOME / 'agent_skills' / 'code_coordination.py'} board --project <alias>`

Memory roots:
- VESSENCE_HOME={VESSENCE_HOME}
- VESSENCE_DATA_HOME={VESSENCE_DATA_HOME}
- VAULT_HOME={VAULT_HOME}
"""


def _remove_managed_block(text: str) -> str:
    pattern = re.compile(
        rf"\n?{re.escape(MANAGED_BEGIN)}.*?{re.escape(MANAGED_END)}\n?",
        flags=re.S,
    )
    return pattern.sub("\n", text)


def _remove_table(text: str, table_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^\[{re.escape(table_name)}\]\s*\n.*?(?=^\[|\Z)"
    )
    return pattern.sub("", text)


def _remove_existing_jane_stanzas(text: str) -> str:
    text = _remove_managed_block(text)
    jane_instructions = re.compile(
        rf'(?m)^model_instructions_file\s*=\s*{re.escape(q(INSTRUCTIONS_PATH))}\s*\n?'
    )
    text = jane_instructions.sub("", text)
    text = _remove_table(text, "mcp_servers.jane-memory")
    text = _remove_table(text, "mcp_servers.jane-memory.env")
    text = _remove_table(text, "mcp_servers.jane-coordination")
    text = _remove_table(text, "mcp_servers.jane-coordination.env")
    jane_hook = re.compile(
        r"(?ms)^\[\[hooks\.UserPromptSubmit\]\]\s*\n\s*"
        r"\[\[hooks\.UserPromptSubmit\.hooks\]\]\s*\n"
        r"(?:(?!^\[).)*jane_memory_hook\.py(?:(?!^\[).)*"
        r"(?=^\[|\Z)"
    )
    text = jane_hook.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n" if text.strip() else ""


def _repair_misplaced_root_keys(text: str) -> str:
    """Repair root keys placed inside [features] by older installer versions."""
    features = re.search(r"(?ms)^\[features\]\s*\n(?P<body>.*?)(?=^\[|\Z)", text)
    if not features:
        return text

    root_lines: list[str] = []
    feature_lines: list[str] = []
    for line in features.group("body").splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+)\s*=", line)
        if match and match.group(1) in ROOT_CONFIG_KEYS:
            root_lines.append(line)
        else:
            feature_lines.append(line)
    if not root_lines:
        return text

    feature_body = "\n".join(feature_lines).strip()
    rebuilt = "[features]\n" + (feature_body + "\n" if feature_body else "")
    without_misplaced = text[: features.start()] + rebuilt + text[features.end() :]
    return "\n".join(root_lines) + "\n\n" + without_misplaced.lstrip()


def _ensure_features_hooks(text: str) -> str:
    features = re.search(r"(?ms)^\[features\]\s*\n(?P<body>.*?)(?=^\[|\Z)", text)
    if not features:
        first_table = re.search(r"(?m)^\[", text)
        insertion = first_table.start() if first_table else len(text)
        before = text[:insertion].rstrip()
        after = text[insertion:].lstrip()
        parts = [part for part in (before, "[features]\nhooks = true", after) if part]
        return "\n\n".join(parts) + "\n"

    body = features.group("body")
    if re.search(r"(?m)^\s*hooks\s*=", body):
        body = re.sub(r"(?m)^\s*hooks\s*=.*$", "hooks = true", body)
    else:
        body = "hooks = true\n" + body
    return text[: features.start("body")] + body + text[features.end("body") :]


def _managed_config_block() -> str:
    return f"""
{MANAGED_BEGIN}
[[hooks.SessionStart]]
matcher = "startup|resume|clear|compact"

[[hooks.SessionStart.hooks]]
type = "command"
command = {q(HOOK_PATH)}
timeout = 12

[[hooks.SubagentStart]]

[[hooks.SubagentStart.hooks]]
type = "command"
command = {q(HOOK_PATH)}
timeout = 12

[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = {q(HOOK_PATH)}
timeout = 35

[[hooks.PostToolUse]]
matcher = ".*"

[[hooks.PostToolUse.hooks]]
type = "command"
command = {q(HOOK_PATH)}
timeout = 10

[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = {q(HOOK_PATH)}
timeout = 10

[[hooks.SubagentStop]]

[[hooks.SubagentStop.hooks]]
type = "command"
command = {q(HOOK_PATH)}
timeout = 10

[mcp_servers.jane-memory]
command = {q(VENV_PYTHON)}
args = [{q(VESSENCE_HOME / "startup_code" / "codex_memory_mcp.py")}]

[mcp_servers.jane-memory.env]
VAULT_HOME = {q(VAULT_HOME)}
VESSENCE_DATA_HOME = {q(VESSENCE_DATA_HOME)}
VESSENCE_HOME = {q(VESSENCE_HOME)}

[mcp_servers.jane-coordination]
command = {q(VENV_PYTHON)}
args = [{q(VESSENCE_HOME / "startup_code" / "codex_coordination_mcp.py")}]

[mcp_servers.jane-coordination.env]
VESSENCE_DATA_HOME = {q(VESSENCE_DATA_HOME)}
VESSENCE_HOME = {q(VESSENCE_HOME)}
{MANAGED_END}
"""


def patch_config(text: str) -> str:
    text = _remove_existing_jane_stanzas(text)
    text = _repair_misplaced_root_keys(text)
    text = _ensure_features_hooks(text)
    has_instructions = re.search(r"(?m)^model_instructions_file\s*=", text)
    top = "" if has_instructions else f"model_instructions_file = {q(INSTRUCTIONS_PATH)}\n\n"
    out = top + text.strip() + "\n\n" + _managed_config_block().strip() + "\n"
    return re.sub(r"\n{3,}", "\n\n", out)


def validate_runtime() -> None:
    result = subprocess.run(
        [str(VENV_PYTHON), "-c", "import mcp; import sqlite3"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "required imports failed"
        raise RuntimeError(f"Codex Jane runtime interpreter is invalid: {detail}")


def install(dry_run: bool = False) -> list[Path]:
    changed: list[Path] = []

    if not dry_run:
        validate_runtime()

    files = {
        HOOK_PATH: hook_script(),
        INSTRUCTIONS_PATH: instructions_text(),
    }
    current_config = CONFIG_PATH.read_text() if CONFIG_PATH.exists() else ""
    files[CONFIG_PATH] = patch_config(current_config)

    for path, content in files.items():
        old = path.read_text() if path.exists() else None
        if old == content:
            continue
        changed.append(path)
        if dry_run:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    if not dry_run:
        HOOK_PATH.chmod(HOOK_PATH.stat().st_mode | stat.S_IXUSR)

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show files that would change")
    args = parser.parse_args()

    changed = install(dry_run=args.dry_run)
    action = "Would update" if args.dry_run else "Updated"
    if changed:
        print(f"{action} Codex Jane runtime integration:")
        for path in changed:
            print(f"  - {path}")
    else:
        print("Codex Jane runtime integration already up to date.")

    print("First interactive Codex boot may ask you to trust the hook via /hooks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
