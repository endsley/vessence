#!/usr/bin/env python3
"""permission_gate.py — PreToolUse hook that gates sensitive tools through the Jane web UI.

Runs inside the Claude CLI subprocess. For tools requiring approval, sends an HTTP
request to the Jane web server and blocks until the user approves or denies.

Hook protocol (stdin → JSON, stdout → JSON):
  Input:  {"tool_name": "Bash", "tool_input": {"command": "rm -rf ..."}}
  Output: {"decision": "approve"} or {"decision": "block", "reason": "Denied by user"}
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

# ── Policy ────────────────────────────────────────────────────────────────────

# Tools that always need user approval
APPROVAL_REQUIRED = {"Bash", "Write", "Edit", "NotebookEdit"}

# Read-only bash commands that are auto-approved
READONLY_PREFIXES = (
    "git status", "git log", "git diff", "git branch", "git show",
    "ls ", "cat ", "head ", "tail ", "wc ", "file ", "which ", "echo ",
    "pwd", "whoami", "date", "uptime", "df ", "du ", "free ",
    "python3 -c \"import", "python -c \"import",
)

# Patterns that are always dangerous — never auto-approve
DANGEROUS_PATTERNS = (
    "rm -rf", "rm -r /", "mkfs", "dd if=", "> /dev/",
    "git push --force", "git reset --hard",
    "DROP TABLE", "DROP DATABASE", "DELETE FROM",
    "chmod 777", ":(){ :|:",
)

# Jane web server endpoint
JANE_WEB_PORT = int(os.environ.get("JANE_WEB_PORT", "8081"))
PERMISSION_URL = f"http://127.0.0.1:{JANE_WEB_PORT}/api/jane/permission/request"
TIMEOUT_SECONDS = 300  # 5 minutes


def _is_readonly_bash(command: str) -> bool:
    """Check if a bash command is read-only and safe to auto-approve."""
    cmd = command.strip().lstrip("cd /tmp && ").lstrip("cd ")
    for prefix in READONLY_PREFIXES:
        if cmd.startswith(prefix):
            return True
    # Pipeline ending in a readonly command
    if "|" in cmd:
        last = cmd.rsplit("|", 1)[-1].strip()
        for prefix in READONLY_PREFIXES:
            if last.startswith(prefix):
                return True
    return False


def _is_dangerous(command: str) -> bool:
    """Check if a command contains dangerous patterns."""
    lower = command.lower()
    return any(p.lower() in lower for p in DANGEROUS_PATTERNS)


def _request_permission(tool_name: str, tool_input: dict) -> bool:
    """Send permission request to Jane web and block until user responds."""
    request_id = f"perm_{os.getpid()}_{int(time.time() * 1000)}"

    payload = json.dumps({
        "request_id": request_id,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "session_id": os.environ.get("SESSION_ID", "standing_brain"),
    }).encode("utf-8")

    req = urllib.request.Request(
        PERMISSION_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        response = urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS)
        result = json.loads(response.read())
        return result.get("approved", False)
    except urllib.error.URLError as e:
        # Can't reach web server — fail open (approve) to avoid blocking the brain
        print(json.dumps({
            "decision": "approve",
            "reason": f"Permission server unreachable ({e}); auto-approving",
        }), file=sys.stderr)
        return True
    except Exception as e:
        print(json.dumps({
            "decision": "approve",
            "reason": f"Permission check error ({e}); auto-approving",
        }), file=sys.stderr)
        return True


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        print(json.dumps({"decision": "approve"}))
        return

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Auto-approve tools that don't need permission
    if tool_name not in APPROVAL_REQUIRED:
        print(json.dumps({"decision": "approve"}))
        return

    # Bash: auto-approve readonly commands
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if _is_readonly_bash(command) and not _is_dangerous(command):
            print(json.dumps({"decision": "approve"}))
            return

    # Request permission from user via web UI
    approved = _request_permission(tool_name, tool_input)

    if approved:
        print(json.dumps({"decision": "approve"}))
    else:
        print(json.dumps({
            "decision": "block",
            "reason": "Denied by user via web UI",
        }))


if __name__ == "__main__":
    main()
