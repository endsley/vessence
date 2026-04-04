#!/usr/bin/env python3
import json
import os
import sys
import uuid
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
import ollama

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import (
    VECTOR_DB_LONG_TERM,
    CHROMA_COLLECTION_LONG_TERM,
    LOCAL_LLM_MODEL,
)


REVIEW_THRESHOLD = 500
REWRITE_THRESHOLD = 800
SPLIT_THRESHOLD = 1500
MAX_REWRITTEN_CHARS = 500
MAX_SPLIT_ITEMS = 6


def _extract_json(text: str):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def _qwen(prompt: str) -> str:
    response = ollama.chat(
        model=LOCAL_LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You convert large archived technical memory into compact long-term memory. "
                    "Preserve only durable facts, decisions, root causes, fixes, lessons, and open risks. "
                    "Avoid filler, UI noise, repeated boilerplate, and raw transcript style."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    return (response.get("message", {}) or {}).get("content", "").strip()


def rewrite_memory(doc: str) -> str:
    prompt = (
        "Rewrite this long-term memory into one compact durable memory.\n"
        f"Requirements:\n"
        f"- under {MAX_REWRITTEN_CHARS} characters\n"
        "- keep only reusable facts, decisions, fixes, root causes, or lessons learned\n"
        "- remove raw terminal noise, login chatter, and repeated boilerplate\n"
        "- output plain text only\n\n"
        f"Memory:\n{doc}"
    )
    rewritten = _qwen(prompt)
    return rewritten[:MAX_REWRITTEN_CHARS].strip() or doc[:MAX_REWRITTEN_CHARS].strip()


def split_memory(doc: str) -> list[str]:
    prompt = (
        "Split this oversized long-term memory into atomic durable memories.\n"
        "Return ONLY valid JSON with this schema:\n"
        '{"memories":["...", "..."]}\n'
        f"Requirements:\n"
        f"- 2 to {MAX_SPLIT_ITEMS} memories\n"
        "- each item should be short, standalone, and reusable later\n"
        "- keep only durable facts, decisions, fixes, root causes, lessons, and open risks\n"
        "- remove transcript noise, decorative formatting, terminal art, and login/update chatter\n"
        "- each item should ideally stay under 400 characters\n\n"
        f"Memory:\n{doc}"
    )
    raw = _qwen(prompt)
    parsed = _extract_json(raw) or {}
    memories = []
    for item in parsed.get("memories", []) or []:
        text = str(item or "").strip()
        if text:
            memories.append(text[:500])
    if memories:
        return memories[:MAX_SPLIT_ITEMS]

    fallback = rewrite_memory(doc)
    return [fallback] if fallback else []


def normalize_long_term_memory(limit: int | None = None) -> dict:
    with silence_stderr_fd():
        client = chromadb.PersistentClient(path=VECTOR_DB_LONG_TERM)
        collection = client.get_collection(name=CHROMA_COLLECTION_LONG_TERM)

    data = collection.get(include=["documents", "metadatas"])
    ids = data.get("ids", [])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])

    items = list(zip(ids, docs, metas))
    if limit is not None:
        items = items[:limit]

    reviewed = 0
    rewritten = 0
    split = 0
    unchanged = 0
    deleted = 0
    old_total_chars = 0
    new_total_chars = 0
    examples = []

    for mem_id, doc, meta in items:
        text = str(doc or "").strip()
        meta = meta or {}
        size = len(text)
        if size <= REVIEW_THRESHOLD:
            unchanged += 1
            continue
        if meta.get("normalized_style") == "long_term_normalized_v1":
            unchanged += 1
            continue

        reviewed += 1
        old_total_chars += size

        if size > SPLIT_THRESHOLD:
            parts = split_memory(text)
            if not parts:
                unchanged += 1
                new_total_chars += size
                continue
            new_ids = [str(uuid.uuid4()) for _ in parts]
            new_metas = []
            for idx, part in enumerate(parts, start=1):
                new_metas.append({
                    **meta,
                    "raw_chars": size,
                    "summary_chars": len(part),
                    "normalized_style": "long_term_normalized_v1",
                    "normalized_from": mem_id,
                    "normalized_part": idx,
                    "normalized_parts_total": len(parts),
                })
                new_total_chars += len(part)
            collection.add(ids=new_ids, documents=parts, metadatas=new_metas)
            collection.delete(ids=[mem_id])
            split += 1
            deleted += 1
            if len(examples) < 5:
                examples.append({
                    "id": mem_id,
                    "mode": "split",
                    "raw_chars": size,
                    "parts": [p[:220] for p in parts],
                })
            continue

        if size > REWRITE_THRESHOLD:
            compact = rewrite_memory(text)
            if not compact:
                unchanged += 1
                new_total_chars += size
                continue
            collection.update(
                ids=[mem_id],
                documents=[compact],
                metadatas=[{
                    **meta,
                    "raw_chars": size,
                    "summary_chars": len(compact),
                    "normalized_style": "long_term_normalized_v1",
                }],
            )
            rewritten += 1
            new_total_chars += len(compact)
            if len(examples) < 5:
                examples.append({
                    "id": mem_id,
                    "mode": "rewrite",
                    "raw_chars": size,
                    "summary_chars": len(compact),
                    "before": text[:220],
                    "after": compact[:220],
                })
            continue

        unchanged += 1
        new_total_chars += size

    return {
        "reviewed": reviewed,
        "rewritten": rewritten,
        "split": split,
        "deleted_originals": deleted,
        "unchanged": unchanged,
        "raw_chars_reviewed": old_total_chars,
        "new_chars_written": new_total_chars,
        "shrink_ratio": round((1 - (new_total_chars / old_total_chars)), 4) if old_total_chars else 0.0,
        "thresholds": {
            "review_gt": REVIEW_THRESHOLD,
            "rewrite_gt": REWRITE_THRESHOLD,
            "split_gt": SPLIT_THRESHOLD,
        },
        "examples": examples,
    }


if __name__ == "__main__":
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except Exception:
            limit = None
    result = normalize_long_term_memory(limit=limit)
    print(json.dumps(result, indent=2, ensure_ascii=True))
