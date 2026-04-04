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
from pathlib import Path
from typing import AsyncGenerator, Optional

logger = logging.getLogger("jane.standing_brain")

# ── Provider error detection ─────────────────────────────────────────────────

# Known patterns in stderr that indicate rate limit / billing / quota errors.
# Each provider maps to a list of (substring, category) tuples.
_STDERR_ERROR_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "claude": [
        ("rate_limit", "rate_limit"),
        ("overloaded", "overloaded"),
        ("billing", "billing"),
        ("insufficient_quota", "billing"),
        ("credit", "billing"),
        ("529", "overloaded"),
        ("Too many requests", "rate_limit"),
    ],
    "gemini": [
        ("quota", "rate_limit"),
        ("rate limit", "rate_limit"),
        ("429", "rate_limit"),
        ("billing", "billing"),
        ("RESOURCE_EXHAUSTED", "rate_limit"),
        ("Too many requests", "rate_limit"),
    ],
    "openai": [
        ("rate_limit", "rate_limit"),
        ("insufficient_quota", "billing"),
        ("billing", "billing"),
        ("429", "rate_limit"),
        ("Too many requests", "rate_limit"),
    ],
}

# All supported providers
ALL_PROVIDERS = ("claude", "gemini", "openai")


def _provider_uses_standing_process(provider: str) -> bool:
    """Return whether this provider supports the long-lived standing-brain CLI path."""
    return provider in {"claude", "gemini"}


def _classify_stderr_line(provider: str, line: str) -> tuple[str, str] | None:
    """Check if a stderr line matches a known error pattern.
    Returns (matched_substring, category) or None.
    """
    patterns = _STDERR_ERROR_PATTERNS.get(provider, [])
    line_lower = line.lower()
    for substring, category in patterns:
        if substring.lower() in line_lower:
            return (substring, category)
    return None


def _available_providers(current: str) -> list[str]:
    """Return providers the user can switch to (excluding the current one)."""
    return [p for p in ALL_PROVIDERS if p != current]


# ── Configuration ────────────────────────────────────────────────────────────

_PROVIDER = os.environ.get("JANE_BRAIN", "claude").lower()

# Single model per provider — read from env with sensible defaults.
_DEFAULT_MODELS = {
    "claude": "claude-opus-4-6",
    "gemini": "gemini-2.5-pro",
    "openai": "gpt-5.4",
}

_ENV_VAR_FOR_MODEL = {
    "claude": "JANE_MODEL_CLAUDE",
    "gemini": "JANE_MODEL_GEMINI",
    "openai": "JANE_MODEL_OPENAI",
}


def _configured_provider() -> str:
    """Return the provider from the current env file if available."""
    from jane.config import ENV_FILE_PATH

    env_path = Path(ENV_FILE_PATH) if ENV_FILE_PATH else None
    if env_path and env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "JANE_BRAIN":
                provider = value.strip().lower()
                if provider in ALL_PROVIDERS:
                    return provider

    provider = os.environ.get("JANE_BRAIN", _PROVIDER).lower()
    return provider if provider in ALL_PROVIDERS else _PROVIDER


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


