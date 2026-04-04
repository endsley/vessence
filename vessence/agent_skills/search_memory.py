#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Environment guard: if we're not running inside the ADK venv, re-exec with the correct Python.
# This makes the script safe to call with any Python (e.g. `python3 search_memory.py`).
_REQUIRED_PYTHON = os.environ.get('ADK_VENV_PYTHON', 'python3')
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skills.memory_retrieval import get_memory_summary as shared_get_memory_summary


def get_memory_summary(query: str, conversation_summary: str = "", session_id: str = "", essence_chromadb_path: str | None = None) -> str:
    return shared_get_memory_summary(
        query,
        conversation_summary=conversation_summary,
        assistant_name="Jane",
        session_id=session_id,
        essence_chromadb_path=essence_chromadb_path,
    )


def search_memory(query):
    print(get_memory_summary(query))

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "recent updates and current status"
    search_memory(query)
