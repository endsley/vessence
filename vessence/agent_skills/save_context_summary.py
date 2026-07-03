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

from agent_skills.context_summary_helpers import (
    clean_qwen_summary as _clean_qwen_summary,
    context_snapshot_fact as _context_snapshot_fact,
    last_summary_record as _last_summary_record,
    parse_hook_payload as _parse_hook_payload,
    response_text_from_payload as _response_text_from_payload,
    should_summarize_response as _should_summarize_response,
)
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
        return _clean_qwen_summary(result.stdout)
    except Exception as e:
        return f"[summary unavailable: {e}]"


def main():
    raw = sys.stdin.read().strip()
    data = _parse_hook_payload(raw)

    # Extract response text — Stop hook provides it in "message" field
    response_text = _response_text_from_payload(data)

    if not _should_summarize_response(response_text):
        # Nothing meaningful to summarize
        sys.exit(0)

    summary = ask_qwen_summarize(response_text)
    if not summary or "[summary unavailable" in summary:
        sys.exit(0)

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    fact = _context_snapshot_fact(now, summary)

    try:
        subprocess.run(
            [ADD_MEMORY, fact, "--topic", "context_snapshot", "--days", "14", "--author", "jane"],
            capture_output=True, timeout=30
        )
        # Save last summary for debugging
        os.makedirs(os.path.dirname(CONTEXT_LOG), exist_ok=True)
        with open(CONTEXT_LOG, "w") as f:
            json.dump(_last_summary_record(now, summary), f, indent=2)
    except Exception as e:
        sys.stderr.write(f"save_context_summary error: {e}\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
