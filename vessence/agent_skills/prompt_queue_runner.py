#!/usr/bin/env python3
"""
prompt_queue_runner.py — Autonomous prompt queue processor.

Reads vault/documents/prompt_list.md, finds the first uncompleted prompt,
runs it via the shared automation runner, sends the result to Discord, marks the prompt
[COMPLETE] or [INCOMPLETE], and logs to short-term memory.

Checks idle state before each prompt — stops if user becomes active.

Usage:
    prompt_queue_runner.py
    prompt_queue_runner.py --force   # skip idle check (for testing)
"""

import os
import sys
import json
import time
import argparse
import datetime
import subprocess
import requests
import re
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from jane.config import get_chroma_client, ENV_FILE_PATH
load_dotenv(ENV_FILE_PATH)

from jane.config import (
    PROMPT_LIST_PATH, ACCOMPLISHED_PATH,
    USER_STATE_PATH, IDLE_STATE_PATH,
    JANE_BRIDGE_ENV as ENV_FILE,
    IDLE_THRESHOLD_SECS as IDLE_THRESHOLD,
    CHIEH_USER_ID,
    ADD_MEMORY_SCRIPT as ADD_MEMORY, ADD_FACT_SCRIPT as ADD_FACT,
    QUEUE_ARCHIVE_THRESHOLD as ARCHIVE_THRESHOLD,
    PROMPT_QUEUE_LOG, LOGS_DIR,
    DISCORD_API_BASE, DISCORD_MAX_MSG_LEN, DISCORD_SAFE_CHUNK,
    HTTP_TIMEOUT_DISCORD, HTTP_TIMEOUT_CLAUDE,
    QUEUE_PAUSE_BETWEEN_SECS,
    VECTOR_DB_SHORT_TERM, ADK_VENV_PYTHON,
)
# automation_runner no longer used — queue now calls internal web API directly

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [queue_runner] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(PROMPT_QUEUE_LOG)],
)
logger = logging.getLogger("prompt_queue_runner")


# ── Idle check ─────────────────────────────────────────────────────────────────
def is_idle() -> bool:
    """Returns True if the user has been idle for > IDLE_THRESHOLD seconds.
    Checks both user_state.json (Discord/Amber) and idle_state.json (Claude Code terminal).
    Any recent activity in either source counts as active.
    """
    now = time.time()
    most_recent_ts = 0

    # Check Discord activity (Amber)
    try:
        with open(USER_STATE_PATH) as f:
            state = json.load(f)
        ts = state.get("last_message_ts", 0)
        if ts > most_recent_ts:
            most_recent_ts = ts
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"user_state.json read error: {e}")

    # Check Claude Code terminal activity
    try:
        with open(IDLE_STATE_PATH) as f:
            state = json.load(f)
        ts = state.get("last_active_ts", 0)
        if ts > most_recent_ts:
            most_recent_ts = ts
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"idle_state.json read error: {e}")

    if most_recent_ts == 0:
        logger.info("No activity state found — assuming idle")
        return True

    idle_secs = now - most_recent_ts
    logger.info(f"Idle check: {idle_secs:.0f}s since last activity (threshold: {IDLE_THRESHOLD}s)")
    return idle_secs >= IDLE_THRESHOLD


# ── Notification sender (no-op — Discord disconnected, work log reserved for completions only)
def send_discord(message: str):
    """No-op. Notifications no longer posted to work log — only completions are logged."""
    pass


# ── Prompt list parser ──────────────────────────────────────────────────────────
def load_prompts() -> list[dict]:
    """
    Parse prompt_list.md into a list of {index, text, status} dicts.

    Format per entry:
        N. [status]
        Verbatim prompt text (possibly multiline)

           - sub-bullet outcome/note
    """
    with open(PROMPT_LIST_PATH) as f:
        content = f.read()

    STATUS_TAGS = {
        "[completed]":  "complete",
        "[COMPLETE]":   "complete",   # legacy
        "[incomplete]": "incomplete",
        "[INCOMPLETE]": "incomplete", # legacy
        "[new]":        "pending",
    }

    prompts = []
    chunks = re.split(r'\n(?=\d+\.\s)', content)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        first = lines[0].strip()
        m = re.match(r'^(\d+)\.\s*', first)
        if not m:
            continue
        idx = int(m.group(1))
        after_num = first[m.end():]

        status = "pending"
        inline_text = after_num
        for tag, s in STATUS_TAGS.items():
            if after_num.startswith(tag):
                status = s
                inline_text = after_num[len(tag):].strip()
                break

        # Collect verbatim lines; stop at first sub-bullet ("   - ")
        body_lines = []
        if inline_text:
            body_lines.append(inline_text)
        for line in lines[1:]:
            if line.startswith("   -") or line.startswith("\t-"):
                break
            if line.strip() == "---":
                break
            body_lines.append(line)

        text = "\n".join(body_lines).strip()
        prompts.append({"index": idx, "text": text, "status": status})

    return prompts


