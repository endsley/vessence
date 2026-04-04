#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

_REQUIRED_PYTHON = os.environ.get("ADK_VENV_PYTHON", "")
if _REQUIRED_PYTHON and os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)


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


os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
with _silence():
    import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import CHROMA_COLLECTION_FILE_INDEX, VAULT_DIR, VECTOR_DB_FILE_INDEX
from agent_skills.index_vault import (
    READABLE_EXTENSIONS,
    describe_readable_file,
    extract_readable_text,
)


def _resolve_path(meta: dict | None) -> Path | None:
    meta = meta or {}
    path = str(meta.get("path", "")).strip()
    if not path:
        return None
    p = Path(path)
    if p.is_absolute():
        return p
    vault_root = Path(VAULT_DIR)
    if path.startswith("vault/"):
        return vault_root.parent / path
    return vault_root / path.lstrip("/")


def _extract_path_from_doc(doc: str) -> Path | None:
    text = str(doc or "")
    match = re.search(r"at path (.+?)\.\s", text)
    if not match:
        return None
    return Path(match.group(1).strip())


def _mime_for_path(path: Path) -> str:
    import mimetypes
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def _build_memory_text(path: Path, description: str, mime_type: str) -> str:
    return f"Vault file: '{path.name}' at path {path}. {description} File type: {mime_type}."


def backfill(limit: int | None = None) -> dict:
    with _silence():
        client = chromadb.PersistentClient(path=VECTOR_DB_FILE_INDEX)
        coll = client.get_or_create_collection(CHROMA_COLLECTION_FILE_INDEX, metadata={"hnsw:space": "cosine"})

    rows = coll.get(include=["documents", "metadatas"])
    ids = rows.get("ids", []) or []
    docs = rows.get("documents", []) or []
    metas = rows.get("metadatas", []) or []

    updated = 0
    skipped = 0
    missing = 0
    examples = []

    for idx, (mem_id, doc, meta) in enumerate(zip(ids, docs, metas), start=1):
        if limit is not None and updated >= limit:
            break
        meta = meta or {}
        path = _resolve_path(meta) or _extract_path_from_doc(doc)
        if not path or not path.exists() or not path.is_file():
            missing += 1
            continue
        if path.suffix.lower() not in READABLE_EXTENSIONS:
            skipped += 1
            continue

        mime_type = _mime_for_path(path)
        extracted = extract_readable_text(path)
        description = describe_readable_file(path, mime_type, extracted)
        new_doc = _build_memory_text(path, description, mime_type)

        if new_doc == (doc or ""):
            skipped += 1
            continue

        new_meta = dict(meta)
        new_meta["path"] = str(path)
        new_meta["filename"] = path.name
        new_meta["description_source"] = "content_derived_backfill_v1"
        coll.update(ids=[mem_id], documents=[new_doc], metadatas=[new_meta])
        updated += 1

        if len(examples) < 5:
            examples.append({
                "id": mem_id,
                "path": str(path),
                "before": str(doc or "")[:220],
                "after": new_doc[:220],
            })

    return {
        "updated": updated,
        "skipped": skipped,
        "missing": missing,
        "examples": examples,
    }


if __name__ == "__main__":
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except Exception:
            limit = None
    print(json.dumps(backfill(limit=limit), indent=2, ensure_ascii=True))
