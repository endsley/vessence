import os
import tempfile
from pathlib import Path

from jane.brain_adapters import BrainAdapterError, build_execution_profile, get_brain_adapter, resolve_timeout_seconds
from jane.config import CODEX_BIN, VESSENCE_HOME


class AutomationError(RuntimeError):
    pass


def get_automation_provider() -> str:
    return os.environ.get("AUTOMATION_CLI_PROVIDER", os.environ.get("JANE_BRAIN", "codex")).lower()


def run_automation_prompt(
    prompt: str,
    *,
    system_prompt: str = "",
    timeout_seconds: int | None = None,
    workdir: str | None = None,
    provider: str | None = None,
    on_progress: "Callable[[str], None] | None" = None,
) -> str:
    provider_name = (provider or get_automation_provider()).lower()
    target_dir = workdir or VESSENCE_HOME
    resolved_timeout = resolve_timeout_seconds(provider_name, timeout_seconds)

    if provider_name == "codex":
        return _run_codex(prompt, timeout_seconds=resolved_timeout, workdir=target_dir)

    try:
        from jane.brain_adapters import _execute_subprocess_streaming
        adapter = get_brain_adapter(provider_name, build_execution_profile(provider_name, timeout_seconds=resolved_timeout))
        return _execute_subprocess_streaming(
            adapter, system_prompt, prompt,
            on_delta=on_progress or (lambda _: None),
        )
    except BrainAdapterError as exc:
        raise AutomationError(str(exc)) from exc


def _run_codex(prompt: str, *, timeout_seconds: int, workdir: str) -> str:
    import subprocess

    with tempfile.NamedTemporaryFile(prefix="automation_runner_", suffix=".txt", delete=False) as tmp:
        output_path = tmp.name

    cmd = [
        CODEX_BIN,
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "-C",
        workdir,
        "-o",
        output_path,
        prompt,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        Path(output_path).unlink(missing_ok=True)
        raise AutomationError(f"Codex CLI not found: {CODEX_BIN}") from exc
    except subprocess.TimeoutExpired as exc:
        Path(output_path).unlink(missing_ok=True)
        raise AutomationError(f"Codex CLI timed out after {timeout_seconds}s") from exc

    text = Path(output_path).read_text().strip() if Path(output_path).exists() else ""
    try:
        Path(output_path).unlink(missing_ok=True)
    except Exception:
        pass

    if result.returncode != 0:
        err = (result.stderr or text or result.stdout or "").strip()
        raise AutomationError(
            f"Codex CLI failed (exit code {result.returncode}): {err[:500] or 'no error output'}"
        )
    if not text:
        raise AutomationError(
            f"Codex CLI returned an empty response (exit code {result.returncode}, "
            f"stderr: {(result.stderr or '').strip()[:200] or 'none'})"
        )
    return text