def mark_prompt(index: int, status: str, note: str = ""):
    """
    Update prompt_list.md: set the status tag and append a sub-bullet note.
    Preserves verbatim text exactly; replaces any existing sub-bullets for this entry.
    """
    with open(PROMPT_LIST_PATH) as f:
        content = f.read()

    tag = {"complete": "[completed]", "incomplete": "[incomplete]"}.get(status, "[new]")
    entry_re = re.compile(rf"^{index}\.\s")

    lines = content.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if entry_re.match(line):
            new_lines.append(f"{index}. {tag}")
            i += 1
            # Copy verbatim body lines; drop old sub-bullets
            body_lines = []
            while i < len(lines):
                l = lines[i]
                if re.match(r"^\d+\.\s", l):
                    break
                if l.startswith("   -") or l.startswith("\t-"):
                    i += 1
                    continue
                body_lines.append(l)
                i += 1
            # Strip trailing blank lines from body
            while body_lines and not body_lines[-1].strip():
                body_lines.pop()
            new_lines.extend(body_lines)
            # Append new sub-bullet
            if note:
                new_lines.append("")
                prefix = "" if status == "complete" else "Attempted: "
                new_lines.append(f"   - {prefix}{note}")
            new_lines.append("")
        else:
            new_lines.append(line)
            i += 1

    with open(PROMPT_LIST_PATH, "w") as f:
        f.write("\n".join(new_lines))

    log_queue_mutation(f"status → {status}", index, note=note)


def add_prompt(text: str) -> int:
    """Append a new [new] prompt entry to prompt_list.md. Returns the new index.
    Deduplicates: rejects if identical text already exists as a [new] entry."""
    text = text.strip()
    prompts = load_prompts()

    # Reject duplicate: same text already queued as [new]
    for p in prompts:
        if p.get("status") == "new" and p.get("text", "").strip() == text:
            print(f"Duplicate rejected — already queued as #{p['index']}")
            return p["index"]

    next_index = max((p["index"] for p in prompts), default=0) + 1

    with open(PROMPT_LIST_PATH, "a") as f:
        f.write(f"\n{next_index}. [new]\n{text}\n")

    log_queue_mutation("added", next_index, prompt_text=text)
    print(f"Added to prompt list as #{next_index}: {text[:60]}{'...' if len(text) > 60 else ''}")
    return next_index


def delete_prompt(index: int):
    """
    Remove a prompt entry from prompt_list.md by index and log the deletion
    to short-term memory.
    """
    with open(PROMPT_LIST_PATH) as f:
        content = f.read()

    # Find and capture the prompt text before deleting (for memory log)
    prompts = load_prompts()
    target = next((p for p in prompts if p["index"] == index), None)
    if not target:
        logger.warning(f"delete_prompt: index {index} not found.")
        print(f"Error: prompt #{index} not found.")
        return

    # Remove the entry block from the file
    entry_re = re.compile(rf"^{index}\.\s")
    lines = content.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if entry_re.match(line):
            i += 1
            # Skip the entire block until the next numbered entry
            while i < len(lines) and not re.match(r"^\d+\.\s", lines[i]):
                i += 1
        else:
            new_lines.append(line)
            i += 1

    # Strip any extra trailing blank lines left behind
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()
    new_lines.append("")

    with open(PROMPT_LIST_PATH, "w") as f:
        f.write("\n".join(new_lines))

    # Re-number remaining prompts to close the gap
    _renumber_prompts()

    log_queue_mutation("deleted", index, prompt_text=target["text"])
    logger.info(f"Deleted prompt #{index}.")
    print(f"Deleted prompt #{index}.")


def _renumber_prompts():
    """Re-number all prompt entries sequentially to eliminate gaps."""
    with open(PROMPT_LIST_PATH) as f:
        content = f.read()

    lines = content.split("\n")
    new_lines = []
    counter = 1
    for line in lines:
        m = re.match(r"^(\d+)\.\s", line)
        if m:
            line = re.sub(r"^\d+\.", f"{counter}.", line, count=1)
            counter += 1
        new_lines.append(line)

    with open(PROMPT_LIST_PATH, "w") as f:
        f.write("\n".join(new_lines))