# How long to wait for a response before considering the brain stuck.
# Claude Opus can think/use tools for extended periods — give it plenty of time.
RESPONSE_TIMEOUT_SECS = 900  # 15 minutes total
# Chunk read interval: wait this long per read attempt before retrying.
# Keeps the async loop responsive while allowing long brain computation.
_READ_CHUNK_TIMEOUT = 30  # seconds per read attempt
# Max consecutive failures before giving up
MAX_FAILURES = 3
# Max turns before forcing a brain restart to refresh context
MAX_TURNS_BEFORE_REFRESH = 1000
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
    _stderr_task: Optional[asyncio.Task] = field(default=None, repr=False)
    last_stderr_error: Optional[dict] = field(default=None, repr=False)  # most recent parsed error

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
        self._on_provider_error: Optional[callable] = None  # callback(error_dict)

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
        if _provider_uses_standing_process(_PROVIDER):
            try:
                await self._spawn(self._brain)
                logger.info("Standing brain started: provider=%s model=%s pid=%s",
                            _PROVIDER, model, self._brain.process.pid if self._brain.process else "?")
            except Exception as e:
                logger.error("Failed to start standing brain [%s]: %s", model, e)
        else:
            logger.info("Standing brain disabled for provider=%s model=%s", _PROVIDER, model)

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

        # Use /tmp as CWD to avoid picking up CLAUDE.md / .gemini/GEMINI.md
        # from the project directory.  CLAUDE.md contains hooks and rules
        # (e.g. read CODE_MAP.md first, run check_continuation.py) that cause
        # the CLI to do tool use instead of responding, leading to empty
        # responses after the 20-turn refresh.
        bp.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
            start_new_session=True,
        )
        bp.session_id = None
        bp.turn_count = 0
        bp.last_used = time.time()
        bp.consecutive_failures = 0
        bp.cpu_hot_since = 0.0

        # Start stderr reader background task
        bp._stderr_task = asyncio.create_task(self._read_stderr(bp))

        if _PROVIDER == "claude":
            try:
                # Newer Claude CLI builds often defer the stream-json init event
                # until the first user message arrives. Waiting 30s here makes
                # provider switches look broken even though the process is usable.
                init_line = await asyncio.wait_for(bp.process.stdout.readline(), timeout=1)
                if init_line:
                    init_data = json.loads(init_line)
                    if init_data.get("type") == "system" and init_data.get("subtype") == "init":
                        bp.session_id = init_data.get("session_id")
                        logger.info("Brain [%s] initialized: session=%s", bp.model, bp.session_id)
            except asyncio.TimeoutError:
                logger.debug("Brain [%s] init deferred until first turn", bp.model)
            except json.JSONDecodeError as e:
                logger.warning("Brain [%s] init parse error: %s", bp.model, e)
        else:
            await asyncio.sleep(2)
            if bp.alive:
                bp.session_id = f"{_PROVIDER}_default"
                logger.info("Brain [%s] ready (pid=%s)", bp.model, bp.process.pid)
            else:
                logger.warning("Brain [%s] failed to start", bp.model)

    async def _read_stderr(self, bp: BrainProcess):
        """Background task: continuously read stderr and detect provider errors."""
        try:
            while bp.alive and bp.process and bp.process.stderr:
                try:
                    line = await asyncio.wait_for(bp.process.stderr.readline(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                logger.debug("Brain [%s] stderr: %s", bp.model, text[:200])
                match = _classify_stderr_line(_PROVIDER, text)
                if match:
                    substring, category = match
                    error_info = {
                        "provider": _PROVIDER,
                        "category": category,
                        "matched": substring,
                        "message": text[:500],
                        "alternatives": _available_providers(_PROVIDER),
                        "timestamp": time.time(),
                    }
                    bp.last_stderr_error = error_info
                    logger.warning("Brain [%s] stderr error detected [%s]: %s",
                                   bp.model, category, text[:200])
                    _log_crash(f"Provider error [{_PROVIDER}/{category}]: {text[:200]}")
                    if self._on_provider_error:
                        try:
                            self._on_provider_error(error_info)
                        except Exception as cb_err:
                            logger.debug("Provider error callback failed: %s", cb_err)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("Stderr reader exited: %s", e)

    def set_provider_error_callback(self, callback):
        """Register a callback for provider errors. callback(error_dict) is called from stderr reader."""
        self._on_provider_error = callback

    def get_last_provider_error(self) -> Optional[dict]:
        """Return the last stderr-detected provider error, if any."""
        if self._brain:
            return self._brain.last_stderr_error
        return None

    def clear_provider_error(self):
        """Clear the cached provider error."""
        if self._brain:
            self._brain.last_stderr_error = None

    async def switch_provider(self, new_provider: str) -> dict:
        """Switch to a different LLM provider at runtime.

        1. Kill the current CLI process
        2. Check if the new CLI is installed, install if needed
        3. Update _PROVIDER and env
        4. Spawn the new CLI process
        5. Update .env file for persistence

        Returns dict with status info including needs_auth if applicable.
        """
        global _PROVIDER

        if new_provider not in ALL_PROVIDERS:
            return {"ok": False, "error": f"Unknown provider: {new_provider}"}

        if new_provider == _PROVIDER and self._brain and self._brain.alive:
            return {"ok": True, "message": f"Already running {new_provider}"}

        old_provider = _PROVIDER
        logger.info("Switching provider: %s → %s", old_provider, new_provider)

        # 1. Kill current process
        if self._brain:
            if self._brain._stderr_task:
                self._brain._stderr_task.cancel()
            await self._kill(self._brain)

        # 2. Check if CLI is installed, install if needed
        cli_check = {
            "claude": "claude",
            "gemini": "gemini",
            "openai": "codex",
        }
        cli_name = cli_check.get(new_provider, new_provider)
        needs_install = shutil.which(cli_name) is None

        if needs_install:
            logger.info("CLI '%s' not found, installing...", cli_name)
            install_script = os.path.join(
                os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence")),
                "docker", "jane", "install_brain.sh",
            )
            if os.path.isfile(install_script):
                env = os.environ.copy()
                env["JANE_BRAIN"] = new_provider
                # Remove the flag file so install_brain.sh doesn't skip
                flag_file = "/app/data/.brain_installed"
                if os.path.exists(flag_file):
                    os.remove(flag_file)
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "bash", install_script,
                        env=env,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                    if proc.returncode != 0:
                        logger.error("install_brain.sh failed: %s", stderr.decode()[:500])
                        return {"ok": False, "error": f"Failed to install {new_provider} CLI"}
                    logger.info("install_brain.sh completed for %s", new_provider)
                except asyncio.TimeoutError:
                    return {"ok": False, "error": f"Timed out installing {new_provider} CLI"}
            else:
                return {"ok": False, "error": f"Install script not found and {cli_name} not installed"}

        # 3. Update provider
        _PROVIDER = new_provider
        os.environ["JANE_BRAIN"] = new_provider

        # 4. Update model for new provider
        new_model = (
            os.environ.get(_ENV_VAR_FOR_MODEL.get(new_provider, ""), "")
            or _DEFAULT_MODELS.get(new_provider, "gemini-2.5-pro")
        )
        self._brain = BrainProcess(model=new_model)

        # 5. Spawn new process
        needs_auth = False
        if _provider_uses_standing_process(new_provider):
            try:
                await self._spawn(self._brain)
                if not self._brain.alive:
                    raise RuntimeError("Process died immediately after spawn")
            except Exception as e:
                logger.error("Failed to spawn %s brain: %s", new_provider, e)
                return {"ok": False, "error": f"Failed to start {new_provider}: {e}"}
            await asyncio.sleep(1)
            needs_auth = not self._brain.alive
        else:
            logger.info("Provider %s uses direct execution path; skipping standing-brain spawn", new_provider)

        # 6. Update .env for persistence
        self._update_env_file(new_provider)

        # 7. Report provider switch result
        result = {
            "ok": True,
            "provider": new_provider,
            "model": new_model,
            "was_installed": needs_install,
            "needs_auth": needs_auth,
        }

        if needs_auth:
            # Provide OAuth info so frontend can show auth link
            result["auth_url"] = None  # Will be resolved by the /api/cli-login endpoint
            result["message"] = f"{new_provider} CLI needs authentication. Use the login flow to authenticate."
        else:
            result["message"] = f"Switched to {new_provider} ({new_model})"

        logger.info("Provider switch complete: %s → %s (needs_auth=%s)", old_provider, new_provider, needs_auth)
        return result

    @staticmethod
    def _update_env_file(new_provider: str):
        """Update JANE_BRAIN in the .env file so the switch persists across restarts."""
        from jane.config import ENV_FILE_PATH
        env_path = Path(ENV_FILE_PATH) if ENV_FILE_PATH else None
        if not env_path or not env_path.exists():
            # Try common locations
            for candidate in [
                Path(os.environ.get("VESSENCE_DATA_HOME", "")) / ".env",
                Path("/data/.env"),
            ]:
                if candidate.exists():
                    env_path = candidate
                    break
        if not env_path or not env_path.exists():
            logger.warning("Could not find .env file to persist provider switch")
            return

        lines = env_path.read_text().splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("JANE_BRAIN="):
                new_lines.append(f"JANE_BRAIN={new_provider}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"JANE_BRAIN={new_provider}")
        env_path.write_text("\n".join(new_lines) + "\n")
        logger.info("Updated .env: JANE_BRAIN=%s", new_provider)

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
        configured_provider = _configured_provider()
        if configured_provider != _PROVIDER:
            result = await self.switch_provider(configured_provider)
            if not result.get("ok"):
                raise RuntimeError(result.get("error", f"Failed to switch provider to {configured_provider}"))
            if result.get("needs_auth"):
                raise RuntimeError(result.get("message", f"{configured_provider} requires authentication"))

        if not _provider_uses_standing_process(_PROVIDER):
            raise RuntimeError(
                f"Provider {_PROVIDER} does not support the standing-brain send path"
            )

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
            _raw_events_seen = 0

            try:
                if _PROVIDER == "claude":
                    async for event_type, chunk in self._read_claude_response(bp):
                        _raw_events_seen += 1
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
                logger.info("Brain [%s] turn %d complete in %dms (%d chars, %d raw events)",
                            bp.model, bp.turn_count, elapsed, len(response_text), _raw_events_seen)
            else:
                bp.consecutive_failures += 1
                logger.error(
                    "Brain [%s] turn %d EMPTY RESPONSE: elapsed=%dms, raw_events=%d, "
                    "process_alive=%s, message_len=%d, system_prompt_len=%d",
                    bp.model, bp.turn_count, elapsed, _raw_events_seen,
                    bp.alive, len(message), len(system_prompt),
                )
                # Check if stderr captured a provider error that explains the empty response
                if bp.last_stderr_error and (time.time() - bp.last_stderr_error.get("timestamp", 0)) < 30:
                    yield ("provider_error", json.dumps(bp.last_stderr_error))
                    bp.last_stderr_error = None
                else:
                    logger.warning("Brain [%s] turn %d: no result event, no stderr error captured", bp.model, bp.turn_count)

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
        """Read one complete NDJSON line from stdout using raw reads (no buffer limit).

        Uses short read intervals (_READ_CHUNK_TIMEOUT) so the event loop stays
        responsive, while enforcing a total RESPONSE_TIMEOUT_SECS deadline.
        """
        import time as _time
        deadline = _time.monotonic() + RESPONSE_TIMEOUT_SECS
        buf = bytearray()
        while True:
            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError(f"No brain output for {RESPONSE_TIMEOUT_SECS}s")
            timeout = min(_READ_CHUNK_TIMEOUT, remaining)
            try:
                chunk = await asyncio.wait_for(
                    bp.process.stdout.read(65536),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Short interval expired but total deadline not reached — retry
                continue
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
        import time as _time
        if hasattr(bp, '_read_buffer') and bp._read_buffer:
            buf = bytearray(bp._read_buffer)
            bp._read_buffer = b''
            idx = buf.find(b'\n')
            if idx >= 0:
                line = bytes(buf[:idx])
                bp._read_buffer = bytes(buf[idx + 1:])
                return line
            deadline = _time.monotonic() + RESPONSE_TIMEOUT_SECS
            while True:
                remaining = deadline - _time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError(f"No brain output for {RESPONSE_TIMEOUT_SECS}s")
                timeout = min(_READ_CHUNK_TIMEOUT, remaining)
                try:
                    chunk = await asyncio.wait_for(
                        bp.process.stdout.read(65536),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    continue
                if not chunk:
                    return bytes(buf) if buf else None
                buf.extend(chunk)
                idx = buf.find(b'\n')
                if idx >= 0:
                    line = bytes(buf[:idx])
                    bp._read_buffer = bytes(buf[idx + 1:])
                    return line
        return await self._read_ndjson_line(bp)

    async def _read_claude_response(self, bp: BrainProcess) -> AsyncGenerator[tuple[str, str], None]:
        """Read NDJSON stream events from Claude CLI stdout."""
        response_text = ""
        # Track which content blocks we've already processed to avoid
        # re-emitting thoughts/tool descriptions on every assistant event
        # (each assistant event contains ALL content blocks so far).
        _seen_block_count = 0
        _lines_read = 0
        while True:
            raw = await self._read_claude_line(bp)
            if not raw:
                if _lines_read == 0:
                    logger.warning("Brain [%s] _read_claude_response: EOF with 0 lines read (process alive=%s)", bp.model, bp.alive)
                else:
                    logger.debug("Brain [%s] _read_claude_response: EOF after %d lines, response=%d chars", bp.model, _lines_read, len(response_text))
                break
            _lines_read += 1

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
                logger.info("Brain [%s] result event: result_len=%d, accumulated=%d, lines_read=%d",
                            bp.model, len(result_text), len(response_text), _lines_read)
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
        if bp._stderr_task:
            bp._stderr_task.cancel()
            bp._stderr_task = None
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
