#!/usr/bin/env python3
"""stop_hook_memory.py — Stop hook: extract memorable facts after each Claude Code turn.

Writes to ChromaDB automatically:
  - Long-term: explicit user facts detected via patterns (permanent)
  - Short-term: 1-sentence Ollama activity summary (expires in 14 days)

Hook input (stdin): {"session_id": "...", "stop_hook_active": bool}
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

_home = Path.home()
_ambient = Path(os.environ.get("AMBIENT_BASE", str(_home / "ambient")))
VESSENCE_HOME = os.environ.get("VESSENCE_HOME", str(_ambient / "vessence"))
VENV_PYTHON = str(_ambient / "venv" / "bin" / "python")

# ── Explicit long-term fact patterns ─────────────────────────────────────────
# Only fire on clear first-person statements the user makes about themselves.
LONG_TERM_PATTERNS = [
    (re.compile(r"\bmy name is ([^.!?\n]{2,40})", re.I),       "identity",    "name"),
    (re.compile(r"\bcall me ([^.!?\n]{2,30})", re.I),          "identity",    "name"),
    (re.compile(r"\bi(?:'m| am) a ([^.!?\n]{5,60})", re.I),    "identity",    "role"),
    (re.compile(r"\bi work (?:at|for) ([^.!?\n]{3,60})", re.I),"identity",    "work"),
    (re.compile(r"\bi(?:'m| am) based in ([^.!?\n]{3,50})", re.I), "identity","location"),
    (re.compile(r"\bi live in ([^.!?\n]{3,50})", re.I),        "identity",    "location"),
    (re.compile(r"\bi prefer ([^.!?\n]{5,80})", re.I),         "preferences", ""),
    (re.compile(r"\bi(?:'d| would) rather ([^.!?\n]{5,80})", re.I), "preferences", ""),
    (re.compile(r"\bremember that ([^.!?\n]{5,120})", re.I),   "notes",       ""),
]


def _read_stdin() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def _find_session_file(session_id: str) -> Path | None:
    projects = _home / ".claude" / "projects"
    for f in projects.rglob(f"{session_id}.jsonl"):
        return f
    return None


def _get_last_turn(session_file: Path) -> tuple[str, str]:
    """Return (user_msg, assistant_msg) for the most recent complete turn."""
    try:
        lines = session_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except Exception:
        return "", ""

    user_msg = assistant_msg = ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except Exception:
            continue
        msg = entry.get("message", {})
        role = msg.get("role", "")
        content = msg.get("content", "")

        if isinstance(content, list):
            text = " ".join(
                c.get("text", "") for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            ).strip()
        else:
            text = str(content).strip()

        if not text:
            continue

        if not assistant_msg and role == "assistant":
            assistant_msg = text[:3000]
        elif not user_msg and role == "user":
            user_msg = text[:1000]

        if user_msg and assistant_msg:
            break

    return user_msg, assistant_msg


def _write_long_term(fact: str, topic: str, subtopic: str = "") -> None:
    cmd = [VENV_PYTHON, f"{VESSENCE_HOME}/memory/v1/add_fact.py",
           fact, "--topic", topic, "--author", "stop_hook"]
    if subtopic:
        cmd += ["--subtopic", subtopic]
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
    except Exception:
        pass


def _write_short_term(fact: str, days: int = 14) -> None:
    cmd = [VENV_PYTHON, f"{VESSENCE_HOME}/memory/v1/add_forgettable_memory.py",
           fact, "--topic", "session_activity", "--days", str(days),
           "--author", "stop_hook"]
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
    except Exception:
        pass


def _extract_long_term_facts(user_msg: str) -> list[tuple[str, str, str]]:
    facts = []
    for pattern, topic, subtopic in LONG_TERM_PATTERNS:
        for m in pattern.finditer(user_msg):
            raw = m.group(0).strip().rstrip(".,;")
            if len(raw) > 6:
                facts.append((f"User stated: {raw}", topic, subtopic))
    return facts


def _ollama_summary(user_msg: str, assistant_msg: str) -> str | None:
    """Ask local Ollama Qwen for a 1-sentence activity summary. Fails silently."""
    try:
        payload = json.dumps({
            "model": "qwen2.5:latest",
            "prompt": (
                "Summarize this conversation turn in ONE short sentence (max 120 chars) "
                "describing what was accomplished or discussed. Be specific — name files, "
                "systems, or topics touched. No filler.\n\n"
                f"User: {user_msg[:500]}\n"
                f"Assistant: {assistant_msg[:800]}\n\n"
                "Summary:"
            ),
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1, "num_predict": 60},
            "keep_alive": -1,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read())
            return (result.get("response") or "").strip()[:200] or None
    except Exception:
        return None


def main() -> int:
    data = _read_stdin()

    # Prevent infinite loop — stop_hook_active is True when a hook triggered the stop
    if data.get("stop_hook_active"):
        return 0

    session_id = data.get("session_id", "")
    if not session_id:
        return 0

    session_file = _find_session_file(session_id)
    if not session_file:
        return 0

    user_msg, assistant_msg = _get_last_turn(session_file)
    if not user_msg and not assistant_msg:
        return 0

    # Long-term: pattern-match explicit user facts from what the user said
    for fact, topic, subtopic in _extract_long_term_facts(user_msg):
        _write_long_term(fact, topic, subtopic)

    # Short-term: Ollama summary of what was done this turn
    if assistant_msg:
        summary = _ollama_summary(user_msg, assistant_msg)
        if summary:
            _write_short_term(f"CLI session activity: {summary}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
