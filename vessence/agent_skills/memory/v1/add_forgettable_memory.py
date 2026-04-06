#!/usr/bin/env python3
"""
Utility to add a time-limited "forgettable" memory to ChromaDB.

These memories expire after --days (default 14) and are auto-purged by the
nightly Memory Janitor. Use them for:
  - Recent changes / things just implemented
  - Progress made on a project
  - Problems recently solved and the solutions found
  - Temporary decisions or workarounds

Usage:
  add_forgettable_memory.py "Fixed the ChromaDB expiry bug in janitor_memory.py."
  add_forgettable_memory.py "Discovered cosine similarity works better than L2 for short facts." --days 30
  add_forgettable_memory.py "..." --topic "architecture" --subtopic "memory system" --days 7
"""

import os
import sys
import uuid
import argparse
import datetime
from pathlib import Path

_REQUIRED_PYTHON = os.environ.get('ADK_VENV_PYTHON', 'python3')
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)


class silence_stderr_fd:
    def __enter__(self):
        self.stdout_fd = os.dup(1)
        self.stderr_fd = os.dup(2)
        self.null_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.null_fd, 1)
        os.dup2(self.null_fd, 2)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self.stdout_fd, 1)
        os.dup2(self.stderr_fd, 2)
        os.close(self.null_fd)
        os.close(self.stdout_fd)
        os.close(self.stderr_fd)


os.environ["ORT_LOGGING_LEVEL"] = "3"
with silence_stderr_fd():
    import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from jane.config import get_chroma_client, SHORT_TERM_TTL_DAYS as DEFAULT_TTL_DAYS, VECTOR_DB_SHORT_TERM as SHORT_TERM_DB_PATH, CHROMA_COLLECTION_SHORT_TERM


def add_forgettable_memory(
    fact: str,
    days: int = DEFAULT_TTL_DAYS,
    topic: str = "General",
    subtopic: str = "",
    author: str = "jane",
) -> str:
    """
    Adds a short-term memory entry (formerly 'forgettable') to the shared
    short_term_memory DB. Expires after `days` days; purged by nightly janitor.
    """
    now = datetime.datetime.utcnow()
    created_at = now.isoformat()
    expires_at = (now + datetime.timedelta(days=days)).isoformat()
    memory_id = str(uuid.uuid4())

    with silence_stderr_fd():
        client = get_chroma_client(path=SHORT_TERM_DB_PATH)
        collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION_SHORT_TERM,
            metadata={"hnsw:space": "cosine"},
        )

    collection.add(
        documents=[fact],
        ids=[memory_id],
        metadatas=[{
            "memory_type": "short_term",
            "author": author,
            "topic": topic,
            "subtopic": subtopic,
            "timestamp": created_at,
            "expires_at": expires_at,
            "ttl_days": days,
        }],
    )
    print(
        f"[short-term] Added (expires {expires_at[:10]}): "
        f"{fact[:80]}{'...' if len(fact) > 80 else ''}"
    )
    return memory_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add a forgettable (time-limited) memory to ChromaDB."
    )
    parser.add_argument("fact", help="The memory text to store.")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_TTL_DAYS,
        help=f"TTL in days before this memory expires (default: {DEFAULT_TTL_DAYS})",
    )
    parser.add_argument("--topic", default="General", help="Topic tag")
    parser.add_argument("--subtopic", default="", help="Subtopic tag")
    parser.add_argument(
        "--author",
        default="jane",
        help="Who is adding this memory (jane, amber, system, …)",
    )
    args = parser.parse_args()
    add_forgettable_memory(args.fact, args.days, args.topic, args.subtopic, args.author)
