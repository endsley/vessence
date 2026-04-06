#!/usr/bin/env python3
"""
topic_memory.py — Topic-based short-term memory system.

Called asynchronously after each turn (fire-and-forget, separate process).
Uses Haiku to classify topic + update/create summary in ChromaDB.

Usage:
    # From Python (fire-and-forget):
    subprocess.Popen([PYTHON, __file__, '--user', msg, '--assistant', response])

    # From shell (Stop hook):
    echo '{"user":"...","assistant":"..."}' | python topic_memory.py --stdin
"""

import sys
import os
import json
import datetime
import argparse
import logging

logger = logging.getLogger("topic_memory")

# Suppress ONNX noise
os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')

sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from jane.config import (
    get_chroma_client,
    VECTOR_DB_SHORT_TERM,
    CHROMA_COLLECTION_SHORT_TERM,
    SHORT_TERM_TTL_DAYS,
)

MAX_TOPIC_CHARS = 1000
TRIGGER_EVERY_N_TURNS = 2  # only process every Nth turn to reduce API calls
TURN_COUNTER_FILE = os.path.join(
    os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")),
    "data", "topic_memory_turn_counter.json",
)


def _silence_stderr():
    """Redirect stderr to suppress ONNX/ChromaDB noise."""
    null_fd = os.open(os.devnull, os.O_WRONLY)
    old = os.dup(2)
    os.dup2(null_fd, 2)
    os.close(null_fd)
    return old


def _restore_stderr(old):
    os.dup2(old, 2)
    os.close(old)


def _get_collection():
    old = _silence_stderr()
    try:
        client = get_chroma_client(path=VECTOR_DB_SHORT_TERM)
        return client.get_or_create_collection(CHROMA_COLLECTION_SHORT_TERM)
    finally:
        _restore_stderr(old)


def _find_nearest_topics(collection, query_text: str, n_results: int = 5) -> list[dict]:
    """Vector search for the top-N most similar existing topic entries."""
    old = _silence_stderr()
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where={"memory_type": "short_term_topic"},
            include=["documents", "metadatas", "distances"],
        )
    finally:
        _restore_stderr(old)

    topics = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            topics.append({
                "id": doc_id,
                "topic": results["metadatas"][0][i].get("topic", "unknown"),
                "summary": results["documents"][0][i],
                "distance": results["distances"][0][i],
                "updated_at": results["metadatas"][0][i].get("updated_at", ""),
            })
    return topics


def _call_claude(user_msg: str, assistant_msg: str, existing_topics: list[dict]) -> dict:
    """
    Use claude CLI (--print) to classify topic + produce updated summary.
    Inherits OAuth from the user's Claude Code session — no API key needed.

    Returns: {"action": "update"|"create"|"skip", "topic_id": "...", "topic_title": "...", "summary": "..."}
    """
    import subprocess

    topic_list = ""
    if existing_topics:
        for t in existing_topics:
            dist_info = f" (similarity: {1 - t.get('distance', 1):.2f})" if 'distance' in t else ""
            topic_list += f"- ID: {t['id']} | Title: {t['topic']}{dist_info} | Summary: {t['summary'][:300]}\n"
    else:
        topic_list = "(none — this will be the first topic)\n"

    prompt = f"""You manage a topic-based short-term memory system. Given a conversation turn, you must:
1. Decide if this turn belongs to an EXISTING topic or is a NEW topic
2. Produce an updated summary (or new summary) under {MAX_TOPIC_CHARS} characters

Existing topics:
{topic_list}
Latest exchange:
USER: {user_msg[:500]}
ASSISTANT: {assistant_msg[:500]}

Rules:
- If the turn clearly matches an existing topic, UPDATE that topic's summary by merging new info
- If the turn is about something new, CREATE a new topic
- If the turn is low-value (greetings, "ok", "thanks", short acknowledgments), return {{"action": "skip"}}
- Summary must be under {MAX_TOPIC_CHARS} chars, factual, concise — capture decisions, actions, status, next steps
- If updating and the merged summary would exceed {MAX_TOPIC_CHARS} chars, compress older details to fit
- Topic titles should be short and descriptive (under 60 chars)

Respond with ONLY valid JSON (no markdown, no explanation):
{{"action": "update"|"create"|"skip", "topic_id": "existing_id_or_null", "topic_title": "short title", "summary": "the summary text"}}"""

    claude_bin = os.environ.get("CLAUDE_BIN", os.path.expanduser("~/.local/bin/claude"))
    result = subprocess.run(
        [claude_bin, "--print", "--model", "haiku", prompt],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude --print failed: {result.stderr[:200]}")

    text = result.stdout.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)


