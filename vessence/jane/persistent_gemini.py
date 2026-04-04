import asyncio
import contextlib
import os
import pty
import re
import shutil
import termios
import time
from dataclasses import dataclass
from typing import Callable


ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
PROMPT_PATTERNS = [
    "Type your message or @path/to/file",
]
NOISE_INDICATORS = [
    "Waiting for auth...",
    "Gemini CLI update available!",
    "Automatic update failed",
    "Ready (user)",
    "Logged in with Google",
    "screen reader-friendly view",
    "YOLO mode",
    "~ no sandbox",
    "Logging in...",
    "Logged in.",
    "Updated successfully",
    "update manually",
]


@dataclass
class _PendingTurn:
    emitted_len: int
    future: asyncio.Future
    on_delta: Callable[[str], None] | None


class TurnInterruptedError(RuntimeError):
    def __init__(self, message: str, emitted_len: int = 0):
        super().__init__(message)
        self.emitted_len = emitted_len


class GeminiPersistentSession:
    def __init__(self, session_id: str, cwd: str):
        self.session_id = session_id
        self.cwd = cwd
        self.process: asyncio.subprocess.Process | None = None
        self.master_fd: int | None = None
        self.reader_task: asyncio.Task | None = None
        self.ready_event = asyncio.Event()
        self.request_lock = asyncio.Lock()
        self.state_lock = asyncio.Lock()
        self.pending_turn: _PendingTurn | None = None
        self.pending_text = ""
        self.startup_buffer = ""
        self.exiting = False
        self.max_prompt_len = max(len(p) for p in PROMPT_PATTERNS)
        self.start_failure: RuntimeError | None = None
        self._last_activity: float = time.time()

    async def ensure_started(self) -> None:
        async with self.state_lock:
            if self.process and self.process.returncode is None and self.reader_task and not self.reader_task.done():
                return
            await self._spawn_locked()
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=90.0)
        except asyncio.TimeoutError as exc:
            async with self.state_lock:
                await self._close_locked()
            raise RuntimeError("Persistent Gemini did not become ready within 90s") from exc
        if self.start_failure is not None:
            error = self.start_failure
            async with self.state_lock:
                await self._close_locked()
            raise error

    async def _spawn_locked(self) -> None:
        await self._close_locked()
        gemini_path = shutil.which("gemini")
        if not gemini_path:
            raise RuntimeError("gemini CLI not found in PATH")

        master_fd, slave_fd = pty.openpty()
        try:
            attr = termios.tcgetattr(slave_fd)
            attr[3] = attr[3] & ~termios.ECHO
            termios.tcsetattr(slave_fd, termios.TCSANOW, attr)
        except Exception:
            pass

        os.set_blocking(master_fd, False)
        self.ready_event.clear()
        self.pending_turn = None
        self.pending_text = ""
        self.startup_buffer = ""
        self.start_failure = None

        # Load API key from runtime .env if not already in environment
        # (onboarding may have written it after the container started)
        # Gemini CLI checks GEMINI_API_KEY first, then GOOGLE_API_KEY
        from jane.brain_adapters import _load_runtime_env_keys
        _load_runtime_env_keys(("GOOGLE_API_KEY", "GEMINI_API_KEY"))

        try:
            self.process = await asyncio.create_subprocess_exec(
                "gemini",
                "--approval-mode=yolo",
                "--output-format",
                "text",
                "--screen-reader",
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.cwd,
                start_new_session=True,  # own process group for clean shutdown
            )
        except Exception:
            os.close(slave_fd)
            os.close(master_fd)
            raise
        else:
            os.close(slave_fd)
            self.master_fd = master_fd
            self.reader_task = asyncio.create_task(self._read_loop())

    async def _close_locked(self) -> None:
        self.ready_event.clear()
        pending = self.pending_turn
        self.pending_turn = None
        if pending and not pending.future.done():
            pending.future.set_exception(
                TurnInterruptedError("Gemini persistent session restarted", emitted_len=pending.emitted_len)
            )
        self.start_failure = None

        proc = self.process
        self.process = None
        fd = self.master_fd
        self.master_fd = None
        reader_task = self.reader_task
        self.reader_task = None

        if reader_task and not reader_task.done():
            reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader_task

        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass

    async def shutdown(self) -> None:
        self.exiting = True
        async with self.state_lock:
            await self._close_locked()

    async def run_turn(self, prompt_text: str, on_delta=None, timeout_seconds: float = 180.0) -> str:
        self._last_activity = time.time()
        for attempt in range(2):
            try:
                return await self._run_turn_once(prompt_text, on_delta=on_delta, timeout_seconds=timeout_seconds)
            except TurnInterruptedError as exc:
                if attempt == 0 and exc.emitted_len == 0:
                    async with self.state_lock:
                        await self._spawn_locked()
                    continue
                raise RuntimeError(str(exc)) from exc
            except RuntimeError as exc:
                if attempt == 0 and "Persistent Gemini session is not attached to a PTY" in str(exc):
                    async with self.state_lock:
                        await self._spawn_locked()
                    continue
                raise
        raise RuntimeError("Persistent Gemini could not recover from a transient session failure")

    async def _run_turn_once(self, prompt_text: str, on_delta=None, timeout_seconds: float = 180.0) -> str:
        await self.ensure_started()
        async with self.request_lock:
            if not self.process or self.process.returncode is not None:
                await self.ensure_started()

            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self.pending_turn = _PendingTurn(emitted_len=0, future=future, on_delta=on_delta)
            self.pending_text = ""

            try:
                if self.master_fd is None:
                    raise RuntimeError("Persistent Gemini session is not attached to a PTY")
                os.write(self.master_fd, (prompt_text + "\n").encode())
            except Exception:
                async with self.state_lock:
                    await self._spawn_locked()
                raise

            try:
                response = await asyncio.wait_for(future, timeout=timeout_seconds)
                return response
            except asyncio.TimeoutError:
                async with self.state_lock:
                    await self._spawn_locked()
                raise RuntimeError(f"Persistent Gemini timed out after {int(timeout_seconds)}s")
            finally:
                self.pending_turn = None
                self.pending_text = ""

    def _clean_text(self, text: str) -> str:
        text = ANSI_ESCAPE_RE.sub("", text)
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _find_prompt(self, text: str) -> tuple[int, str] | tuple[None, None]:
        for pattern in PROMPT_PATTERNS:
            idx = text.find(pattern)
            if idx != -1:
                return idx, pattern
        return None, None

    def _is_meaningful(self, text: str) -> bool:
        stripped = text.strip()
        if len(stripped) <= 5:
            return False
        for indicator in NOISE_INDICATORS:
            if indicator in stripped and len(stripped) < len(indicator) + 20:
                return False
        return True

    def _emit_safe_delta(self) -> None:
        pending = self.pending_turn
        if not pending or not pending.on_delta:
            return
        safe_end = len(self.pending_text) - self.max_prompt_len
        if safe_end <= pending.emitted_len:
            return
        delta = self.pending_text[pending.emitted_len:safe_end]
        if delta:
            pending.emitted_len = safe_end
            pending.on_delta(delta)

    def _finish_turn_if_prompt_seen(self) -> bool:
        pending = self.pending_turn
        if not pending:
            return False
        prompt_idx, _ = self._find_prompt(self.pending_text)
        if prompt_idx is None:
            return False

        final_text = self.pending_text[:prompt_idx].strip()
        remainder = self.pending_text[prompt_idx + self.max_prompt_len:]
        delta = final_text[pending.emitted_len:]
        if delta and pending.on_delta:
            pending.on_delta(delta)
        if not pending.future.done():
            pending.future.set_result(final_text)
        self.pending_text = remainder
        return True

    async def _read_loop(self) -> None:
        while not self.exiting:
            if self.master_fd is None:
                await asyncio.sleep(0.05)
                continue

            try:
                try:
                    data_bytes = os.read(self.master_fd, 4096)
                except (BlockingIOError, InterruptedError):
                    data_bytes = None
                if not data_bytes:
                    if self.process and self.process.returncode is not None:
                        if not self.ready_event.is_set():
                            snippet = self.startup_buffer.strip() or f"Gemini exited with code {self.process.returncode}"
                            self.start_failure = RuntimeError(f"Persistent Gemini failed during startup: {snippet[:300]}")
                            self.ready_event.set()
                        break
                    await asyncio.sleep(0.05)
                    continue
            except OSError:
                if self.process and self.process.returncode is not None:
                    if not self.ready_event.is_set():
                        snippet = self.startup_buffer.strip() or f"Gemini exited with code {self.process.returncode}"
                        self.start_failure = RuntimeError(f"Persistent Gemini failed during startup: {snippet[:300]}")
                        self.ready_event.set()
                    break
                await asyncio.sleep(0.1)
                continue

            text = self._clean_text(data_bytes.decode(errors="ignore"))
            if not text:
                continue

            if not self.ready_event.is_set():
                self.startup_buffer += text
                import logging as _logging
                _log = _logging.getLogger("jane.persistent_gemini")
                if len(self.startup_buffer) % 200 < len(text):  # Log periodically
                    _log.info("Gemini startup buffer (%d chars): ...%s",
                              len(self.startup_buffer),
                              repr(self.startup_buffer[-100:]))
                prompt_idx, pattern = self._find_prompt(self.startup_buffer)
                if prompt_idx is not None:
                    _log.info("Gemini ready prompt found at index %d in %d chars", prompt_idx, len(self.startup_buffer))
                    self.ready_event.set()
                    self.startup_buffer = self.startup_buffer[prompt_idx + len(pattern):]
                    self.start_failure = None
                elif self.process and self.process.returncode is not None:
                    snippet = self.startup_buffer.strip() or f"Gemini exited with code {self.process.returncode}"
                    self.start_failure = RuntimeError(f"Persistent Gemini failed during startup: {snippet[:300]}")
                    self.ready_event.set()
                continue

            if not self.pending_turn:
                if self.process and self.process.returncode is not None:
                    return
                continue

            self.pending_text += text
            if self._finish_turn_if_prompt_seen():
                continue

            self._emit_safe_delta()

        if self.pending_turn and not self.pending_turn.future.done():
            self.pending_turn.future.set_exception(
                TurnInterruptedError("Persistent Gemini session stopped", emitted_len=self.pending_turn.emitted_len)
            )