def run_prompt(prompt_text: str) -> tuple[str, bool]:
    """
    Run prompt via the internal Jane web API (persistent session).
    Uses the same endpoint as web chat — no subprocess, no cold start.
    Returns (result_text, success).
    """
    logger.info("Sending prompt to persistent session via internal API...")

    short_desc = prompt_text[:80] + ("..." if len(prompt_text) > 80 else "")
    _announcements_path = os.path.join(
        os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")),
        "data", "jane_announcements.jsonl"
    )
    _progress_id = f"queue_{int(time.time()*1000)}"

    def _push_announcement(msg_text: str, is_final: bool = False):
        try:
            entry = json.dumps({
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "queue_progress",
                "id": _progress_id,
                "message": msg_text,
                "final": is_final,
            })
            with open(_announcements_path, "a") as f:
                f.write(entry + "\n")
        except Exception:
            pass

    _push_announcement(f"**Working on:** {short_desc}")

    jane_url = os.environ.get("JANE_WEB_URL", "http://localhost:8081")
    api_url = f"{jane_url}/api/jane/chat/stream"

    try:
        # Use a dedicated session for queue prompts so they share context
        # but don't pollute interactive user sessions
        resp = requests.post(
            api_url,
            json={
                "message": prompt_text,
                "session_id": "prompt_queue_session",
                "platform": "queue",
            },
            stream=True,
            timeout=(10, None),  # 10s connect timeout, no read timeout
        )
        if resp.status_code == 401:
            # Internal API needs auth bypass — fall back to sync endpoint
            resp = requests.post(
                f"{jane_url}/api/jane/chat",
                json={
                    "message": prompt_text,
                    "session_id": "prompt_queue_session",
                    "platform": "queue",
                },
                timeout=(10, 600),  # 10min read timeout for sync
            )
            if resp.ok:
                data = resp.json()
                response = data.get("text", "")
                _push_announcement(f"**Completed:** {short_desc}", is_final=True)
                return response, bool(response)
            else:
                _push_announcement(f"**Failed:** HTTP {resp.status_code}", is_final=True)
                return f"Error: HTTP {resp.status_code}", False

        # Stream SSE response and collect full text
        response_text = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") == "delta":
                response_text += event.get("data", "")
            elif event.get("type") == "done":
                if not response_text:
                    response_text = event.get("data", "")
                break
            elif event.get("type") == "error":
                err = event.get("data", "Unknown error")
                _push_announcement(f"**Failed:** {err[:100]}", is_final=True)
                return f"Error: {err}", False

        # Log to Work Log
        try:
            from agent_skills.work_log_tools import log_activity
            result_snippet = (response_text or "")[:150].replace("\n", " ").strip()
            log_activity(f"Completed: {short_desc} → {result_snippet}", category="prompt_completed")
        except Exception:
            pass

        _push_announcement(f"**Completed:** {short_desc}", is_final=True)
        return response_text, bool(response_text.strip())

    except requests.ConnectionError:
        msg = "Jane web is not running — skipping this cycle"
        logger.warning(msg)
        _push_announcement(f"**Skipped:** {msg}", is_final=True)
        return msg, False
    except Exception as e:
        _push_announcement(f"**Failed:** {str(e)[:100]}", is_final=True)
        return f"Error: {e}", False


# ── Short-term memory logger ────────────────────────────────────────────────────
def log_queue_mutation(action: str, prompt_index: int, prompt_text: str = "", note: str = ""):
    """Log queue mutations to the log file only — NOT to short-term memory.

    Queue add/delete/status-change events are ephemeral and pollute ChromaDB
    with low-value entries. Only successful completions (via log_to_memory)
    should be persisted to memory.
    """
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    summary = prompt_text[:80] + ('...' if len(prompt_text) > 80 else '') if prompt_text else ''
    logger.info(
        "Queue mutation: %s item #%d%s%s",
        action, prompt_index,
        f" — {summary}" if summary else "",
        f" ({note})" if note else "",
    )


