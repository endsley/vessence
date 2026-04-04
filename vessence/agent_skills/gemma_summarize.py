#!/usr/bin/env python3
"""
gemma_summarize.py — Called by the Stop hook after every Claude response.

Reads the most recent conversation turns from the session JSONL transcript,
calls gemma3:4b (fast local model) to summarize, and saves to short-term
ChromaDB memory. This gives crash resilience and context for subprocess sessions.

Stop hook input (stdin): {"session_id": "...", "stop_hook_active": bool, ...}
"""

import sys
import os
import json
import datetime
import subprocess
from pathlib import Path

_REQUIRED_PYTHON = os.environ.get('ADK_VENV_PYTHON', 'python3')
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

import ollama
import chromadb
import uuid

TRANSCRIPT_DIR   = os.path.join(os.path.expanduser('~'), '.claude', 'projects', f'-home-{os.environ.get("USER", "user")}')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import SHORT_TERM_TTL_DAYS, VECTOR_DB_SHORT_TERM

SHORT_TERM_DB    = VECTOR_DB_SHORT_TERM
GEMMA_MODEL      = "gemma3:4b"
TURNS_TO_INCLUDE = 6      # last N messages to summarize (user + assistant)
MIN_TEXT_LEN     = 100    # skip if too little content


def silence_stderr():
    """Suppress chromadb ONNX noise."""
    null_fd = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    os.dup2(null_fd, 2)
    os.close(null_fd)
    return old_stderr


def restore_stderr(old_fd):
    os.dup2(old_fd, 2)
    os.close(old_fd)


def extract_text_from_content(content) -> str:
    """Extract plain text from a message content block list."""
    if isinstance(content, str):
        return content
    texts = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif block.get("type") == "tool_result":
                # Include tool results briefly
                inner = block.get("content", "")
                if isinstance(inner, list):
                    for ib in inner:
                        if isinstance(ib, dict) and ib.get("type") == "text":
                            texts.append("[tool result] " + ib.get("text", "")[:200])
                elif isinstance(inner, str):
                    texts.append("[tool result] " + inner[:200])
    return "\n".join(t for t in texts if t.strip())


def read_recent_turns(session_id: str) -> str:
    """Read the last TURNS_TO_INCLUDE messages from the session JSONL."""
    path = os.path.join(TRANSCRIPT_DIR, f"{session_id}.jsonl")
    if not os.path.exists(path):
        return ""

    messages = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                msg = obj.get("message", {})
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    text = extract_text_from_content(content)
                    if text.strip():
                        messages.append((role, text.strip()))
            except Exception:
                continue

    # Take last N turns
    recent = messages[-TURNS_TO_INCLUDE:]
    if not recent:
        return ""

    parts = []
    for role, text in recent:
        label = os.environ.get("USER_NAME", "User") if role == "user" else "Jane"
        parts.append(f"{label}: {text[:600]}")
    return "\n\n".join(parts)


def summarize_with_gemma(text: str) -> str:
    """Call gemma3:4b to produce a concise summary."""
    prompt = (
        "Summarize the following conversation in 3-4 sentences. "
        "Focus on what was decided, implemented, or discovered. "
        "Be specific — name files, systems, or outcomes. "
        "Do not include filler phrases.\n\n"
        f"{text}"
    )
    response = ollama.chat(
        model=GEMMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"num_predict": 200, "temperature": 0.3}
    )
    return response["message"]["content"].strip()


def save_to_short_term(summary: str, session_id: str):
    """Write summary to short-term ChromaDB memory."""
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(days=SHORT_TERM_TTL_DAYS)
    fact = f"[Context snapshot {now.strftime('%Y-%m-%dT%H:%M:%SZ')}] {summary}"

    old_stderr = silence_stderr()
    try:
        client = chromadb.PersistentClient(path=SHORT_TERM_DB)
        collection = client.get_or_create_collection(
            name="short_term_memory",
            metadata={"hnsw:space": "cosine"},
        )
        collection.add(
            documents=[fact],
            ids=[str(uuid.uuid4())],
            metadatas=[{
                "memory_type": "short_term",
                "author": "jane",
                "topic": "context_snapshot",
                "subtopic": session_id[:8],
                "timestamp": now.isoformat(),
                "expires_at": expires.isoformat(),
                "ttl_days": SHORT_TERM_TTL_DAYS,
            }]
        )
    finally:
        restore_stderr(old_stderr)


def main():
    raw = sys.stdin.read().strip()
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    session_id = data.get("session_id", "")
    if not session_id:
        sys.exit(0)

    conversation_text = read_recent_turns(session_id)
    if len(conversation_text) < MIN_TEXT_LEN:
        sys.exit(0)

    try:
        summary = summarize_with_gemma(conversation_text)
        if summary:
            save_to_short_term(summary, session_id)
    except Exception as e:
        sys.stderr.write(f"gemma_summarize error: {e}\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