def _should_skip(user_msg: str, assistant_msg: str) -> bool:
    """Quick pre-filter to skip obviously low-value turns without an API call."""
    user_clean = (user_msg or "").strip().lower()
    if not user_clean:
        return True
    low_value = {
        "ok", "okay", "yes", "yeah", "yep", "no", "nope", "thanks", "thank you",
        "got it", "sounds good", "cool", "nice", "done", "sure", "go ahead",
        "continue", "next", "status?",
    }
    if user_clean in low_value:
        return True
    if len(user_clean) <= 5 and not user_clean.endswith("?"):
        return True
    return False


def _increment_turn_counter() -> int:
    """Increment and return the turn counter. Persists across sessions."""
    os.makedirs(os.path.dirname(TURN_COUNTER_FILE), exist_ok=True)
    count = 0
    try:
        with open(TURN_COUNTER_FILE) as f:
            count = json.load(f).get("count", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    count += 1
    with open(TURN_COUNTER_FILE, "w") as f:
        json.dump({"count": count}, f)
    return count


def process_turn(user_msg: str, assistant_msg: str, source: str = "unknown"):
    """
    Main entry point. Classifies topic, updates/creates short-term memory entry.
    Designed to be called in a background process — never blocks the main conversation.
    Only fires every TRIGGER_EVERY_N_TURNS turns.
    """
    if _should_skip(user_msg, assistant_msg):
        return

    turn_num = _increment_turn_counter()
    if turn_num % TRIGGER_EVERY_N_TURNS != 0:
        return  # Skip this turn

    collection = _get_collection()
    # Vector search for top 3 most relevant existing topics
    query = f"{user_msg} {assistant_msg[:200]}"
    nearest_topics = _find_nearest_topics(collection, query, n_results=3)

    try:
        result = _call_claude(user_msg, assistant_msg, nearest_topics)
    except Exception as e:
        logger.error(f"Haiku call failed: {e}")
        return

    action = result.get("action", "skip")
    if action == "skip":
        return

    now = datetime.datetime.now(datetime.UTC)
    expires = (now + datetime.timedelta(days=SHORT_TERM_TTL_DAYS)).isoformat()

    summary = result.get("summary", "")[:MAX_TOPIC_CHARS]
    topic_title = result.get("topic_title", "untitled")[:60]

    if action == "update" and result.get("topic_id"):
        topic_id = result["topic_id"]
        # Verify the ID actually exists in the candidates
        existing_ids = [t["id"] for t in nearest_topics]
        if topic_id not in existing_ids:
            # Haiku hallucinated an ID — treat as create
            action = "create"
        else:
            old = _silence_stderr()
            try:
                collection.upsert(
                    ids=[topic_id],
                    documents=[summary],
                    metadatas=[{
                        "topic": topic_title,
                        "source": source,
                        "updated_at": now.isoformat(),
                        "expires_at": expires,
                        "memory_type": "short_term_topic",
                    }],
                )
            finally:
                _restore_stderr(old)
            return

    if action == "create":
        topic_id = f"topic_{now.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
        old = _silence_stderr()
        try:
            collection.upsert(
                ids=[topic_id],
                documents=[summary],
                metadatas=[{
                    "topic": topic_title,
                    "source": source,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "expires_at": expires,
                    "memory_type": "short_term_topic",
                }],
            )
        finally:
            _restore_stderr(old)


def fire_and_forget(user_msg: str, assistant_msg: str, source: str = "cli"):
    """Launch topic memory processing in a background subprocess."""
    import subprocess
    python = sys.executable
    script = os.path.abspath(__file__)
    subprocess.Popen(
        [python, script, "--user", user_msg[:2000], "--assistant", assistant_msg[:2000], "--source", source],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Topic-based short-term memory")
    parser.add_argument("--user", type=str, default="", help="User message")
    parser.add_argument("--assistant", type=str, default="", help="Assistant response")
    parser.add_argument("--source", type=str, default="cli", help="Source platform")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin")
    args = parser.parse_args()

    if args.stdin:
        data = json.load(sys.stdin)
        args.user = data.get("user", "")
        args.assistant = data.get("assistant", "")
        args.source = data.get("source", "cli")

    if not args.user and not args.assistant:
        return

    process_turn(args.user, args.assistant, args.source)


if __name__ == "__main__":
    main()