def log_to_memory(prompt_index: int, prompt_text: str, result: str, success: bool):
    if not success:
        # Failures/timeouts are logged to the log file only — they retry and
        # would spam ChromaDB with duplicate "timed out" entries.
        logger.info("Prompt #%d FAIL/INCOMPLETE — not persisting to memory", prompt_index)
        return

    date_str = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    fact = (
        f"Prompt queue item {prompt_index} processed autonomously on {date_str}. "
        f"Status: SUCCESS. "
        f"Prompt: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}. "
        f"Result summary: {result[:300]}{'...' if len(result) > 300 else ''}"
    )
    try:
        # Short-term: expires in 14 days
        subprocess.run(
            [ADD_MEMORY, fact, "--topic", "prompt_queue", "--author", "jane"],
            capture_output=True, timeout=30
        )
        # Long-term: permanent record of what was accomplished
        subprocess.run(
            [ADD_FACT, fact, "--topic", "prompt_queue", "--subtopic", f"item_{prompt_index}"],
            capture_output=True, timeout=30
        )
    except Exception as e:
        logger.warning(f"Failed to log to memory: {e}")


# ── Prompt summary ──────────────────────────────────────────────────────────────
def prompt_summary(text: str, max_chars: int = 400) -> str:
    """
    Return a readable summary of the prompt for Discord notifications.
    Shows the full prompt up to max_chars so the user can recognize what's running.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text
    # Try to cut at a sentence or line boundary near max_chars
    cut = text[:max_chars]
    for sep in ('\n', '. ', '! ', '? '):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[:idx + len(sep)].strip() + "\n_(prompt continues…)_"
    return cut.rstrip() + "…"


# ── Archiver ────────────────────────────────────────────────────────────────────
def archive_completed_prompts():
    """
    If prompt_list.md exceeds ARCHIVE_THRESHOLD entries, move all [completed]
    prompts to accomplished_prompts.md and delete their ChromaDB memory entries.
    """
    prompts = load_prompts()
    if len(prompts) <= ARCHIVE_THRESHOLD:
        return

    completed = [p for p in prompts if p["status"] == "complete"]
    if not completed:
        return

    logger.info(f"List has {len(prompts)} prompts (>{ARCHIVE_THRESHOLD}) — archiving {len(completed)} completed.")

    # ── Append to accomplished_prompts.md ──
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    with open(ACCOMPLISHED_PATH, "a") as f:
        f.write(f"\n\n## Archived {now}\n\n")
        for p in completed:
            f.write(f"### Prompt #{p['index']}\n\n{p['text']}\n\n---\n")

    # ── Remove completed entries from prompt_list.md ──
    with open(PROMPT_LIST_PATH) as f:
        content = f.read()

    completed_indices = {p["index"] for p in completed}
    chunks = re.split(r'\n(?=\d+\.\s)', content)
    kept = []
    for chunk in chunks:
        m = re.match(r'^(\d+)\.\s', chunk.strip())
        if m and int(m.group(1)) in completed_indices:
            continue
        kept.append(chunk)

    # Re-number remaining prompts sequentially
    header_chunks = [c for c in kept if not re.match(r'^\d+\.\s', c.strip())]
    item_chunks   = [c for c in kept if re.match(r'^\d+\.\s', c.strip())]
    renumbered = []
    for new_idx, chunk in enumerate(item_chunks, start=1):
        chunk = re.sub(r'^\d+\.', f"{new_idx}.", chunk.strip())
        renumbered.append(chunk)

    new_content = "\n\n".join(header_chunks + renumbered).strip() + "\n"
    with open(PROMPT_LIST_PATH, "w") as f:
        f.write(new_content)

    # ── Delete ChromaDB short-term memory entries for archived prompts ──
    try:
        _REQUIRED_PYTHON = ADK_VENV_PYTHON
        SHORT_TERM_DB = VECTOR_DB_SHORT_TERM
        purge_script = (
            "import os; os.environ['ORT_LOGGING_LEVEL']='3'\n"
            "import chromadb, sys\n"
            f"client = get_chroma_client(path='{SHORT_TERM_DB}')\n"
            "col = client.get_or_create_collection('short_term_memory')\n"
            f"indices = {list(completed_indices)}\n"
            "results = col.get(where={'topic': 'prompt_queue'}, include=['metadatas'])\n"
            "to_delete = [id for id, meta in zip(results['ids'], results['metadatas'])\n"
            "             if any(meta.get('subtopic','') == f'item_{i}' for i in indices)]\n"
            "if to_delete:\n"
            "    col.delete(ids=to_delete)\n"
            "    print(f'Deleted {len(to_delete)} ChromaDB entries')\n"
        )
        subprocess.run([_REQUIRED_PYTHON, "-c", purge_script], capture_output=True, timeout=30)
    except Exception as e:
        logger.warning(f"ChromaDB purge error: {e}")

    archived_count = len(completed)
    send_discord(
        f"🗂️ **Prompt list archived** — {archived_count} completed prompt(s) moved to "
        f"`accomplished_prompts.md`. List re-numbered from {len(prompts)} → {len(prompts) - archived_count} entries."
    )
    logger.info(f"Archived {archived_count} prompts.")


# ── Main ────────────────────────────────────────────────────────────────────────
def _acquire_run_lock() -> "open | None":
    """Acquire an exclusive file lock to prevent concurrent queue runs. Returns lock file handle or None."""
    import fcntl
    lock_path = os.path.join(LOGS_DIR, "prompt_queue_runner.lock")
    try:
        lock_fh = open(lock_path, "w")
        fcntl.lockf(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fh
    except (IOError, OSError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Skip idle check")
    parser.add_argument("--add", type=str, metavar="TEXT", help="Append a new prompt to the list")
    parser.add_argument("--delete", type=int, metavar="INDEX", help="Delete a prompt by index and log to memory")
    args = parser.parse_args()

    os.makedirs(LOGS_DIR, exist_ok=True)

    if args.add:
        add_prompt(args.add)
        return

    if args.delete:
        delete_prompt(args.delete)
        return

    # Prevent concurrent queue runs from cron overlap
    lock_fh = _acquire_run_lock()
    if lock_fh is None:
        logger.info("Another queue runner is already active — exiting.")
        return

    if not args.force and not is_idle():
        logger.info("User is active — exiting without processing.")
        lock_fh.close()
        return

    prompts = load_prompts()
    actionable = [p for p in prompts if p["status"] in ("pending", "incomplete")]

    if not actionable:
        logger.info("No pending or incomplete prompts.")
        return

    for prompt in actionable:
        # Re-check idle before each prompt
        if not args.force and not is_idle():
            logger.info(f"User became active — pausing queue.")
            send_discord("⏸ Paused prompt queue — you became active. Resuming when idle again.")
            return

        # Check system load — wait until CPU/memory is acceptable
        try:
            from agent_skills.system_load import wait_until_safe
            if not wait_until_safe(max_wait_minutes=15, check_interval_seconds=60):
                logger.info("System still busy after 15 min — skipping remaining prompts.")
                return
        except Exception:
            pass  # system_load not available, proceed anyway

        idx = prompt["index"]
        text = prompt["text"]
        is_retry = prompt["status"] == "incomplete"

        if is_retry:
            logger.info(f"Retrying incomplete prompt {idx}")
            send_discord(
                f"🔄 **Retrying prompt #{idx}** _(previously incomplete)_\n\n"
                f"{prompt_summary(text)}"
            )
            # Prepend failure context so Claude can diagnose and fix
            run_text = (
                f"This prompt previously ran but was marked INCOMPLETE (empty or failed result). "
                f"Please investigate why it may have failed, then complete it properly.\n\n"
                f"Original prompt:\n{text}"
            )
        else:
            logger.info(f"Processing prompt {idx}")
            send_discord(
                f"🤖 **Starting prompt #{idx}:**\n\n"
                f"{prompt_summary(text)}"
            )
            run_text = text

        result, success = run_prompt(run_text)
        log_to_memory(idx, text, result, success)

        status = "complete" if success else "incomplete"
        note = result[:200].replace('\n', ' ').strip()
        mark_prompt(idx, status, note=note)

        if success:
            discord_msg = (
                f"✅ **Prompt #{idx} COMPLETE**\n\n"
                f"**Result:**\n{result}"
            )
        else:
            failure_detail = (
                result.strip()
                if result.strip()
                else "_(No output returned — possible timeout, permission error, or execution failure.)_"
            )
            discord_msg = (
                f"⚠️ **Prompt #{idx} INCOMPLETE**\n\n"
                f"**Prompt was:**\n{prompt_summary(text)}\n\n"
                f"**What went wrong:**\n{failure_detail}\n\n"
                f"_Review the above and edit the prompt or fix the underlying issue before the next retry._"
            )
        send_discord(discord_msg)
        logger.info(f"Prompt {idx} done: {status}")

        # Small pause between prompts
        time.sleep(QUEUE_PAUSE_BETWEEN_SECS)

    logger.info("Prompt queue run complete.")
    archive_completed_prompts()


if __name__ == "__main__":
    main()
