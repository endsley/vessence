#!/usr/bin/env python3
"""
add_fact.py — Write a fact to the shared ChromaDB (user_memories collection).

Both Jane and Amber read from this collection. Use this whenever Jane learns
something from the user that Amber should also know.

Usage:
    add_fact.py "User's favorite restaurant is X." [--topic preferences] [--subtopic food]

Options:
    --topic     Short label (e.g. preferences, family, work, health). Default: General
    --subtopic  Optional finer label.
    --author    Who is recording this fact. Default: jane
"""
import argparse
import sys
import uuid
import os
from pathlib import Path

# Re-exec with the ADK venv python so chromadb/onnx imports work cleanly.
_REQUIRED_PYTHON = os.environ.get('ADK_VENV_PYTHON', 'python3')
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

class _silence:
    def __enter__(self):
        import os as _os
        self._fds = ((_os.dup(1), _os.dup(2)))
        self._null = _os.open(_os.devnull, _os.O_WRONLY)
        _os.dup2(self._null, 1); _os.dup2(self._null, 2)
    def __exit__(self, *_):
        import os as _os
        _os.dup2(self._fds[0], 1); _os.dup2(self._fds[1], 2)
        _os.close(self._null); _os.close(self._fds[0]); _os.close(self._fds[1])

os.environ["ORT_LOGGING_LEVEL"] = "3"
with _silence():
    import chromadb
import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import get_chroma_client, VECTOR_DB_USER_MEMORIES, CHROMA_COLLECTION_USER_MEMORIES


def add_fact(fact: str, topic: str = "General", subtopic: str = "", author: str = "jane", user_id: str = None) -> str:
    if user_id is None:
        user_id = os.environ.get("USER_NAME", "user")
    with _silence():
        client = get_chroma_client(path=VECTOR_DB_USER_MEMORIES)
        collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION_USER_MEMORIES,
            metadata={"hnsw:space": "cosine"}
        )
    metadata = {
        "user_id": user_id,
        "author": author,
        "topic": topic,
        "memory_type": "long_term",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    if subtopic:
        metadata["subtopic"] = subtopic

    collection.add(
        documents=[fact],
        ids=[str(uuid.uuid4())],
        metadatas=[metadata],
    )
    return f"Saved to shared memory (topic={topic}): {fact}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a fact to the shared ChromaDB.")
    parser.add_argument("fact", help="The fact to store, as a complete sentence.")
    parser.add_argument("--topic", default="General", help="Short topic label.")
    parser.add_argument("--subtopic", default="", help="Optional subtopic label.")
    parser.add_argument("--author", default="jane", help="Author tag (default: jane).")
    parser.add_argument("--user-id", default=os.environ.get("USER_NAME", "user"), help="User ID tag.")
    args = parser.parse_args()

    result = add_fact(args.fact, topic=args.topic, subtopic=args.subtopic, author=args.author, user_id=args.user_id)
    print(result)
