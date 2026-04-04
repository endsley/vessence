import os
import selectors
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


def _kill_pgroup(process: subprocess.Popen) -> None:
    """Kill a subprocess and its entire process group."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            process.kill()
        except ProcessLookupError:
            pass


@dataclass(frozen=True)
class ExecutionProfile:
    mode: str = "safe"
    timeout_seconds: int = 180          # legacy: used as idle timeout
    idle_timeout_seconds: int = 120     # kill if no output for this long
    max_wall_seconds: int = 1800        # absolute safety cap (30 min)


PROVIDER_TIMEOUT_DEFAULTS = {
    "claude": 600,
    "codex": 600,
    "openai": 600,
    "gemini": 300,
}

PROVIDER_IDLE_DEFAULTS = {
    "claude": 1800,   # 30 min — Claude can think/use tools for long stretches
    "codex": 1800,
    "openai": 1800,
    "gemini": 600,
}

PROVIDER_WALL_DEFAULTS = {
    "claude": 3600,   # 1 hour hard cap
    "codex": 1800,
    "openai": 1800,
    "gemini": 1800,
}


class BrainAdapterError(RuntimeError):
    pass


class BrainAdapter:
    name = "unknown"
    label = "Unknown"
    required_env: tuple[str, ...] = ()

    def __init__(self, execution_profile: ExecutionProfile):
        self.execution_profile = execution_profile

    def _missing_env(self) -> list[str]:
        return [key for key in self.required_env if not os.environ.get(key)]

    def build_command(self, system_prompt: str, transcript: str) -> list[str]:
        raise NotImplementedError

    def parse_output(self, stdout: str) -> str:
        return stdout.strip()

    def execute_stream(self, system_prompt: str, transcript: str, on_delta: Callable[[str], None]) -> str:
        response = self.execute(system_prompt, transcript)
        on_delta(response)
        return response

    def execute(self, system_prompt: str, transcript: str) -> str:
        missing = self._missing_env()
        if missing:
            raise BrainAdapterError(f"Missing required environment variables: {', '.join(missing)}")

        cmd = self.build_command(system_prompt, transcript)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.execution_profile.timeout_seconds,
                env=os.environ.copy(),
            )
        except FileNotFoundError as exc:
            raise BrainAdapterError(f"{self.label} CLI not found: {cmd[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise BrainAdapterError(f"{self.label} CLI timed out after {self.execution_profile.timeout_seconds}s") from exc

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise BrainAdapterError(
                f"{self.label} CLI failed (exit code {result.returncode}): {err[:500] or 'no error output'}"
            )

        response = self.parse_output(result.stdout)
        if not response:
            raise BrainAdapterError(
                f"{self.label} returned an empty response (exit code {result.returncode}, "
                f"stderr: {(result.stderr or '').strip()[:200] or 'none'})"
            )
        return response


class GeminiBrainAdapter(BrainAdapter):
    name = "gemini"
    label = "Gemini"
    required_env = ("GOOGLE_API_KEY",)

    def build_command(self, system_prompt: str, transcript: str) -> list[str]:
        cmd = [os.environ.get("GEMINI_BIN", "/usr/local/bin/gemini")]
        if self.execution_profile.mode == "yolo":
            cmd.append("--approval-mode=yolo")
        cmd.extend(["-p", f"{system_prompt}\n\n{transcript}"])
        return cmd

    def execute_stream(self, system_prompt: str, transcript: str, on_delta: Callable[[str], None]) -> str:
        return _execute_subprocess_streaming(self, system_prompt, transcript, on_delta)


class ClaudeBrainAdapter(BrainAdapter):
    name = "claude"
    label = "Claude"
    required_env = ()  # Claude CLI uses its own auth, no API key needed

    # Claude CLI searches upward for CLAUDE.md which activates hooks that
    # interfere with subprocess calls. We set cwd to /tmp to avoid this.
    cwd_override = "/tmp"

    def build_command(self, system_prompt: str, transcript: str) -> list[str]:
        from jane.config import CLAUDE_BIN
        cmd = [os.environ.get("CLAUDE_BIN", CLAUDE_BIN)]
        if self.execution_profile.mode == "yolo":
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["-p", f"{system_prompt}\n\n{transcript}"])
        return cmd

    def execute(self, system_prompt: str, transcript: str) -> str:
        # Route through streaming path so Claude benefits from idle timeout
        return _execute_subprocess_streaming(self, system_prompt, transcript, lambda _: None)

    def execute_stream(self, system_prompt: str, transcript: str, on_delta: Callable[[str], None]) -> str:
        return _execute_subprocess_streaming(self, system_prompt, transcript, on_delta)


class OpenAIBrainAdapter(BrainAdapter):
    name = "openai"
    label = "OpenAI"
    required_env = ("OPENAI_API_KEY",)

    def execute(self, system_prompt: str, transcript: str) -> str:
        missing = self._missing_env()
        if missing:
            raise BrainAdapterError(f"Missing required environment variables: {', '.join(missing)}")

        full_prompt = f"{system_prompt}\n\n{transcript}".strip()
        with tempfile.NamedTemporaryFile(prefix="codex_brain_", suffix=".txt", delete=False) as tmp:
            output_path = tmp.name

        cmd = [
            os.environ.get("CODEX_BIN", "codex"),
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "-C",
            os.environ.get("VESSENCE_HOME", str(Path.home() / "vessence")),
            "-o",
            output_path,
            full_prompt,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.execution_profile.timeout_seconds,
                env=os.environ.copy(),
            )
        except FileNotFoundError as exc:
            Path(output_path).unlink(missing_ok=True)
            raise BrainAdapterError(f"Codex CLI not found: {cmd[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            Path(output_path).unlink(missing_ok=True)
            raise BrainAdapterError(f"Codex CLI timed out after {self.execution_profile.timeout_seconds}s") from exc

        response = Path(output_path).read_text().strip() if Path(output_path).exists() else ""
        try:
            Path(output_path).unlink(missing_ok=True)
        except Exception:
            pass

        if result.returncode != 0:
            err = (result.stderr or response or result.stdout or "").strip()
            raise BrainAdapterError(
                f"Codex CLI failed (exit code {result.returncode}): {err[:500] or 'no error output'}"
            )
        if not response:
            raise BrainAdapterError(
                f"Codex CLI returned an empty response (exit code {result.returncode}, "
                f"stderr: {(result.stderr or '').strip()[:200] or 'none'})"
            )
        return response


class CodexBrainAdapter(OpenAIBrainAdapter):
    name = "codex"
    label = "Codex"
    required_env = ()


def resolve_timeout_seconds(brain_name: str | None, timeout_seconds: int | None = None) -> int:
    """Resolve the legacy ``timeout_seconds`` value (kept for backward compat)."""
    if timeout_seconds is not None:
        return timeout_seconds

    normalized = (brain_name or "").lower()
    provider_default = PROVIDER_TIMEOUT_DEFAULTS.get(normalized, 180)

    provider_override = os.environ.get(f"JANE_TIMEOUT_SECONDS_{normalized.upper()}")
    if provider_override:
        return int(provider_override)

    shared_override = os.environ.get("JANE_TIMEOUT_SECONDS")
    if shared_override:
        return max(int(shared_override), provider_default)

    return provider_default


def _resolve_idle_timeout(brain_name: str | None) -> int:
    normalized = (brain_name or "").lower()
    env_val = os.environ.get(f"JANE_IDLE_TIMEOUT_{normalized.upper()}")
    if env_val:
        return int(env_val)
    env_val = os.environ.get("JANE_IDLE_TIMEOUT")
    if env_val:
        return int(env_val)
    return PROVIDER_IDLE_DEFAULTS.get(normalized, 120)


def _resolve_wall_timeout(brain_name: str | None) -> int:
    normalized = (brain_name or "").lower()
    env_val = os.environ.get(f"JANE_WALL_TIMEOUT_{normalized.upper()}")
    if env_val:
        return int(env_val)
    env_val = os.environ.get("JANE_WALL_TIMEOUT")
    if env_val:
        return int(env_val)
    return PROVIDER_WALL_DEFAULTS.get(normalized, 1800)


def build_execution_profile(
    brain_name: str | None,
    *,
    mode: str | None = None,
    timeout_seconds: int | None = None,
) -> ExecutionProfile:
    return ExecutionProfile(
        mode=(mode or os.environ.get("JANE_EXECUTION_MODE", "safe")).lower(),
        timeout_seconds=resolve_timeout_seconds(brain_name, timeout_seconds),
        idle_timeout_seconds=_resolve_idle_timeout(brain_name),
        max_wall_seconds=_resolve_wall_timeout(brain_name),
    )


def get_brain_adapter(brain_name: str, execution_profile: ExecutionProfile) -> BrainAdapter:
    registry = {
        "gemini": GeminiBrainAdapter,
        "claude": ClaudeBrainAdapter,
        "openai": OpenAIBrainAdapter,
        "codex": CodexBrainAdapter,
    }
    adapter_cls = registry.get(brain_name.lower(), GeminiBrainAdapter)
    return adapter_cls(execution_profile)


def _execute_subprocess_streaming(
    adapter: BrainAdapter,
    system_prompt: str,
    transcript: str,
    on_delta: Callable[[str], None],
) -> str:
    """Execute a CLI subprocess with idle-based timeout.

    Instead of a fixed wall-clock deadline, the process is killed only when
    it produces no output for ``idle_timeout_seconds``.  A hard
    ``max_wall_seconds`` cap still exists as a safety net.
    """
    missing = adapter._missing_env()
    if missing:
        raise BrainAdapterError(f"Missing required environment variables: {', '.join(missing)}")

    cmd = adapter.build_command(system_prompt, transcript)
    cwd = getattr(adapter, "cwd_override", None)

    idle_timeout = adapter.execution_profile.idle_timeout_seconds
    wall_deadline = time.monotonic() + adapter.execution_profile.max_wall_seconds

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
            cwd=cwd,
            env=os.environ.copy(),
            start_new_session=True,  # own process group for clean shutdown
        )
    except FileNotFoundError as exc:
        raise BrainAdapterError(f"{adapter.label} CLI not found: {cmd[0]}") from exc

    selector = selectors.DefaultSelector()
    if process.stdout is not None:
        selector.register(process.stdout, selectors.EVENT_READ, data="stdout")
    if process.stderr is not None:
        selector.register(process.stderr, selectors.EVENT_READ, data="stderr")

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    last_activity = time.monotonic()

    try:
        while selector.get_map():
            now = time.monotonic()

            # Check idle timeout (no output for too long)
            idle_elapsed = now - last_activity
            if idle_elapsed >= idle_timeout:
                raise subprocess.TimeoutExpired(
                    cmd, idle_timeout,
                    output=f"idle for {idle_elapsed:.0f}s (limit {idle_timeout}s)",
                )

            # Check wall-clock safety cap
            if now >= wall_deadline:
                raise subprocess.TimeoutExpired(
                    cmd, adapter.execution_profile.max_wall_seconds,
                    output="hit max wall-clock limit",
                )

            wait_time = min(0.1, idle_timeout - idle_elapsed, wall_deadline - now)
            events = selector.select(timeout=max(0.001, wait_time))

            if not events:
                if process.poll() is not None:
                    break
                continue

            for key, _ in events:
                stream = key.fileobj
                try:
                    data = os.read(stream.fileno(), 4096)
                except OSError:
                    data = b""
                if not data:
                    selector.unregister(stream)
                    continue

                last_activity = time.monotonic()  # reset idle timer
                text = data.decode(errors="ignore")
                if key.data == "stdout":
                    stdout_chunks.append(text)
                    on_delta(text)
                else:
                    stderr_chunks.append(text)

        wait_remaining = max(0.0, min(idle_timeout, wall_deadline - time.monotonic()))
        try:
            process.wait(timeout=wait_remaining)
        except subprocess.TimeoutExpired:
            # Attribute idle vs wall based on what was pending
            elapsed_idle = time.monotonic() - last_activity
            if elapsed_idle >= idle_timeout:
                raise subprocess.TimeoutExpired(
                    cmd, idle_timeout,
                    output=f"idle for {elapsed_idle:.0f}s (limit {idle_timeout}s)",
                )
            raise subprocess.TimeoutExpired(
                cmd, adapter.execution_profile.max_wall_seconds,
                output="hit max wall-clock limit",
            )
    except subprocess.TimeoutExpired as exc:
        _kill_pgroup(process)
        process.wait()
        detail = getattr(exc, "output", "") or ""
        if "idle" in str(detail):
            msg = f"{adapter.label} CLI killed: no output for {idle_timeout}s (idle timeout)"
        elif "wall" in str(detail):
            msg = f"{adapter.label} CLI killed: exceeded {adapter.execution_profile.max_wall_seconds}s wall-clock limit"
        else:
            msg = f"{adapter.label} CLI timed out after {exc.timeout}s"
        raise BrainAdapterError(msg) from exc
    finally:
        selector.close()
        # Ensure process is dead — prevents zombies on unexpected exceptions
        if process.poll() is None:
            _kill_pgroup(process)
            process.wait()
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    if process.returncode != 0:
        err = ("".join(stderr_chunks) or "".join(stdout_chunks) or "").strip()
        raise BrainAdapterError(
            f"{adapter.label} CLI failed (exit code {process.returncode}): {err[:500] or 'no error output'}"
        )

    response = adapter.parse_output("".join(stdout_chunks))
    if not response:
        stderr_hint = "".join(stderr_chunks).strip()[:200]
        raise BrainAdapterError(
            f"{adapter.label} returned an empty response (exit code {process.returncode}, "
            f"stderr: {stderr_hint or 'none'})"
        )
    return response
