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
import time
import argparse
import datetime
import subprocess
import requests
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from jane.config import ENV_FILE_PATH
load_dotenv(ENV_FILE_PATH)

from jane.config import (
    PROMPT_LIST_PATH, ACCOMPLISHED_PATH,
    USER_STATE_PATH, IDLE_STATE_PATH,
    JANE_BRIDGE_ENV as ENV_FILE,
    IDLE_THRESHOLD_SECS as IDLE_THRESHOLD,
    OWNER_USER_ID,
    ADD_MEMORY_SCRIPT as ADD_MEMORY, ADD_FACT_SCRIPT as ADD_FACT,
    QUEUE_ARCHIVE_THRESHOLD as ARCHIVE_THRESHOLD,
    PROMPT_QUEUE_LOG, LOGS_DIR,
    DISCORD_API_BASE, DISCORD_MAX_MSG_LEN, DISCORD_SAFE_CHUNK,
    HTTP_TIMEOUT_DISCORD, HTTP_TIMEOUT_CLAUDE,
    QUEUE_PAUSE_BETWEEN_SECS,
    VECTOR_DB_SHORT_TERM, ADK_VENV_PYTHON,
)
# automation_runner no longer used — queue now calls internal web API directly
from agent_skills.prompt_queue_docs import (
    delete_prompt_entry,
    parse_prompt_list,
    prompt_failure_detail,
    prompt_result_discord_message,
    prompt_result_note,
    prompt_result_status,
    prompt_summary,
    queue_prompt_run_text,
    remove_completed_prompt_entries,
    render_prompt_status_update,
    render_completed_archive_section,
    renumber_prompt_entries,
)
from agent_skills.prompt_queue_idle import (
    is_idle_from_timestamp as _is_idle_from_timestamp,
    most_recent_activity_timestamp as _most_recent_activity_timestamp,
    read_activity_timestamp as _read_activity_timestamp,
)
from agent_skills.prompt_queue_memory import (
    completion_fact as _completion_fact,
    mutation_prompt_summary as _mutation_prompt_summary,
    prompt_queue_chroma_purge_script as _prompt_queue_chroma_purge_script,
)
from agent_skills.queue_progress_announcements import (
    append_queue_progress_announcement as _append_queue_progress_announcement,
    queue_announcements_path as _queue_announcements_path,
    queue_progress_id as _queue_progress_id,
    queue_progress_json_line as _queue_progress_json_line,
)
from agent_skills.queue_jane_api import (
    parse_queue_stream_lines as _parse_queue_stream_lines,
    queue_chat_payload as _queue_chat_payload,
    run_queue_chat_request as _run_queue_chat_request,
)

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
    most_recent_ts = _most_recent_activity_timestamp(
        (
            (USER_STATE_PATH, "last_message_ts"),
            (IDLE_STATE_PATH, "last_active_ts"),
        ),
        logger=logger,
    )

    if most_recent_ts == 0:
        logger.info("No activity state found — assuming idle")
        return True

    idle_secs = now - most_recent_ts
    logger.info(f"Idle check: {idle_secs:.0f}s since last activity (threshold: {IDLE_THRESHOLD}s)")
    return _is_idle_from_timestamp(now, most_recent_ts, IDLE_THRESHOLD)


# ── Notification sender (no-op — Discord disconnected, work log reserved for completions only)
def send_discord(message: str):
    """No-op. Notifications no longer posted to work log — only completions are logged."""
    pass


# ── Prompt list parser ──────────────────────────────────────────────────────────
def load_prompts() -> list[dict]:
    with open(PROMPT_LIST_PATH) as f:
        return parse_prompt_list(f.read())


def mark_prompt(index: int, status: str, note: str = ""):
    """
    Update prompt_list.md: set the status tag and append a sub-bullet note.
    Preserves verbatim text exactly; replaces any existing sub-bullets for this entry.
    """
    with open(PROMPT_LIST_PATH) as f:
        content = f.read()

    with open(PROMPT_LIST_PATH, "w") as f:
        f.write(render_prompt_status_update(content, index, status, note))

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

    with open(PROMPT_LIST_PATH, "w") as f:
        f.write(delete_prompt_entry(content, index))

    # Re-number remaining prompts to close the gap
    _renumber_prompts()

    log_queue_mutation("deleted", index, prompt_text=target["text"])
    logger.info(f"Deleted prompt #{index}.")
    print(f"Deleted prompt #{index}.")


