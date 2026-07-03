"""Background task offloader — runs big tasks async and posts progress via announcements."""

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
from jane_web.task_offloader_announcements import (
    append_task_progress_announcement as _append_task_progress_announcement,
)
from jane_web.task_offloader_context import (
    automation_prompt_context as _automation_prompt_context,
)
from jane_web.task_offloader_messages import (
    automation_error_announcement_message as _automation_error_announcement_message,
    empty_response_retry_message as _empty_response_retry_message,
    final_result_message as _final_result_message,
    heartbeat_progress_message as _heartbeat_progress_message,
    start_progress_message as _start_progress_message,
    truncate_text as _truncate,
    unexpected_error_announcement_message as _unexpected_error_announcement_message,
)

logger = logging.getLogger("jane.offloader")

ANNOUNCEMENTS_PATH = Path(VESSENCE_DATA_HOME) / "data" / "jane_announcements.jsonl"
# How often to emit a progress announcement while the task runs (seconds)
_PROGRESS_INTERVAL = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_progress_announcement(task_id: str, message: str, *, final: bool = False) -> None:
    _append_task_progress_announcement(
        ANNOUNCEMENTS_PATH,
        task_id,
        message,
        _now_iso(),
        final=final,
    )


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
    from context_builder.v1.context_builder import build_jane_context

    # Announce start
    _write_progress_announcement(task_id, _start_progress_message(message))

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
                heartbeat_message = _heartbeat_progress_message(last_delta)
            if heartbeat_message:
                _write_progress_announcement(task_id, heartbeat_message)

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
            from vault_web.auth import get_session_user
            from jane_web.main import _default_user_id
            _offload_user_id = get_session_user(session_id) or _default_user_id()
            state = _get_session(_offload_user_id, session_id)
            history = list(state.history) if state and state.history else []
        except Exception as exc:
            logger.warning("Could not load session history for offloaded task %s: %s", task_id, exc)

        system_prompt = ""
        prompt_text = message
        try:
            ctx = build_jane_context(message, history)
            # Use the transcript (Recent Conversation + User: message) as the
            # prompt so the model sees Jane's previous turns. The offloader
            # previously passed just `message`, which made pronouns like "this"
            # or "it" have no antecedent.
            prompt_text, system_prompt = _automation_prompt_context(message, ctx)
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
                    _write_progress_announcement(task_id, _empty_response_retry_message())
                    time.sleep(2)
                    continue
                raise

        # Post final result
        stop_heartbeat.set()
        _write_progress_announcement(task_id, _final_result_message(result), final=True)
        logger.info("Offloaded task %s completed successfully", task_id)

    except AutomationError as exc:
        stop_heartbeat.set()
        err_str = str(exc)
        logger.error(
            "Offloaded task %s failed after %d attempt(s): %s",
            task_id, max_attempts, err_str,
        )
        _write_progress_announcement(
            task_id,
            _automation_error_announcement_message(err_str),
            final=True,
        )

    except Exception as exc:
        stop_heartbeat.set()
        logger.exception("Offloaded task %s failed with unexpected error", task_id)
        _write_progress_announcement(
            task_id,
            _unexpected_error_announcement_message(exc),
            final=True,
        )
