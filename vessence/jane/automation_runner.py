import logging
import os
import tempfile
import time
from pathlib import Path

from jane.brain_adapters import BrainAdapterError, build_execution_profile, get_brain_adapter, resolve_timeout_seconds
from jane.config import CODEX_BIN, VESSENCE_HOME
from agent_skills.cron_token_meter import log_llm_call as _log_llm_call

logger = logging.getLogger(__name__)


class AutomationError(RuntimeError):
    pass


# Canonical provider names. "openai" and "codex" are the same backend (Codex CLI);
# "opus"/"anthropic" mean Claude. Normalizing keeps the fallback chain from trying
# the same underlying subscription twice.
_PROVIDER_ALIASES = {
    "opus": "claude",
    "anthropic": "claude",
    "openai": "codex",
    "gpt": "codex",
    "google": "gemini",
    # Antigravity (agy) is the CLI behind the "gemini" provider.
    "agy": "gemini",
    "antigravity": "gemini",
}

# Order tried when a provider is exhausted/unavailable. Codex first (default brain),
# then Claude, then Gemini. The primary provider is always attempted first regardless.
_FALLBACK_ORDER = ("codex", "claude", "gemini")


def _canonical_provider(name: str) -> str:
    name = (name or "").lower()
    return _PROVIDER_ALIASES.get(name, name)


def _should_try_fallback(error_message: str) -> bool:
    """True when a failure looks like exhaustion/unavailability rather than a
    deterministic content/usage error we'd just hit again on another provider."""
    lowered = (error_message or "").lower()
    signals = (
        "limit", "quota", "exhaust", "rate", "429", "usage",
        "overloaded", "capacity", "unavailable", "timed out", "timeout",
        "not found", "failed", "empty response", "missing required",
    )
    return any(s in lowered for s in signals)


def _fallback_sequence(primary: str) -> list[str]:
    """Primary first, then the remaining providers in canonical order, deduped."""
    primary = _canonical_provider(primary)
    seq = [primary] + [p for p in _FALLBACK_ORDER if p != primary]
    seen: set[str] = set()
    ordered: list[str] = []
    for p in seq:
        if p and p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def get_automation_provider() -> str:
    return os.environ.get("AUTOMATION_CLI_PROVIDER", os.environ.get("JANE_BRAIN", "codex")).lower()


def _dispatch_single(
    provider_name: str,
    prompt: str,
    *,
    system_prompt: str,
    timeout_seconds: int | None,
    workdir: str,
    on_progress: "Callable[[str], None] | None",
) -> str:
    """Run the prompt against exactly one provider. Raises AutomationError on failure."""
    resolved_timeout = resolve_timeout_seconds(provider_name, timeout_seconds)
    start = time.perf_counter()
    error = None
    response = ""

    try:
        if provider_name == "codex":
            response = _run_codex(prompt, timeout_seconds=resolved_timeout, workdir=workdir)
        else:
            from jane.brain_adapters import _execute_subprocess_streaming
            adapter = get_brain_adapter(provider_name, build_execution_profile(provider_name, timeout_seconds=resolved_timeout))
            response = _execute_subprocess_streaming(
                adapter, system_prompt, prompt,
                on_delta=on_progress or (lambda _: None),
            )
        return response
    except AutomationError as exc:
        error = str(exc)
        raise
    except BrainAdapterError as exc:
        error = str(exc)
        raise AutomationError(error) from exc
    except Exception as exc:
        error = str(exc)
        raise AutomationError(error) from exc
    finally:
        _log_llm_call(
            provider=provider_name,
            model="",
            prompt_chars=len(prompt),
            response_chars=len(response),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            success=error is None,
            phase="automation_runner._dispatch_single",
            job=os.environ.get("CRON_JOB"),
            error=error,
        )


def run_automation_prompt(
    prompt: str,
    *,
    system_prompt: str = "",
    timeout_seconds: int | None = None,
    workdir: str | None = None,
    provider: str | None = None,
    on_progress: "Callable[[str], None] | None" = None,
    use_fallback: bool | None = None,
) -> str:
    """Run an automation prompt, falling back across providers when one is exhausted.

    The primary provider (explicit ``provider`` arg, else ``get_automation_provider()``)
    is tried first. If it fails with a transient/quota/unavailable-style error, the
    remaining providers in ``_FALLBACK_ORDER`` are tried in turn (codex -> claude ->
    gemini, primary excluded). This is what lets a codex-default cron switch to Claude
    when Codex is out of usage, and vice-versa.

    Fallback is on by default. Disable per-call with ``use_fallback=False`` or globally
    with the env var ``AUTOMATION_CLI_FALLBACK=0``.
    """
    primary = _canonical_provider(provider or get_automation_provider())
    target_dir = workdir or VESSENCE_HOME

    if use_fallback is None:
        use_fallback = os.environ.get("AUTOMATION_CLI_FALLBACK", "1").strip().lower() not in ("0", "false", "no")

    providers = _fallback_sequence(primary) if use_fallback else [primary]

    last_exc: Exception | None = None
    for idx, provider_name in enumerate(providers):
        try:
            return _dispatch_single(
                provider_name, prompt,
                system_prompt=system_prompt,
                timeout_seconds=timeout_seconds,
                workdir=target_dir,
                on_progress=on_progress,
            )
        except AutomationError as exc:
            last_exc = exc
            is_last = idx == len(providers) - 1
            if is_last or not _should_try_fallback(str(exc)):
                raise
            next_provider = providers[idx + 1]
            logger.warning(
                "Automation provider '%s' failed (%s); falling back to '%s'.",
                provider_name, str(exc)[:150], next_provider,
            )

    raise last_exc or AutomationError("All automation providers failed.")


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
        "-",
    ]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
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