def _renumber_prompts():
    """Re-number all prompt entries sequentially to eliminate gaps."""
    with open(PROMPT_LIST_PATH) as f:
        content = f.read()

    with open(PROMPT_LIST_PATH, "w") as f:
        f.write(renumber_prompt_entries(content))


def run_prompt(prompt_text: str) -> tuple[str, bool]:
    """
    Run prompt via the internal Jane web API (persistent session).
    Uses the same endpoint as web chat — no subprocess, no cold start.
    Returns (result_text, success).
    """
    logger.info("Sending prompt to persistent session via internal API...")

    short_desc = prompt_text[:80] + ("..." if len(prompt_text) > 80 else "")
    _announcements_path = _queue_announcements_path(
        os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")),
    )
    _progress_id = _queue_progress_id("queue", int(time.time()*1000))

    def _push_announcement(msg_text: str, is_final: bool = False):
        try:
            _append_queue_progress_announcement(
                _announcements_path,
                _progress_id,
                msg_text,
                is_final,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
        except Exception:
            pass

    _push_announcement(f"**Working on:** {short_desc}")

    jane_url = os.environ.get("JANE_WEB_URL", "http://localhost:8081")

    try:
        stream_result = _run_queue_chat_request(
            jane_url,
            prompt_text,
            "prompt_queue_session",
            post=requests.post,
        )
        if stream_result.error:
            _push_announcement(f"**Failed:** {stream_result.error[:100]}", is_final=True)
            return stream_result.text, False
        response_text = stream_result.text

        # Log to Work Log
        if stream_result.source == "stream":
            try:
                from agent_skills.work_log_tools import log_activity
                result_snippet = (response_text or "")[:150].replace("\n", " ").strip()
                log_activity(f"Completed: {short_desc} → {result_snippet}", category="prompt_completed")
            except Exception:
                pass

        _push_announcement(f"**Completed:** {short_desc}", is_final=True)
        return response_text, stream_result.success

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
    summary = _mutation_prompt_summary(prompt_text)
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
    fact = _completion_fact(prompt_index, prompt_text, result, date_str)
    try:
        # Short-term: expires using the configured recent-memory TTL
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
        f.write(render_completed_archive_section(completed, now))

    # ── Remove completed entries from prompt_list.md ──
    with open(PROMPT_LIST_PATH) as f:
        content = f.read()

    completed_indices = {p["index"] for p in completed}
    with open(PROMPT_LIST_PATH, "w") as f:
        f.write(remove_completed_prompt_entries(content, completed_indices))

    # ── Delete ChromaDB short-term memory entries for archived prompts ──
    try:
        _REQUIRED_PYTHON = ADK_VENV_PYTHON
        SHORT_TERM_DB = VECTOR_DB_SHORT_TERM
        purge_script = _prompt_queue_chroma_purge_script(SHORT_TERM_DB, completed_indices)
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
        else:
            logger.info(f"Processing prompt {idx}")
            send_discord(
                f"🤖 **Starting prompt #{idx}:**\n\n"
                f"{prompt_summary(text)}"
            )

        run_text = queue_prompt_run_text(text, is_retry)
        result, success = run_prompt(run_text)
        log_to_memory(idx, text, result, success)

        status = prompt_result_status(success)
        mark_prompt(idx, status, note=prompt_result_note(result))
        send_discord(prompt_result_discord_message(idx, text, result, success))
        logger.info(f"Prompt {idx} done: {status}")

        # Small pause between prompts
        time.sleep(QUEUE_PAUSE_BETWEEN_SECS)

    logger.info("Prompt queue run complete.")
    archive_completed_prompts()


if __name__ == "__main__":
    main()
