#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

_REQUIRED_PYTHON = os.environ.get("ADK_VENV_PYTHON", "/home/chieh/google-adk-env/adk-venv/bin/python")
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


os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
with silence_stderr_fd():
    import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import VECTOR_DB_SHORT_TERM, CHROMA_COLLECTION_SHORT_TERM
from memory.v1.conversation_manager import ConversationManager


def migrate_short_term_memory(limit: int | None = None) -> dict:
    with silence_stderr_fd():
        client = chromadb.PersistentClient(path=VECTOR_DB_SHORT_TERM)
        collection = client.get_collection(name=CHROMA_COLLECTION_SHORT_TERM)

    data = collection.get(include=["documents", "metadatas"])
    ids = data.get("ids", [])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])

    total = len(ids)
    if limit is not None:
        ids = ids[:limit]
        docs = docs[:limit]
        metas = metas[:limit]

    updated = 0
    skipped = 0
    total_raw_chars = 0
    total_new_chars = 0
    examples = []

    for idx, (mem_id, doc, meta) in enumerate(zip(ids, docs, metas), start=1):
        meta = meta or {}
        raw = str(doc or "").strip()
        if not raw:
            skipped += 1
            continue

        total_raw_chars += len(raw)

        if meta.get("summary_style") in {"concise_turn_memory_v1", "code_change_turn_memory_v1"} and meta.get("summary_chars"):
            total_new_chars += int(meta.get("summary_chars") or len(raw))
            skipped += 1
            continue

        summarized, summary_style = ConversationManager._summarize_for_short_term(
            role=str(meta.get("role", "unknown")),
            content=raw,
        )
        summarized = summarized.strip()

        if not summarized:
            summarized = raw[:320]

        total_new_chars += len(summarized)
        new_meta = {
            **meta,
            "raw_chars": len(raw),
            "summary_chars": len(summarized),
            "summary_style": summary_style,
            "migration_tag": "short_term_rewrite_v1",
        }
        collection.update(ids=[mem_id], documents=[summarized], metadatas=[new_meta])
        updated += 1

        if len(examples) < 5:
            examples.append({
                "id": mem_id,
                "raw_chars": len(raw),
                "summary_chars": len(summarized),
                "before": raw[:240],
                "after": summarized[:240],
            })

    return {
        "total_entries": total,
        "processed_entries": len(ids),
        "updated": updated,
        "skipped": skipped,
        "raw_chars_processed": total_raw_chars,
        "new_chars_processed": total_new_chars,
        "shrink_ratio": round((1 - (total_new_chars / total_raw_chars)), 4) if total_raw_chars else 0.0,
        "examples": examples,
    }


if __name__ == "__main__":
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except Exception:
            limit = None
    result = migrate_short_term_memory(limit=limit)
    print(json.dumps(result, indent=2, ensure_ascii=True))
