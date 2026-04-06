#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Environment guard: if we're not running inside the ADK venv, re-exec with the correct Python.
# This makes the script safe to call with any Python (e.g. `python3 search_memory.py`).
_REQUIRED_PYTHON = os.environ.get('ADK_VENV_PYTHON', 'python3')
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agent_skills.memory.v1.memory_retrieval import build_memory_sections


def search_memory(query):
    sections = build_memory_sections(query, assistant_name="Jane")
    print("\n\n".join(sections) if sections else "No relevant context found.")

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "recent updates and current status"
    search_memory(query)
