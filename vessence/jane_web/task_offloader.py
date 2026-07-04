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


class _TaskProgressHeartbeat:
    def __init__(
        self,
        task_id: str,
        *,
        interval: float = _PROGRESS_INTERVAL,
        write_progress_fn=None,
        heartbeat_message_fn=_heartbeat_progress_message,
        thread_factory=threading.Thread,
    ) -> None:
        self._task_id = task_id
        self._interval = interval
        self._write_progress_fn = write_progress_fn or _write_progress_announcement
        self._heartbeat_message_fn = heartbeat_message_fn
        self._last_delta = ""
        self._delta_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = thread_factory(target=self._loop, daemon=True)

    def on_progress(self, chunk: str) -> None:
        with self._delta_lock:
            self._last_delta = chunk

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _latest_message(self) -> str | None:
        with self._delta_lock:
            return self._heartbeat_message_fn(self._last_delta)

    def _loop(self) -> None:
        while not self._stop_event.wait(self._interval):
            heartbeat_message = self._latest_message()
            if heartbeat_message:
                self._write_progress_fn(self._task_id, heartbeat_message)


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


def _load_offload_history(session_id: str, task_id: str) -> list[dict]:
    try:
        from jane_web.jane_proxy import _get_session
        from vault_web.auth import get_session_user
        from jane_web.main import _default_user_id
        offload_user_id = get_session_user(session_id) or _default_user_id()
        state = _get_session(offload_user_id, session_id)
        return list(state.history) if state and state.history else []
    except Exception as exc:
        logger.warning("Could not load session history for offloaded task %s: %s", task_id, exc)
        return []


def _task_prompt_context(
    message: str,
    history: list[dict],
    task_id: str,
    *,
    build_context_fn,
) -> tuple[str, str]:
    system_prompt = ""
    prompt_text = message
    try:
        ctx = build_context_fn(message, history)
        # Use the transcript (Recent Conversation + User: message) as the
        # prompt so the model sees Jane's previous turns. The offloader
        # previously passed just `message`, which made pronouns like "this"
        # or "it" have no antecedent.
        prompt_text, system_prompt = _automation_prompt_context(message, ctx)
    except Exception:
        logger.warning("Context build failed for offloaded task %s, running without context", task_id)
    return prompt_text, system_prompt


def _run_automation_with_retries(
    task_id: str,
    prompt_text: str,
    system_prompt: str,
    on_progress,
    *,
    runner,
    automation_error_cls,
    max_attempts: int = 2,
    sleep_fn=time.sleep,
    write_progress_fn=_write_progress_announcement,
) -> str:
    for attempt in range(1, max_attempts + 1):
        try:
            return runner(
                prompt_text,
                system_prompt=system_prompt,
                workdir=VESSENCE_HOME,
                on_progress=on_progress,
            )
        except automation_error_cls as exc:
            is_empty_response = "empty response" in str(exc).lower()
            logger.warning(
                "Offloaded task %s attempt %d/%d failed: %s",
                task_id, attempt, max_attempts, exc,
            )
            if attempt < max_attempts and is_empty_response:
                write_progress_fn(task_id, _empty_response_retry_message())
                sleep_fn(2)
                continue
            raise
    return ""


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

    heartbeat = _TaskProgressHeartbeat(task_id)
    heartbeat.start()

    max_attempts = 2
    try:
        # Build context for the automation run.
        # Pull the session's conversation history so the offloaded task can
        # resolve pronouns like "this", "it", "that" back to Jane's previous
        # turns. Without this, messages like "please implement this" have
        # no antecedent and Jane responds "I don't know what you're referring to".
        history = _load_offload_history(session_id, task_id)
        prompt_text, system_prompt = _task_prompt_context(
            message,
            history,
            task_id,
            build_context_fn=build_jane_context,
        )

        result = _run_automation_with_retries(
            task_id,
            prompt_text,
            system_prompt,
            heartbeat.on_progress,
            runner=run_automation_prompt,
            automation_error_cls=AutomationError,
            max_attempts=max_attempts,
        )

        # Post final result
        heartbeat.stop()
        _write_progress_announcement(task_id, _final_result_message(result), final=True)
        logger.info("Offloaded task %s completed successfully", task_id)

    except AutomationError as exc:
        heartbeat.stop()
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
        heartbeat.stop()
        logger.exception("Offloaded task %s failed with unexpected error", task_id)
        _write_progress_announcement(
            task_id,
            _unexpected_error_announcement_message(exc),
            final=True,
        )
