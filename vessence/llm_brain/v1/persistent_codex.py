"""Persistent Codex CLI sessions via `codex exec --json` + `codex exec resume --json`.

This manager is intentionally separate from persistent_claude.py so Codex can
have provider-specific streaming behavior without affecting Claude's existing
path.
"""
import asyncio
import json
import logging
import os
import shlex
import shutil
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger("jane.persistent_codex")


def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


@dataclass
class CodexPersistentSession:
    session_id: str
    codex_thread_id: str | None = None
    last_used: float = field(default_factory=time.time)
    turn_count: int = 0

    def is_fresh(self) -> bool:
        return self.codex_thread_id is None


class CodexPersistentManager:
    _STALE_SESSION_SECS = 1800
    _MAX_SESSIONS = 20

    def __init__(self):
        self._sessions: dict[str, CodexPersistentSession] = {}
        self._lock = asyncio.Lock()
        self._codex_bin = os.environ.get("CODEX_BIN", shutil.which("codex") or "codex")
        self._active_procs: dict[str, asyncio.subprocess.Process] = {}
        self._workdir = os.environ.get("VESSENCE_HOME", str(Path.home() / "ambient" / "vessence"))

    async def get(self, session_id: str) -> CodexPersistentSession:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                if len(self._sessions) >= self._MAX_SESSIONS:
                    oldest_id = min(self._sessions, key=lambda sid: self._sessions[sid].last_used)
                    self._sessions.pop(oldest_id, None)
                    proc = self._active_procs.pop(oldest_id, None)
                    if proc and proc.returncode is None:
                        _kill_process_tree(proc)
                    logger.info("[%s] Evicted oldest Codex session to stay under %d cap",
                                oldest_id[:12], self._MAX_SESSIONS)
                session = CodexPersistentSession(session_id=session_id)
                self._sessions[session_id] = session
            session.last_used = time.time()
            return session

    async def end(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
            proc = self._active_procs.pop(session_id, None)
            if proc and proc.returncode is None:
                _kill_process_tree(proc)

    async def run_turn(
        self,
        session_id: str,
        prompt_text: str,
        on_delta: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_thought: Callable[[str], None] | None = None,
        on_tool_use: Callable[[str], None] | None = None,
        on_tool_result: Callable[[str], None] | None = None,
        timeout_seconds: float = 300.0,
        model: str | None = None,
        yolo: bool = False,
    ) -> str:
        session = await self.get(session_id)
        cmd = self._build_cmd(session, prompt_text, model=model, yolo=yolo)

        logger.info(
            "[%s] Running Codex turn %d (thread=%s, prompt_len=%d)",
            session_id[:12],
            session.turn_count + 1,
            session.codex_thread_id or "new",
            len(prompt_text),
        )

        response_text, thread_id = await self._execute_streaming(
            cmd,
            on_delta=on_delta,
            on_status=on_status,
            on_thought=on_thought,
            on_tool_use=on_tool_use,
            on_tool_result=on_tool_result,
            timeout_seconds=timeout_seconds,
            session_id=session_id,
        )

        if thread_id:
            session.codex_thread_id = thread_id
        session.turn_count += 1
        session.last_used = time.time()

        logger.info(
            "[%s] Codex turn %d complete (thread=%s, response_len=%d)",
            session_id[:12],
            session.turn_count,
            session.codex_thread_id or "unknown",
            len(response_text),
        )
        return response_text

    def _build_cmd(
        self,
        session: CodexPersistentSession,
        prompt_text: str,
        *,
        model: str | None,
        yolo: bool,
    ) -> list[str]:
        base = [self._codex_bin, "exec"]
        if session.codex_thread_id:
            base.extend(["resume", session.codex_thread_id])
        base.extend(["--json", "--skip-git-repo-check"])
        if yolo:
            base.append("--dangerously-bypass-approvals-and-sandbox")
        if model:
            base.extend(["--model", model])
        base.append(prompt_text)
        return base

    async def _execute_streaming(
        self,
        cmd: list[str],
        *,
        on_delta: Callable[[str], None] | None,
        on_status: Callable[[str], None] | None,
        on_thought: Callable[[str], None] | None,
        on_tool_use: Callable[[str], None] | None,
        on_tool_result: Callable[[str], None] | None,
        timeout_seconds: float,
        session_id: str,
    ) -> tuple[str, str | None]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._workdir,
            start_new_session=True,
        )
        self._active_procs[session_id] = proc

        final_response = ""
        thread_id = None
        pending_agent_message: str | None = None
        last_activity = time.time()
        codex_error: str | None = None

        try:
            while True:
                try:
                    raw = await asyncio.wait_for(
                        proc.stdout.readline(),
                        timeout=min(60.0, timeout_seconds - (time.time() - last_activity)),
                    )
                except asyncio.TimeoutError:
                    elapsed = time.time() - last_activity
                    if elapsed >= timeout_seconds:
                        _kill_process_tree(proc)
                        raise RuntimeError(f"Codex CLI timed out after {int(timeout_seconds)}s")
                    continue

                if not raw:
                    break

                last_activity = time.time()
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "")

                if event_type == "thread.started":
                    thread_id = event.get("thread_id") or thread_id
                    continue

                if event_type == "error":
                    message = (event.get("message") or "").strip()
                    if message:
                        codex_error = self._normalize_error_message(message)
                    continue

                if event_type == "turn.started":
                    if on_status:
                        on_status("Jane is thinking...")
                    continue

                if event_type == "item.started":
                    item = event.get("item") or {}
                    item_type = item.get("type", "")
                    if item_type == "command_execution":
                        self._flush_pending_thought(pending_agent_message, on_thought, on_status)
                        pending_agent_message = None
                        command = item.get("command", "")
                        label = f"Running command: {self._format_command(command)}"
                        if on_tool_use:
                            on_tool_use(label)
                        elif on_status:
                            on_status(label)
                    continue

                if event_type == "item.completed":
                    item = event.get("item") or {}
                    item_type = item.get("type", "")

                    if item_type == "agent_message":
                        text = (item.get("text") or "").strip()
                        if text:
                            if pending_agent_message and pending_agent_message != text:
                                self._flush_pending_thought(pending_agent_message, on_thought, on_status)
                            pending_agent_message = text
                        continue

                    if item_type == "command_execution":
                        self._flush_pending_thought(pending_agent_message, on_thought, on_status)
                        pending_agent_message = None
                        command = item.get("command", "")
                        exit_code = item.get("exit_code")
                        output = (item.get("aggregated_output") or "").strip()
                        detail = self._format_tool_result(command, exit_code, output)
                        if on_tool_result:
                            on_tool_result(detail)
                        elif on_status:
                            on_status(detail)
                        continue

                    if item_type in {"reasoning", "thinking", "analysis"}:
                        text = self._extract_item_text(item)
                        if text:
                            if on_thought:
                                on_thought(text)
                            elif on_status:
                                on_status(text[:300])
                        continue

                if event_type == "item.failed":
                    item = event.get("item") or {}
                    item_type = item.get("type", "")
                    if item_type == "command_execution":
                        self._flush_pending_thought(pending_agent_message, on_thought, on_status)
                        pending_agent_message = None
                        command = item.get("command", "")
                        message = self._extract_item_text(item) or "Command failed."
                        detail = f"{self._format_command(command)} failed\n↳ {message[:300]}"
                        if on_tool_result:
                            on_tool_result(detail)
                        elif on_status:
                            on_status(detail)
                    continue

                if event_type == "turn.completed":
                    if pending_agent_message:
                        final_response = pending_agent_message
                        if on_delta:
                            on_delta(final_response)
                        pending_agent_message = None
                    break

                if event_type == "turn.failed":
                    error = event.get("error") or {}
                    if isinstance(error, dict):
                        message = (error.get("message") or "").strip()
                        if message:
                            codex_error = self._normalize_error_message(message)
                    continue

            await proc.wait()

            if proc.returncode != 0 and not final_response:
                stderr = await proc.stderr.read()
                err_msg = stderr.decode(errors="ignore").strip()[:500]
                detail = codex_error or err_msg or "Codex exited without returning a response."
                raise RuntimeError(f"Codex CLI exited with code {proc.returncode}: {detail}")
        except Exception:
            if proc.returncode is None:
                _kill_process_tree(proc)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3)
                except asyncio.TimeoutError:
                    pass
            raise
        finally:
            self._active_procs.pop(session_id, None)

        return final_response, thread_id

    @staticmethod
    def _format_command(command: str) -> str:
        command = (command or "").strip()
        if not command:
            return "Running command"
        try:
            parts = shlex.split(command)
        except ValueError:
            return command[:160]
        if len(parts) >= 3 and parts[:2] == ["/bin/bash", "-lc"]:
            return parts[2][:160]
        return command[:160]

    @staticmethod
    def _flush_pending_thought(
        pending_agent_message: str | None,
        on_thought: Callable[[str], None] | None,
        on_status: Callable[[str], None] | None,
    ) -> None:
        if not pending_agent_message:
            return
        preview = pending_agent_message[:300]
        if on_thought:
            on_thought(preview)
        elif on_status:
            on_status(preview)

    @staticmethod
    def _extract_item_text(item: dict) -> str:
        for key in ("text", "summary", "message", "error", "stderr", "output"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                elif isinstance(block, str) and block.strip():
                    parts.append(block.strip())
            if parts:
                return "\n".join(parts)
        return ""

    def _format_tool_result(self, command: str, exit_code: int | None, output: str) -> str:
        detail = self._format_command(command)
        if exit_code is not None:
            detail += f" (exit {exit_code})"
        if output:
            preview = output[:300]
            if len(output) > 300:
                preview += f" ... ({len(output)} chars total)"
            return f"{detail}\n↳ {preview}"
        return detail

    @staticmethod
    def _normalize_error_message(message: str) -> str:
        message = (message or "").strip()
        if not message:
            return ""
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict):
                detail = parsed.get("detail")
                if isinstance(detail, str) and detail.strip():
                    return detail.strip()
        except json.JSONDecodeError:
            pass
        return message


_manager: CodexPersistentManager | None = None


def get_codex_persistent_manager() -> CodexPersistentManager:
    global _manager
    if _manager is None:
        _manager = CodexPersistentManager()
    return _manager
