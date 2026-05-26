#!/usr/bin/env python3
"""Install Jane's Chroma-backed memory bridge for standalone Codex CLI.

This configures Codex so new sessions can retrieve Vessence/Jane memories:
  - a UserPromptSubmit hook that injects the nearest relevant Chroma memories
  - persistent model instructions that fall back to the jane-memory MCP server
  - the jane-memory stdio MCP server registration

The installer is idempotent and only manages the Jane memory stanzas it owns.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
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
VENV_PYTHON = Path(os.environ.get("VESSENCE_PYTHON", AMBIENT_HOME / "venv" / "bin" / "python"))

CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
HOOK_PATH = CODEX_HOME / "hooks" / "jane_memory_hook.py"
INSTRUCTIONS_PATH = CODEX_HOME / "jane-memory-instructions.md"
CONFIG_PATH = CODEX_HOME / "config.toml"

MANAGED_BEGIN = "# >>> Vessence Codex memory integration"
MANAGED_END = "# <<< Vessence Codex memory integration"


def q(value: str | Path) -> str:
    """Quote a TOML string path."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def hook_script() -> str:
    return f"""#!/usr/bin/env python3
\"\"\"Codex UserPromptSubmit hook for Jane Chroma memory.\"\"\"

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
    if os.environ.get("JANE_CODEX_MEMORY_HOOK_LOG") != "1":
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as fh:
            fh.write(message + "\\n")
    except Exception:
        pass


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{{}}")
    except json.JSONDecodeError:
        payload = {{}}

    prompt = _prompt_from_payload(payload)
    if not prompt:
        return 0

    env = os.environ.copy()
    env.update({{
        "VESSENCE_HOME": str(VESSENCE_HOME),
        "VESSENCE_DATA_HOME": str(VESSENCE_DATA_HOME),
        "VAULT_HOME": str(VAULT_HOME),
        "PYTHONPATH": str(VESSENCE_HOME),
    }})

    cmd = [
        str(PYTHON),
        str(AUTO_MEMORY),
        "--limit",
        "2",
        "--max-distance",
        "0.50",
        prompt,
    ]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            env=env,
        )
    except Exception as exc:
        _log(f"memory hook failed: {{type(exc).__name__}}: {{exc}}")
        return 0

    memory = result.stdout.strip()
    if not memory:
        _log("memory hook returned no memory")
        return 0

    print(json.dumps({{
        "hookSpecificOutput": {{
            "hookEventName": "UserPromptSubmit",
            "additionalContext": memory,
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
    text = re.sub(r'(?m)^model_instructions_file\s*=.*\n?', "", text)
    text = _remove_table(text, "mcp_servers.jane-memory")
    text = _remove_table(text, "mcp_servers.jane-memory.env")
    jane_hook = re.compile(
        r"(?ms)^\[\[hooks\.UserPromptSubmit\]\]\s*\n\s*"
        r"\[\[hooks\.UserPromptSubmit\.hooks\]\]\s*\n"
        r"(?:(?!^\[).)*jane_memory_hook\.py(?:(?!^\[).)*"
        r"(?=^\[|\Z)"
    )
    text = jane_hook.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n" if text.strip() else ""


def _ensure_features_hooks(text: str) -> str:
    features = re.search(r"(?ms)^\[features\]\s*\n(?P<body>.*?)(?=^\[|\Z)", text)
    if not features:
        prefix = "[features]\nhooks = true\n\n"
        return prefix + text

    body = features.group("body")
    if re.search(r"(?m)^\s*hooks\s*=", body):
        body = re.sub(r"(?m)^\s*hooks\s*=.*$", "hooks = true", body)
    else:
        body = "hooks = true\n" + body
    return text[: features.start("body")] + body + text[features.end("body") :]


def _managed_config_block() -> str:
    return f"""
{MANAGED_BEGIN}
[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = {q(HOOK_PATH)}
timeout = 25

[mcp_servers.jane-memory]
command = {q(VENV_PYTHON)}
args = [{q(VESSENCE_HOME / "startup_code" / "codex_memory_mcp.py")}]

[mcp_servers.jane-memory.env]
VAULT_HOME = {q(VAULT_HOME)}
VESSENCE_DATA_HOME = {q(VESSENCE_DATA_HOME)}
VESSENCE_HOME = {q(VESSENCE_HOME)}
{MANAGED_END}
"""


def patch_config(text: str) -> str:
    text = _remove_existing_jane_stanzas(text)
    text = _ensure_features_hooks(text)
    top = f"model_instructions_file = {q(INSTRUCTIONS_PATH)}\n\n"
    out = top + text.strip() + "\n\n" + _managed_config_block().strip() + "\n"
    return re.sub(r"\n{3,}", "\n\n", out)


def install(dry_run: bool = False) -> list[Path]:
    changed: list[Path] = []

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
        print(f"{action} Codex Jane memory integration:")
        for path in changed:
            print(f"  - {path}")
    else:
        print("Codex Jane memory integration already up to date.")

    print("First interactive Codex boot may ask you to trust the hook via /hooks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
