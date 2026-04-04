#!/usr/bin/env python3
"""
save_context_summary.py — Called by the Stop hook after every Claude response.
Reads the response text from stdin (JSON), asks Qwen to summarize it,
and saves the summary to short-term memory (ChromaDB).

Hook input format: {"session_id": "...", "stop_hook_active": bool, ...}
The response content may be in "message" or we infer from recent activity.
"""

import sys
import os
import json
import subprocess
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import (
    ADK_VENV_PYTHON,
    ADD_MEMORY_SCRIPT,
    CONTEXT_SUMMARY_PATH,
    QWEN_QUERY_SCRIPT,
)

PYTHON = ADK_VENV_PYTHON
QWEN_SCRIPT = QWEN_QUERY_SCRIPT
ADD_MEMORY = ADD_MEMORY_SCRIPT
CONTEXT_LOG = CONTEXT_SUMMARY_PATH


def ask_qwen_summarize(text: str) -> str:
    """Ask Qwen to produce a 2-3 sentence summary of the given text."""
    prompt = (
        f"Summarize the following in 2-3 sentences, focusing on what was decided or accomplished. "
        f"Be concrete — mention specific files, systems, or outcomes changed.\n\n"
        f"{text[:3000]}"
    )
    try:
        result = subprocess.run(
            [PYTHON, QWEN_SCRIPT, prompt],
            capture_output=True, text=True, timeout=45
        )
        # Strip the Qwen header line
        lines = result.stdout.strip().splitlines()
        lines = [l for l in lines if not l.startswith("---")]
        return " ".join(lines).strip()
    except Exception as e:
        return f"[summary unavailable: {e}]"


def main():
    raw = sys.stdin.read().strip()
    data = {}
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        pass

    # Extract response text — Stop hook provides it in "message" field
    response_text = data.get("message", "")

    if not response_text or len(response_text.strip()) < 50:
        # Nothing meaningful to summarize
        sys.exit(0)

    summary = ask_qwen_summarize(response_text)
    if not summary or "[summary unavailable" in summary:
        sys.exit(0)

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    fact = f"[Context snapshot {now}] {summary}"

    try:
        subprocess.run(
            [ADD_MEMORY, fact, "--topic", "context_snapshot", "--days", "14", "--author", "jane"],
            capture_output=True, timeout=30
        )
        # Save last summary for debugging
        os.makedirs(os.path.dirname(CONTEXT_LOG), exist_ok=True)
        with open(CONTEXT_LOG, "w") as f:
            json.dump({"timestamp": now, "summary": summary}, f, indent=2)
    except Exception as e:
        sys.stderr.write(f"save_context_summary error: {e}\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