class GeminiPersistentManager:
    _MAX_SESSIONS = 20  # hard cap on concurrent sessions to prevent memory growth
    _STALE_SESSION_SECS = 1800  # 30 minutes idle

    def __init__(self, cwd: str):
        self.cwd = cwd
        self._sessions: dict[str, GeminiPersistentSession] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> GeminiPersistentSession:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                # Evict oldest session if at capacity
                if len(self._sessions) >= self._MAX_SESSIONS:
                    await self._evict_oldest_locked()
                session = GeminiPersistentSession(session_id=session_id, cwd=self.cwd)
                self._sessions[session_id] = session
            return session

    async def shutdown(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            await session.shutdown()

    # Alias for consistency with ClaudePersistentManager
    async def end(self, session_id: str) -> None:
        await self.shutdown(session_id)

    async def reap_stale_sessions(self) -> int:
        """Kill sessions unused for >30 minutes. Returns count of reaped sessions."""
        now = time.time()
        reaped = 0
        async with self._lock:
            stale_ids = [
                sid for sid, sess in self._sessions.items()
                if hasattr(sess, '_last_activity') and now - getattr(sess, '_last_activity', now) > self._STALE_SESSION_SECS
            ]
            for sid in stale_ids:
                session = self._sessions.pop(sid, None)
                if session:
                    try:
                        await session.shutdown()
                    except Exception:
                        pass
                    reaped += 1
        return reaped

    async def _evict_oldest_locked(self) -> None:
        """Evict the least-recently-used session when at capacity. Must hold _lock."""
        if not self._sessions:
            return
        oldest_id = min(
            self._sessions,
            key=lambda sid: getattr(self._sessions[sid], '_last_activity', 0),
        )
        session = self._sessions.pop(oldest_id, None)
        if session:
            try:
                await session.shutdown()
            except Exception:
                pass


_manager: GeminiPersistentManager | None = None


def get_gemini_persistent_manager(cwd: str) -> GeminiPersistentManager:
    global _manager
    if _manager is None:
        _manager = GeminiPersistentManager(cwd=cwd)
    return _manager
