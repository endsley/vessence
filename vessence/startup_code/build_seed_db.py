#!/usr/bin/env python3
"""
build_seed_db.py — Builds a clean ChromaDB seed database for distribution.

This creates a git-tracked seed database at vessence/seed_db/ that new users
get when they clone the repo. It contains:
  - long_term_knowledge: populated with system facts from jane_seed_memories.json
  - short_term_memory: empty collection (ephemeral, always starts fresh)
  - user_memories: empty collection (personal, filled during onboarding)
  - file_index_memories: empty collection (built when user adds files to vault)

Usage:
    python build_seed_db.py [--force]   # --force rebuilds even if seed_db/ exists
"""

import argparse
import datetime
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Re-exec under ADK venv if available
# ---------------------------------------------------------------------------
_REQUIRED_PYTHON = os.environ.get("ADK_VENV_PYTHON", "")
if _REQUIRED_PYTHON and os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')

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


def main():
    parser = argparse.ArgumentParser(description="Build seed ChromaDB for distribution.")
    parser.add_argument("--force", action="store_true", help="Delete and rebuild seed_db/ if it exists.")
    args = parser.parse_args()

    vessence_home = os.environ.get(
        "VESSENCE_HOME",
        os.path.join(str(Path.home()), "ambient", "vessence"),
    )

    seed_db_dir = os.path.join(vessence_home, "seed_db")
    seed_file = os.path.join(vessence_home, "configs", "jane_seed_memories.json")

    # ── Guard against accidental overwrites ──────────────────────────────
    if os.path.exists(seed_db_dir):
        if not args.force:
            print(f"seed_db/ already exists at {seed_db_dir}")
            print("Use --force to rebuild from scratch.")
            return
        print(f"Removing existing seed_db/ ...")
        shutil.rmtree(seed_db_dir)

    # ── Load seed memories ───────────────────────────────────────────────
    if not os.path.exists(seed_file):
        print(f"ERROR: Seed file not found: {seed_file}")
        sys.exit(1)

    with open(seed_file) as f:
        seeds = json.load(f)
    print(f"Loaded {len(seeds)} seed entries from {seed_file}")

    now = datetime.datetime.utcnow().isoformat()

    # ── Build the directory structure matching runtime layout ─────────────
    # Runtime layout:
    #   vector_db/                   ← user_memories collection
    #   vector_db/long_term_memory/  ← long_term_knowledge collection
    #   vector_db/short_term_memory/ ← short_term_memory collection
    #   vector_db/file_index_memory/ ← file_index_memories collection

    long_term_path = os.path.join(seed_db_dir, "long_term_memory")
    short_term_path = os.path.join(seed_db_dir, "short_term_memory")
    file_index_path = os.path.join(seed_db_dir, "file_index_memory")

    # 1. long_term_knowledge — seeded with system knowledge
    os.makedirs(long_term_path, exist_ok=True)
    lt_client = chromadb.PersistentClient(path=long_term_path)
    lt_collection = lt_client.get_or_create_collection(
        name="long_term_knowledge",
        metadata={"hnsw:space": "cosine"},
    )

    ids = []
    documents = []
    metadatas = []
    for entry in seeds:
        ids.append(str(uuid.uuid4()))
        documents.append(entry["text"])
        meta = {
            "author": "jane_seed",
            "memory_type": entry.get("type", "permanent"),
            "topic": entry.get("topic", "General"),
            "timestamp": now,
            "source": "jane_seed_memories.json",
        }
        if entry.get("subtopic"):
            meta["subtopic"] = entry["subtopic"]
        metadatas.append(meta)

    lt_collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"  long_term_knowledge: {lt_collection.count()} entries seeded")

    # 2. short_term_memory — empty collection
    os.makedirs(short_term_path, exist_ok=True)
    st_client = chromadb.PersistentClient(path=short_term_path)
    st_client.get_or_create_collection(
        name="short_term_memory",
        metadata={"hnsw:space": "cosine"},
    )
    print("  short_term_memory: empty (ready)")

    # 3. user_memories — empty collection (at seed_db root, matching runtime layout)
    um_client = chromadb.PersistentClient(path=seed_db_dir)
    um_client.get_or_create_collection(
        name="user_memories",
        metadata={"hnsw:space": "cosine"},
    )
    print("  user_memories: empty (ready)")

    # 4. file_index_memories — empty collection
    os.makedirs(file_index_path, exist_ok=True)
    fi_client = chromadb.PersistentClient(path=file_index_path)
    fi_client.get_or_create_collection(
        name="file_index_memories",
        metadata={"hnsw:space": "cosine"},
    )
    print("  file_index_memories: empty (ready)")

    # ── Write manifest ───────────────────────────────────────────────────
    manifest = {
        "built_at": now,
        "seed_file": "configs/jane_seed_memories.json",
        "seed_count": len(seeds),
        "collections": {
            "long_term_knowledge": {"path": "long_term_memory/", "count": len(seeds)},
            "short_term_memory": {"path": "short_term_memory/", "count": 0},
            "user_memories": {"path": "./", "count": 0},
            "file_index_memories": {"path": "file_index_memory/", "count": 0},
        },
    }
    manifest_path = os.path.join(seed_db_dir, "SEED_MANIFEST.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nSeed DB built at: {seed_db_dir}")
    print(f"Manifest written to: {manifest_path}")
    print("\nThis directory is checked into git. New users get it on clone.")
    print("The bootstrap copies it to vessence-data/memory/v1/vector_db/ on first setup.")


if __name__ == "__main__":
    main()
