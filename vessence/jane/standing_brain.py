"""standing_brain.py — Standing Brain: a single long-lived CLI process with stream-json I/O.

Spawns one CLI process for the configured provider. The process stays alive and
accepts messages via stdin stream-json, eliminating subprocess spawn overhead
per message.

Usage:
    manager = StandingBrainManager()
    await manager.start()
    async for chunk in manager.send(system_prompt, message):
        print(chunk, end="")
    await manager.shutdown()
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

logger = logging.getLogger("jane.standing_brain")

# ── Configuration ────────────────────────────────────────────────────────────

_PROVIDER = os.environ.get("JANE_BRAIN", "claude").lower()

# Single model per provider — read from env with sensible defaults.
_DEFAULT_MODELS = {
    "claude": "claude-opus-4-6",
    "gemini": "gemini-2.5-pro",
    "openai": "o3",
}

_ENV_VAR_FOR_MODEL = {
    "claude": "JANE_MODEL_CLAUDE",
    "gemini": "JANE_MODEL_GEMINI",
    "openai": "JANE_MODEL_OPENAI",
}


def _get_model() -> str:
    """Return the single model for the current provider, reading from env at call time."""
    env_var = _ENV_VAR_FOR_MODEL.get(_PROVIDER, "JANE_MODEL_CLAUDE")
    # Also check legacy env vars for backwards compatibility
    legacy_var = f"BRAIN_HEAVY_{_PROVIDER.upper()}"
    return (
        os.environ.get(env_var)
        or os.environ.get(legacy_var)
        or _DEFAULT_MODELS.get(_PROVIDER, "claude-opus-4-6")
    )


# How long to wait for a response before considering the brain stuck
RESPONSE_TIMEOUT_SECS = 300
# Max consecutive failures before giving up
MAX_FAILURES = 3
# Max turns before forcing a brain restart to refresh context
MAX_TURNS_BEFORE_REFRESH = 20
# CPU threshold (%) above which a brain is considered runaway
CPU_THRESHOLD_PERCENT = 15.0
# How long (seconds) a brain must exceed CPU threshold before being killed
CPU_HOT_DURATION_SECS = 3600  # 1 hour


def _log_crash(detail: str):
    """Log a crash alert to the Work Log (best-effort, never raises)."""
    try:
        from agent_skills.work_log_tools import log_activity
        log_activity(f"CRASH: {detail}", category="crash_alert")
    except Exception:
        logger.debug("Could not write crash alert to work log: %s", detail)


# ── Brain Process ────────────────────────────────────────────────────────────

@dataclass
class BrainProcess:
    """Represents the single standing CLI process."""
    model: str
    process: Optional[asyncio.subprocess.Process] = None
    session_id: Optional[str] = None
    turn_count: int = 0
    last_used: float = 0.0
    consecutive_failures: int = 0
    cpu_hot_since: float = 0.0  # timestamp when CPU usage first exceeded threshold (0 = not hot)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.returncode is None

    @property
    def idle_seconds(self) -> float:
        if self.last_used == 0:
            return 0
        return time.time() - self.last_used

    @property
    def cpu_percent(self) -> float:
        """Get current CPU usage of the brain process (0-100+). Returns 0 if unavailable."""
        if not self.alive or not self.process or not self.process.pid:
            return 0.0
        try:
            import psutil
            proc = psutil.Process(self.process.pid)
            return proc.cpu_percent(interval=0.1)
        except Exception:
            return 0.0


class StandingBrainManager:
    """Manages a single standing brain process."""

    def __init__(self):
        self._brain: Optional[BrainProcess] = None
        self._started = False
        self._reaper_task: Optional[asyncio.Task] = None

    @property
    def brain(self) -> Optional[BrainProcess]:
        """The single brain process (or None if not started)."""
        return self._brain

    async def start(self):
        """Start the brain process."""
        if self._started:
            return

        model = _get_model()
        self._brain = BrainProcess(model=model)
        try:
            await self._spawn(self._brain)
            logger.info("Standing brain started: provider=%s model=%s pid=%s",
                        _PROVIDER, model, self._brain.process.pid if self._brain.process else "?")
        except Exception as e:
            logger.error("Failed to start standing brain [%s]: %s", model, e)

        self._started = True
        self._reaper_task = asyncio.create_task(self._reap_loop())

    def _build_cmd(self, bp: BrainProcess) -> list[str]:
        """Build the CLI command for the current provider."""
        if _PROVIDER == "claude":
            cli_bin = os.environ.get("CLAUDE_BIN", shutil.which("claude") or "claude")
            cmd = [
                cli_bin, "--print", "--verbose",
                "--input-format", "stream-json",
                "--output-format", "stream-json",
                "--model", bp.model,
            ]
            # Web permission gate: use hook-based approval instead of skip-all
            hook_script = os.path.join(os.path.dirname(__file__), "hooks", "permission_gate.py")
            if os.environ.get("JANE_WEB_PERMISSIONS", "0") == "1" and os.path.isfile(hook_script):
                python_bin = os.environ.get("PYTHON_BIN", sys.executable)
                cmd.append("--dangerously-skip-permissions")
                import json as _json
                hook_settings = _json.dumps({"hooks": {"PreToolUse": [{
                    "matcher": "Bash|Write|Edit|NotebookEdit",
                    "hooks": [{"type": "command",
                               "command": f"{python_bin} {hook_script}",
                               "timeout": 300}],
                }]}})
                cmd.extend(["--settings", hook_settings])
            else:
                cmd.append("--dangerously-skip-permissions")
            return cmd
        elif _PROVIDER == "gemini":
            cli_bin = os.environ.get("GEMINI_BIN", shutil.which("gemini") or "/usr/local/bin/gemini")
            return [
                cli_bin,
                "--approval-mode", "yolo",
                "--output-format", "text",
                "--model", bp.model,
            ]
        elif _PROVIDER == "openai":
            cli_bin = os.environ.get("CODEX_BIN", shutil.which("codex") or "codex")
            return [
                cli_bin, "exec",
                "--model", bp.model,
                "--approval-mode", "full-auto",
            ]
        else:
            raise RuntimeError(f"Unknown provider: {_PROVIDER}")

    async def _spawn(self, bp: BrainProcess):
        """Spawn a new CLI process for the brain."""
        cmd = self._build_cmd(bp)

        bp.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence")),
            start_new_session=True,
        )
        bp.session_id = None
        bp.turn_count = 0
        bp.last_used = time.time()
        bp.consecutive_failures = 0
        bp.cpu_hot_since = 0.0

        if _PROVIDER == "claude":
            try:
                init_line = await asyncio.wait_for(bp.process.stdout.readline(), timeout=30)
                if init_line:
                    init_data = json.loads(init_line)
                    if init_data.get("type") == "system" and init_data.get("subtype") == "init":
                        bp.session_id = init_data.get("session_id")
                        logger.info("Brain [%s] initialized: session=%s", bp.model, bp.session_id)
            except (asyncio.TimeoutError, json.JSONDecodeError) as e:
                logger.warning("Brain [%s] init timeout/error: %s", bp.model, e)
        else:
            await asyncio.sleep(2)
            if bp.alive:
                bp.session_id = f"{_PROVIDER}_default"
                logger.info("Brain [%s] ready (pid=%s)", bp.model, bp.process.pid)
            else:
                logger.warning("Brain [%s] failed to start", bp.model)

    async def send(
        self,
        message: str,
        system_prompt: str = "",
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Send a message to the standing brain and yield tagged response chunks.

        Yields tuples of (event_type, text):
            ("delta", text)   — final response text
            ("thought", text) — intermediate thinking / tool-use events
        """
        bp = self._brain
        if not bp:
            raise RuntimeError("Standing brain not started")

        async with bp._lock:
            if not bp.alive or bp.consecutive_failures >= MAX_FAILURES or bp.turn_count >= MAX_TURNS_BEFORE_REFRESH:
                reason = ("dead" if not bp.alive
                          else f"hit {MAX_FAILURES} consecutive failures" if bp.consecutive_failures >= MAX_FAILURES
                          else f"hit {MAX_TURNS_BEFORE_REFRESH} turns, refreshing context")
                logger.info("Brain [%s] is %s, restarting...", bp.model, reason)
                if not bp.alive or bp.consecutive_failures >= MAX_FAILURES:
                    _log_crash(f"Standing Brain [{bp.model}] — {reason}")
                if bp.alive:
                    await self._kill(bp)
                await self._spawn(bp)
                if not bp.alive:
                    _log_crash(f"Standing Brain [{bp.model}] — restart failed")
                    raise RuntimeError(f"Brain {bp.model} failed to restart")

            # Build the prompt — include system prompt on first turn only
            if bp.turn_count == 0 and system_prompt:
                full_message = f"{system_prompt}\n\nUser: {message}\nJane:"
            else:
                full_message = message

            # Send message via stdin — format depends on provider
            if _PROVIDER == "claude":
                input_msg = json.dumps({
                    "type": "user",
                    "message": {"role": "user", "content": full_message},
                    "session_id": bp.session_id or "default",
                    "parent_tool_use_id": None,
                }) + "\n"
            else:
                input_msg = full_message + "\n"

            try:
                bp.process.stdin.write(input_msg.encode())
                await bp.process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as e:
                logger.error("Brain [%s] stdin write failed: %s", bp.model, e)
                bp.consecutive_failures += 1
                raise RuntimeError(f"Brain {bp.model} pipe broken") from e

            response_text = ""
            start = time.perf_counter()
            got_result = False

            try:
                if _PROVIDER == "claude":
                    async for event_type, chunk in self._read_claude_response(bp):
                        if event_type == "delta":
                            response_text += chunk
                        got_result = True
                        yield (event_type, chunk)
                else:
                    async for chunk in self._read_text_response(bp):
                        response_text += chunk
                        got_result = True
                        yield ("delta", chunk)

            except asyncio.TimeoutError:
                logger.error("Brain [%s] response timeout after %ds", bp.model, RESPONSE_TIMEOUT_SECS)
                bp.consecutive_failures += 1
                raise RuntimeError(f"Brain {bp.model} response timeout")

            elapsed = int((time.perf_counter() - start) * 1000)
            bp.turn_count += 1
            bp.last_used = time.time()

            if got_result:
                bp.consecutive_failures = 0
                logger.info("Brain [%s] turn %d complete in %dms (%d chars)",
                            bp.model, bp.turn_count, elapsed, len(response_text))
            else:
                bp.consecutive_failures += 1
                logger.warning("Brain [%s] turn %d: no result event (process may have died)", bp.model, bp.turn_count)

    async def get_model(self) -> str:
        """Return the model name of the brain."""
        return self._brain.model if self._brain else "unknown"

    async def health_check(self) -> dict:
        """Return health status for the brain."""
        bp = self._brain
        if not bp:
            return {"alive": False, "model": "none", "turns": 0}
        return {
            "alive": bp.alive,
            "model": bp.model,
            "turns": bp.turn_count,
            "idle_secs": int(bp.idle_seconds),
            "pid": bp.process.pid if bp.process else None,
            "failures": bp.consecutive_failures,
        }

    async def _reap_loop(self):
        """Periodically check brain health: kill idle+high-CPU brain, restart if dead."""
        while True:
            await asyncio.sleep(60)
            bp = self._brain
            if not bp:
                continue
            if bp.alive:
                cpu = bp.cpu_percent
                idle = bp.idle_seconds
                is_idle = idle > 300
                if cpu > CPU_THRESHOLD_PERCENT and is_idle:
                    if bp.cpu_hot_since == 0.0:
                        bp.cpu_hot_since = time.time()
                        logger.info("Brain [%s] idle + CPU elevated (%.1f%%), monitoring...", bp.model, cpu)
                    elif time.time() - bp.cpu_hot_since > CPU_HOT_DURATION_SECS:
                        logger.warning("Brain [%s] idle + CPU above %.0f%% for over %ds, killing runaway",
                                       bp.model, CPU_THRESHOLD_PERCENT, CPU_HOT_DURATION_SECS)
                        _log_crash(f"Standing Brain [{bp.model}] — killed: idle + sustained high CPU ({cpu:.1f}%) over {CPU_HOT_DURATION_SECS}s")
                        await self._kill(bp)
                else:
                    if bp.cpu_hot_since > 0:
                        bp.cpu_hot_since = 0.0
            elif not bp.alive and bp.last_used > 0:
                logger.warning("Brain [%s] found dead (pid was %s), auto-restarting...",
                               bp.model, bp.process.pid if bp.process else "?")
                _log_crash(f"Standing Brain [{bp.model}] — found dead, auto-restarting")
                try:
                    await self._spawn(bp)
                    logger.info("Brain [%s] auto-restarted successfully (pid=%s)",
                                bp.model, bp.process.pid if bp.process else "?")
                except Exception as e:
                    logger.error("Brain [%s] auto-restart failed: %s", bp.model, e)
                    _log_crash(f"Standing Brain [{bp.model}] — auto-restart failed: {e}")

    async def _read_ndjson_line(self, bp: BrainProcess) -> bytes | None:
        """Read one complete NDJSON line from stdout using raw reads (no buffer limit)."""
        buf = bytearray()
        while True:
            chunk = await asyncio.wait_for(
                bp.process.stdout.read(65536),
                timeout=RESPONSE_TIMEOUT_SECS,
            )
            if not chunk:
                return bytes(buf) if buf else None
            buf.extend(chunk)
            idx = buf.find(b'\n')
            if idx >= 0:
                line = bytes(buf[:idx])
                remainder = bytes(buf[idx + 1:])
                if remainder:
                    bp._read_buffer = remainder
                return line

    async def _read_claude_line(self, bp: BrainProcess) -> bytes | None:
        """Read one NDJSON line, using any buffered remainder from previous read."""
        if hasattr(bp, '_read_buffer') and bp._read_buffer:
            buf = bytearray(bp._read_buffer)
            bp._read_buffer = b''
            idx = buf.find(b'\n')
            if idx >= 0:
                line = bytes(buf[:idx])
                bp._read_buffer = bytes(buf[idx + 1:])
                return line
            chunk = await asyncio.wait_for(
                bp.process.stdout.read(65536),
                timeout=RESPONSE_TIMEOUT_SECS,
            )
            if not chunk:
                return bytes(buf) if buf else None
            buf.extend(chunk)
            idx = buf.find(b'\n')
            if idx >= 0:
                line = bytes(buf[:idx])
                bp._read_buffer = bytes(buf[idx + 1:])
                return line
            bp._read_buffer = bytes(buf)
        return await self._read_ndjson_line(bp)

    async def _read_claude_response(self, bp: BrainProcess) -> AsyncGenerator[tuple[str, str], None]:
        """Read NDJSON stream events from Claude CLI stdout."""
        response_text = ""
        # Track which content blocks we've already processed to avoid
        # re-emitting thoughts/tool descriptions on every assistant event
        # (each assistant event contains ALL content blocks so far).
        _seen_block_count = 0
        while True:
            raw = await self._read_claude_line(bp)
            if not raw:
                break

            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == "assistant":
                msg = event.get("message", {})
                blocks = msg.get("content", [])
                # Only process new blocks we haven't seen yet
                new_blocks = blocks[_seen_block_count:]
                _seen_block_count = len(blocks)
                for block in new_blocks:
                    block_type = block.get("type", "")

                    if block_type == "thinking":
                        thinking_text = block.get("thinking", "")
                        if thinking_text:
                            # Yield all meaningful lines so the web shows
                            # the same intermediate reasoning the CLI prints.
                            for line in thinking_text.split("\n"):
                                line = line.strip()
                                if line and len(line) > 5:
                                    yield ("thought", line[:300])

                    elif block_type == "tool_use":
                        tool_name = block.get("name", "unknown")
                        tool_input = block.get("input", {})
                        if tool_name in ("Read", "read_file"):
                            desc = f"📖 Reading {tool_input.get('file_path', tool_input.get('path', ''))}"
                        elif tool_name in ("Edit", "edit_file"):
                            desc = f"✏️ Editing {tool_input.get('file_path', tool_input.get('path', ''))}"
                        elif tool_name in ("Write", "write_file"):
                            desc = f"📝 Writing {tool_input.get('file_path', tool_input.get('path', ''))}"
                        elif tool_name in ("Grep", "grep", "search"):
                            pattern = tool_input.get("pattern", tool_input.get("query", ""))
                            desc = f"🔍 Searching for \"{pattern[:80]}\""
                        elif tool_name in ("Glob", "glob"):
                            desc = f"📁 Finding files matching {tool_input.get('pattern', '')}"
                        elif tool_name in ("Bash", "bash"):
                            cmd = tool_input.get("command", "")
                            desc = f"⚡ Running: {cmd[:120]}"
                        elif tool_name == "Agent":
                            agent_desc = tool_input.get("description", tool_input.get("prompt", "")[:80])
                            desc = f"🤖 Spawning agent: {agent_desc}"
                        elif tool_name in ("WebSearch", "web_search"):
                            query = tool_input.get("query", "")
                            desc = f"🌐 Searching web: {query[:100]}"
                        elif tool_name in ("WebFetch", "web_fetch"):
                            url = tool_input.get("url", "")
                            desc = f"🌐 Fetching: {url[:100]}"
                        else:
                            desc = f"🔧 Using {tool_name}"
                        yield ("tool_use", desc)

                    elif block_type == "tool_result":
                        # Show tool results so the web mirrors CLI output
                        content = block.get("content", "")
                        if isinstance(content, list):
                            # Multi-part result — extract text parts
                            parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                            content = "\n".join(parts)
                        if isinstance(content, str) and content.strip():
                            # Truncate long results but show enough to be useful
                            preview = content.strip()[:500]
                            if len(content.strip()) > 500:
                                preview += f" … ({len(content.strip())} chars total)"
                            yield ("tool_result", f"↳ {preview}")

                    elif block_type == "text":
                        text = block.get("text", "")
                        if text and text != response_text:
                            new_text = text[len(response_text):]
                            if new_text:
                                response_text = text
                                yield ("delta", new_text)

            elif event_type == "result":
                result_text = event.get("result", "")
                if result_text and len(result_text) > len(response_text):
                    yield ("delta", result_text[len(response_text):])
                bp.session_id = event.get("session_id", bp.session_id)
                break

            elif event_type == "rate_limit_event":
                continue

    async def _read_text_response(self, bp: BrainProcess) -> AsyncGenerator[str, None]:
        """Read plain text from Gemini/OpenAI CLI stdout."""
        buffer = ""
        while True:
            try:
                line = await asyncio.wait_for(
                    bp.process.stdout.readline(),
                    timeout=3,
                )
                if not line:
                    break
                text = line.decode("utf-8", errors="replace")
                if text.strip() in (">", "❯", "$"):
                    break
                buffer += text
                yield text
            except asyncio.TimeoutError:
                break

    async def _kill(self, bp: BrainProcess):
        """Kill a brain process and its entire process group, then reset turn count."""
        if bp.process and bp.process.returncode is None:
            pid = bp.process.pid
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try:
                    bp.process.kill()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(bp.process.wait(), timeout=3)
            except (asyncio.TimeoutError, ProcessLookupError):
                pass
        bp.turn_count = 0

    async def shutdown(self):
        """Shutdown the brain process."""
        if self._reaper_task:
            self._reaper_task.cancel()
        if self._brain:
            await self._kill(self._brain)
            logger.info("Brain shut down")
        self._brain = None
        self._started = False


# ── Singleton manager ────────────────────────────────────────────────────────

_manager: Optional[StandingBrainManager] = None


def get_standing_brain_manager() -> StandingBrainManager:
    global _manager
    if _manager is None:
        _manager = StandingBrainManager()
    return _manager
