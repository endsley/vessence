#!/usr/bin/env python3
"""
migrate_file_index_memories.py — Move vault/file indexing records out of user_memories
and into the dedicated file_index_memories collection.
"""

import os
import sys
import uuid
from pathlib import Path

_REQUIRED_PYTHON = os.environ.get("ADK_VENV_PYTHON", "python3")
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

os.environ["ORT_LOGGING_LEVEL"] = "3"


class _silence:
    def __enter__(self):
        self._fds = (os.dup(1), os.dup(2))
        self._null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self._null, 1)
        os.dup2(self._null, 2)

    def __exit__(self, *_):
        os.dup2(self._fds[0], 1)
        os.dup2(self._fds[1], 2)
        os.close(self._null)
        os.close(self._fds[0])
        os.close(self._fds[1])


with _silence():
    import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import (  # noqa: E402
    CHROMA_COLLECTION_FILE_INDEX,
    CHROMA_COLLECTION_USER_MEMORIES,
    VECTOR_DB_FILE_INDEX,
    VECTOR_DB_USER_MEMORIES,
)


def _is_file_index_record(doc: str, meta: dict | None) -> bool:
    meta = meta or {}
    topic = str(meta.get("topic", "")).lower()
    subtopic = str(meta.get("subtopic", "")).lower()
    memory_type = str(meta.get("memory_type", "")).lower()
    source = str(meta.get("source", "")).lower()
    text = str(doc or "").lower()
    return (
        topic in {"vault_file", "file_index"}
        or subtopic == "vault_file"
        or memory_type == "file_index"
        or source == "vault"
        or text.startswith("vault file:")
        or text.startswith("saved file '")
        or text.startswith("a file named '")
        or text.startswith("the user has a file named '")
        or text.startswith("the user has and stores ")
        or " stored at /home/chieh/ambient/vault/" in text
        or " saved in the '" in text
        or " location: documents/" in text
    )


def migrate() -> dict:
    with _silence():
        src_client = chromadb.PersistentClient(path=VECTOR_DB_USER_MEMORIES)
        dst_client = chromadb.PersistentClient(path=VECTOR_DB_FILE_INDEX)
        src = src_client.get_or_create_collection(CHROMA_COLLECTION_USER_MEMORIES)
        dst = dst_client.get_or_create_collection(
            CHROMA_COLLECTION_FILE_INDEX,
            metadata={"hnsw:space": "cosine"},
        )

    rows = src.get(include=["documents", "metadatas"])
    ids = rows.get("ids", []) or []
    docs = rows.get("documents", []) or []
    metas = rows.get("metadatas", []) or []

    move_ids = []
    new_ids = []
    new_docs = []
    new_metas = []

    for _id, doc, meta in zip(ids, docs, metas):
        meta = meta or {}
        if not _is_file_index_record(doc, meta):
            continue
        new_meta = dict(meta)
        new_meta["topic"] = "file_index"
        new_meta["memory_type"] = "file_index"
        if "filename" not in new_meta and "path" in new_meta:
            new_meta["filename"] = os.path.basename(str(new_meta["path"]))
        new_meta["migrated_from"] = _id
        move_ids.append(_id)
        new_ids.append(str(uuid.uuid4()))
        new_docs.append(doc)
        new_metas.append(new_meta)

    if new_ids:
        dst.add(ids=new_ids, documents=new_docs, metadatas=new_metas)
        src.delete(ids=move_ids)

    return {
        "migrated": len(new_ids),
        "deleted_from_user_memories": len(move_ids),
    }


if __name__ == "__main__":
    print(migrate())
