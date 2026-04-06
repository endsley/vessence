#!/usr/bin/env python3
"""
seed_chromadb.py — Loads Jane default seed memories into a fresh ChromaDB on first boot.

This script is idempotent: it checks for a sentinel flag file and skips if
seeding has already been done. It also checks whether the user_memories
collection is empty before seeding, so it will not overwrite existing data.

Usage:
    python seed_chromadb.py [--force]  # --force re-seeds even if flag exists

Environment:
    VESSENCE_HOME     — code root (defaults to ~/ambient/vessence)
    VESSENCE_DATA_HOME — data root (defaults to ~/ambient/vessence-data)
"""

import argparse
import json
import os
import sys
import uuid
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Re-exec under ADK venv if available (ensures chromadb/onnx imports work)
# ---------------------------------------------------------------------------
_REQUIRED_PYTHON = os.environ.get("ADK_VENV_PYTHON", "")
if _REQUIRED_PYTHON and os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

# Silence onnxruntime noise
os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')

# Redirect stdout/stderr during chromadb import to suppress init noise
_stdout_fd = os.dup(1)
_stderr_fd = os.dup(2)
_null_fd = os.open(os.devnull, os.O_WRONLY)
os.dup2(_null_fd, 1)
os.dup2(_null_fd, 2)
try:
    import chromadb
finally:
    os.dup2(_stdout_fd, 1)
    os.dup2(_stderr_fd, 2)
    os.close(_null_fd)
    os.close(_stdout_fd)
    os.close(_stderr_fd)


def _resolve_paths():
    """Resolve VESSENCE_HOME, VESSENCE_DATA_HOME, and derived paths."""
    home = str(Path.home())
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.join(home, "ambient"))

    vessence_home = os.environ.get("VESSENCE_HOME", os.path.join(ambient_base, "vessence"))
    vessence_data_home = os.environ.get("VESSENCE_DATA_HOME", os.path.join(ambient_base, "vessence-data"))

    seed_file = os.path.join(vessence_home, "configs", "jane_seed_memories.json")
    vector_db_dir = os.path.join(vessence_data_home, "memory/v1/vector_db")
    flag_file = os.path.join(vessence_data_home, "memory/v1/vector_db", ".seeded")

    return seed_file, vector_db_dir, flag_file


def load_seeds(seed_file: str) -> list[dict]:
    """Load and validate seed memories from JSON."""
    with open(seed_file, "r") as f:
        seeds = json.load(f)

    if not isinstance(seeds, list):
        raise ValueError(f"Seed file must contain a JSON array, got {type(seeds).__name__}")

    required_keys = {"text", "topic", "type"}
    for i, entry in enumerate(seeds):
        missing = required_keys - set(entry.keys())
        if missing:
            raise ValueError(f"Seed entry {i} missing required keys: {missing}")

    return seeds


def seed_collection(vector_db_dir: str, seeds: list[dict]) -> int:
    """Insert seed memories into the user_memories ChromaDB collection.

    Returns the number of entries inserted.
    """
    os.makedirs(vector_db_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=vector_db_dir)
    collection = client.get_or_create_collection(
        name="user_memories",
        metadata={"hnsw:space": "cosine"},
    )

    # Only seed into an empty collection
    if collection.count() > 0:
        print(f"Collection already has {collection.count()} entries — skipping seed.")
        return 0

    now = datetime.datetime.utcnow().isoformat()
    ids = []
    documents = []
    metadatas = []

    for entry in seeds:
        ids.append(str(uuid.uuid4()))
        documents.append(entry["text"])
        metadata = {
            "author": "jane_seed",
            "memory_type": entry.get("type", "permanent"),
            "topic": entry.get("topic", "General"),
            "timestamp": now,
            "source": "jane_seed_memories.json",
        }
        if entry.get("subtopic"):
            metadata["subtopic"] = entry["subtopic"]
        metadatas.append(metadata)

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def write_flag(flag_file: str, count: int):
    """Write a sentinel file marking seeding as complete."""
    os.makedirs(os.path.dirname(flag_file), exist_ok=True)
    with open(flag_file, "w") as f:
        f.write(json.dumps({
            "seeded_at": datetime.datetime.utcnow().isoformat(),
            "entries": count,
            "version": "1.0",
        }, indent=2))
    print(f"Flag written to {flag_file}")


def main():
    parser = argparse.ArgumentParser(description="Seed ChromaDB with Jane default memories.")
    parser.add_argument("--force", action="store_true", help="Re-seed even if flag file exists.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing.")
    args = parser.parse_args()

    seed_file, vector_db_dir, flag_file = _resolve_paths()

    # Check flag
    if os.path.exists(flag_file) and not args.force:
        print(f"Already seeded (flag: {flag_file}). Use --force to re-seed.")
        return

    # Load seeds
    if not os.path.exists(seed_file):
        print(f"ERROR: Seed file not found: {seed_file}")
        sys.exit(1)

    seeds = load_seeds(seed_file)
    print(f"Loaded {len(seeds)} seed memories from {seed_file}")

    if args.dry_run:
        print("Dry run — would insert these entries:")
        for i, s in enumerate(seeds):
            print(f"  [{i+1}] ({s['topic']}/{s.get('subtopic', '-')}): {s['text'][:80]}...")
        return

    # Seed
    count = seed_collection(vector_db_dir, seeds)
    if count > 0:
        write_flag(flag_file, count)
        print(f"Successfully seeded {count} memories into ChromaDB at {vector_db_dir}")
    else:
        print("No entries inserted (collection not empty or no seeds).")


if __name__ == "__main__":
    main()
