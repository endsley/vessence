"""Background task offloader — runs big tasks async and posts progress via announcements."""

import json
import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_ROOT))

from jane.config import VESSENCE_HOME, VESSENCE_DATA_HOME

logger = logging.getLogger("jane.offloader")

ANNOUNCEMENTS_PATH = Path(VESSENCE_DATA_HOME) / "data" / "jane_announcements.jsonl"
# How often to emit a progress announcement while the task runs (seconds)
_PROGRESS_INTERVAL = 10


def _write_announcement(payload: dict) -> None:
    """Append a single JSON line to the announcements file."""
    ANNOUNCEMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ANNOUNCEMENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def offload_task(
    message: str,
    session_id: str,
    file_context: str | None = None,
    platform: str | None = None,
) -> str:
    """Spawn a background thread to run the task. Returns the task ID immediately.

    Progress and final results are written to the announcements JSONL file,
    which the frontend polls every 15 seconds.
    """
    task_id = f"bg_{uuid.uuid4().hex[:12]}"
    thread = threading.Thread(
        target=_run_task,
        args=(task_id, message, session_id, file_context, platform),
        daemon=True,
        name=f"offloader-{task_id}",
    )
    thread.start()
    logger.info("Offloaded task %s for session %s: %.80s", task_id, session_id[:12], message)
    return task_id


def _run_task(
    task_id: str,
    message: str,
    session_id: str,
    file_context: str | None,
    platform: str | None,
) -> None:
    """Execute the task in a background thread and post announcements."""
    from jane.automation_runner import run_automation_prompt, AutomationError
    from jane.context_builder import build_jane_context

    # Announce start
    _write_announcement({
        "id": task_id,
        "type": "queue_progress",
        "message": f"⏳ Working on your request in the background…\n\n> {_truncate(message, 200)}",
        "created_at": _now_iso(),
    })

    # Periodic progress heartbeat
    last_delta = ""
    delta_lock = threading.Lock()
    stop_heartbeat = threading.Event()

    def on_progress(chunk: str) -> None:
        nonlocal last_delta
        with delta_lock:
            last_delta = chunk

    def heartbeat_loop() -> None:
        while not stop_heartbeat.wait(_PROGRESS_INTERVAL):
            with delta_lock:
                snippet = last_delta[-300:] if last_delta else ""
            if snippet:
                _write_announcement({
                    "id": task_id,
                    "type": "queue_progress",
                    "message": f"⏳ Still working… (latest output)\n\n```\n{snippet}\n```",
                    "created_at": _now_iso(),
                })

    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()

    max_attempts = 2
    try:
        # Build context for the automation run.
        # Pull the session's conversation history so the offloaded task can
        # resolve pronouns like "this", "it", "that" back to Jane's previous
        # turns. Without this, messages like "please implement this" have
        # no antecedent and Jane responds "I don't know what you're referring to".
        history: list[dict] = []
        try:
            from jane_web.jane_proxy import _get_session
            state = _get_session(session_id)
            history = list(state.history) if state and state.history else []
        except Exception as exc:
            logger.warning("Could not load session history for offloaded task %s: %s", task_id, exc)

        system_prompt = ""
        prompt_text = message
        try:
            ctx = build_jane_context(message, history)
            system_prompt = ctx.system_prompt or ""
            # Use the transcript (Recent Conversation + User: message) as the
            # prompt so the model sees Jane's previous turns. The offloader
            # previously passed just `message`, which made pronouns like "this"
            # or "it" have no antecedent.
            if ctx.transcript:
                prompt_text = ctx.transcript
        except Exception:
            logger.warning("Context build failed for offloaded task %s, running without context", task_id)

        result = None
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = run_automation_prompt(
                    prompt_text,
                    system_prompt=system_prompt,
                    workdir=VESSENCE_HOME,
                    on_progress=on_progress,
                )
                last_error = None
                break
            except AutomationError as exc:
                last_error = exc
                is_empty_response = "empty response" in str(exc).lower()
                logger.warning(
                    "Offloaded task %s attempt %d/%d failed: %s",
                    task_id, attempt, max_attempts, exc,
                )
                if attempt < max_attempts and is_empty_response:
                    _write_announcement({
                        "id": task_id,
                        "type": "queue_progress",
                        "message": "⏳ Got an empty response — retrying…",
                        "created_at": _now_iso(),
                    })
                    time.sleep(2)
                    continue
                raise

        # Post final result
        stop_heartbeat.set()
        _write_announcement({
            "id": task_id,
            "type": "queue_progress",
            "message": result or "_(task completed with no output)_",
            "created_at": _now_iso(),
            "final": True,
        })
        logger.info("Offloaded task %s completed successfully", task_id)

    except AutomationError as exc:
        stop_heartbeat.set()
        err_str = str(exc)
        logger.error(
            "Offloaded task %s failed after %d attempt(s): %s",
            task_id, max_attempts, err_str,
        )
        # Categorize the error for the user
        if "timed out" in err_str.lower():
            user_msg = "The request timed out — the AI took too long to respond. Try a simpler request or try again later."
        elif "empty response" in err_str.lower():
            user_msg = "The AI returned an empty response after retrying. This usually means the model is overloaded — please try again in a minute."
        elif "not found" in err_str.lower():
            user_msg = "The AI backend is not available right now. Please try again later."
        elif "exit code" in err_str.lower():
            user_msg = f"The AI backend encountered an error: {err_str[:300]}"
        else:
            user_msg = f"Background task failed: {err_str[:300]}"
        _write_announcement({
            "id": task_id,
            "type": "queue_progress",
            "message": f"⚠️ {user_msg}",
            "created_at": _now_iso(),
            "final": True,
        })

    except Exception as exc:
        stop_heartbeat.set()
        logger.exception("Offloaded task %s failed with unexpected error", task_id)
        _write_announcement({
            "id": task_id,
            "type": "queue_progress",
            "message": f"⚠️ An unexpected error occurred: {type(exc).__name__}: {str(exc)[:200]}",
            "created_at": _now_iso(),
            "final": True,
        })


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"
