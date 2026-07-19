"""Provider-agnostic CLI wrapper for LLM completions.

Uses the user's existing subscription (Claude Pro/Max, OpenAI Plus, or Gemini)
via their CLI binary. No separate API keys needed — just a subscription and the
CLI installed.

Supports: claude, codex (OpenAI), gemini CLIs.
"""

import os
import signal
import subprocess
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skills.cli_llm_policy import (
    extract_json_text as _extract_json_text,
    fallback_provider_sequence as _fallback_provider_sequence,
    model_for_tier as _model_for_tier,
    should_try_fallback as _should_try_fallback,
    truncate_prompt_for_cli as _truncate_prompt_for_cli,
)
from agent_skills.cron_token_meter import log_llm_call as _log_llm_call
from jane.config import PROVIDER_CLI, CHEAP_MODEL, SMART_MODEL, FRONTIER_MODEL, _PROVIDER, PROVIDER_MODELS

# Tiered Model Mapping (as of 2026-03-27)
# Orchestrator: Primary Reasoning (Opus/Sonnet)
# Agent: Specialist (Sonnet/Pro)
# Utility: Background Worker (Haiku/Flash)


class RepairProvidersExhausted(RuntimeError):
    """Both approved unattended-repair providers failed safely.

    Critical Waterlily repair intentionally has a narrower policy than normal
    background work: Codex is tried first and Claude second.  Keep only the
    provider name and exception class so an incident/report never receives a
    CLI command, prompt, provider stderr, or other untrusted response text.
    """

    def __init__(self, attempts: list[dict[str, str]]):
        self.attempts = tuple(
            {
                "provider": str(attempt.get("provider") or "unknown"),
                "error_type": str(attempt.get("error_type") or "RuntimeError"),
            }
            for attempt in attempts
        )
        super().__init__("Codex and Claude repair providers were exhausted")


class ProviderCapacityResponse(RuntimeError):
    """A zero-exit CLI response that explicitly says it cannot continue."""


class ProviderLeaseUnavailable(RuntimeError):
    """A critical-repair provider could not be durably associated with its parent.

    Codex and Claude are launched in their own process groups.  If the repair
    worker crashes while one is editing a checkout, another worker must not
    start a second editor beside it.  The caller therefore gets one narrow
    synchronous chance to persist the exact child lease immediately after
    ``Popen``.  A rejected lease stops only that just-created process group.
    """


@dataclass(frozen=True)
class CriticalRepairCompletion:
    """Ephemeral result of one approved critical-repair provider handoff.

    ``output`` is intentionally never persisted by the repair runner.  The
    provider name is structural metadata that lets a failed end-to-end repair
    rotate to the other approved provider on its next durable retry.
    """

    output: str
    provider: str
    failed_attempts: tuple[dict[str, str], ...] = ()


def _looks_like_provider_capacity_response(output: str) -> bool:
    """Recognize terminal token/quota responses returned with exit code zero.

    Some CLIs print a usage/token-limit notice as ordinary stdout instead of a
    non-zero exit.  This detector is deliberately used only by the dedicated
    unattended-repair policy below; normal assistant prose remains untouched.
    """

    text = " ".join(str(output or "").lower().split())
    if not text:
        return False
    limit_terms = (
        "usage limit",
        "token limit",
        "rate limit",
        "quota limit",
        "quota exceeded",
        "context window",
        "context length",
        "ran out of tokens",
        "token budget",
    )
    unable_terms = (
        "limit reached",
        "has reached",
        "have reached",
        "hit your",
        "try again later",
        "cannot continue",
        "can't continue",
        "unable to continue",
        "exhausted",
        "ran out",
        "exceeded",
        "please wait",
        "will reset",
        "resets at",
        "too many requests",
    )
    explicit_capacity_phrases = (
        "usage limit reached",
        "token limit reached",
        "rate limit exceeded",
        "quota exceeded",
        "context window exceeded",
        "context length exceeded",
        "ran out of tokens",
        "too many requests",
        "you've hit your",
        "you have hit your",
        "you've reached your",
        "you have reached your",
    )
    return (
        any(phrase in text for phrase in explicit_capacity_phrases)
        or (any(term in text for term in limit_terms) and any(term in text for term in unable_terms))
    )


def _build_command(
    prompt: str,
    model: str,
    max_tokens: int,
    cli: str | None = None,
    cwd: str | None = None,
) -> list[str]:
    """Build the CLI command for the active provider."""
    cli = cli or os.environ.get("PROVIDER_CLI", PROVIDER_CLI)

    if "claude" in cli or cli == "claude":
        return [cli, "-p", prompt, "--output-format", "text",
                "--model", model]

    elif "codex" in cli or cli == "codex":
        # OpenAI Codex CLI
        cmd = [cli, "exec", "--dangerously-bypass-approvals-and-sandbox"]
        if model:
            cmd.extend(["-m", model])
        if cwd:
            cmd.extend(["-C", cwd])
        return cmd + [prompt]

    elif "agy" in cli or "gemini" in cli or cli in ("agy", "gemini"):
        # Antigravity (agy) — Google's successor to the gemini CLI.
        # Flags must precede -p or -p swallows the next flag as its prompt.
        return [cli, "--dangerously-skip-permissions", "--print-timeout", "60m", "-p", prompt]

    else:
        # Fallback: treat as claude-compatible
        return [cli, "-p", prompt, "--output-format", "text",
                "--model", model]


def _provider_for_command(command: str) -> str:
    command = (command or "").lower()
    if "agy" in command or "gemini" in command:
        return "gemini"
    if "codex" in command:
        return "codex"
    if "claude" in command:
        return "claude"
    return "unknown"


def _terminate_provider_process_group(process: subprocess.Popen[str]) -> None:
    """Stop a timed-out provider and any descendants before fallback starts.

    Critical repair can hand off from Codex to Claude after a provider timeout.
    Leaving the first CLI's children alive would let two autonomous agents edit
    the same checkout concurrently.  The process is launched in its own
    session below, so group signals cannot reach Jane's parent process.
    """
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        # A fast-exiting child may already be gone.  ``communicate`` below
        # still reaps it; do not surface process-management noise to prompts.
        pass
    try:
        process.communicate(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        process.communicate()
    except Exception:
        # The original provider timeout remains the caller-visible result.
        pass


def _run_provider_command(
    cmd: list[str],
    *,
    timeout: int,
    env: dict[str, str],
    cwd: str | None,
    on_process_started: Callable[[int], bool] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one provider in an isolated process group and collect its output.

    ``on_process_started`` is used only by the critical self-healing runner to
    persist a PID/start-tick lease before the provider can make edits.  It
    receives no command, prompt, or output.  If the durable lease cannot be
    recorded, terminate this newly created group before any fallback can run.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=cwd,
        start_new_session=True,
    )
    if on_process_started is not None:
        try:
            leased = on_process_started(int(process.pid))
        except Exception:
            leased = False
        if leased is not True:
            _terminate_provider_process_group(process)
            raise ProviderLeaseUnavailable("critical repair provider lease unavailable")
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_provider_process_group(process)
        raise
    return subprocess.CompletedProcess(cmd, int(process.returncode or 0), stdout, stderr)


def completion(prompt: str, *, model: str | None = None,
               max_tokens: int = 1024, timeout: int = 60,
               cli: str | None = None,
               cwd: str | None = None,
               on_process_started: Callable[[int], bool] | None = None,
               detect_capacity_response: bool = False) -> str:
    """Send a single prompt to the active CLI and return the text response.

    Args:
        prompt: The full prompt text.
        model: Model to use. Defaults to CHEAP_MODEL (for background tasks).
        max_tokens: Max output tokens.
        timeout: Subprocess timeout in seconds.
        cli: Optional CLI binary override.

    Returns:
        The assistant's response text, stripped.
    """
    # Safety truncation to avoid "Argument list too long" errors
    # 32,000 characters is a safe limit for most CLI arguments.
    prompt = _truncate_prompt_for_cli(prompt)

    model = model or CHEAP_MODEL
    cmd = _build_command(prompt, model, max_tokens, cli=cli, cwd=cwd)
    provider = _provider_for_command(cmd[0])
    prompt_chars = len(prompt)
    response_chars = 0
    start = time.perf_counter()
    error = None
    result = None

    subprocess_env = os.environ.copy()
    is_agy = "agy" in cmd[0]
    if is_agy:
        # Run agy under a minimal HOME so it skips the interactive Jane persona
        # bootstrap and returns clean output.
        from jane.agy_env import agy_headless_home
        subprocess_env["HOME"] = agy_headless_home()

    try:
        result = _run_provider_command(
            cmd,
            timeout=timeout,
            env=subprocess_env,
            cwd=cwd if not ("codex" in cmd[0] or cmd[0] == "codex") else None,
            on_process_started=on_process_started,
        )

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "Unknown error").strip()[:500]
            error = f"CLI ({cmd[0]}) failed (exit {result.returncode}): {err}"
            raise RuntimeError(error)

        output = result.stdout.strip()
        response_chars = len(output)
        if not output:
            err = (result.stderr or "no stderr").strip()[:500]
            error = f"CLI ({cmd[0]}) returned empty response: {err}"
            raise RuntimeError(error)

        # Critical repair must hand off immediately when a provider returns a
        # zero-exit quota/token message.  Inspect stderr too: some CLI
        # versions put a short normal-looking stdout banner beside the actual
        # capacity notice on stderr.  This remains opt-in so ordinary prose
        # completion is never reclassified by a broad heuristic.
        if detect_capacity_response and _looks_like_provider_capacity_response(
            "\n".join((output, str(result.stderr or "")))
        ):
            raise ProviderCapacityResponse("provider reported an exhausted token or usage limit")

        return output
    except subprocess.TimeoutExpired as exc:
        # ``TimeoutExpired.__str__`` includes the complete command, which for
        # these CLIs contains the prompt.  Keep both token-meter logs and the
        # fallback path privacy-safe while making timeout a normal retryable
        # provider failure.
        error = f"CLI ({cmd[0]}) timed out after {timeout}s"
        raise RuntimeError(error) from exc
    except Exception as exc:
        if error is None:
            error = str(exc)
        raise
    finally:
        _log_llm_call(
            provider=provider,
            model=model or "",
            prompt_chars=prompt_chars,
            response_chars=response_chars,
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            success=error is None,
            phase="claude_cli_llm.completion",
            job=os.environ.get("CRON_JOB"),
            error=error,
        )


def completion_with_fallback(prompt: str, *, tier: str = "utility", 
                             max_tokens: int = 1024, timeout: int = 60,
                             cwd: str | None = None) -> str:
    """Try primary provider, then fall back to others if limit is hit."""
    import logging
    logger = logging.getLogger(__name__)

    # 1. Try Primary
    try:
        if tier == "orchestrator":
            return completion_orchestrator(prompt, max_tokens=max_tokens, timeout=timeout, use_fallback=False, cwd=cwd)
        elif tier == "agent":
            return completion_agent(prompt, max_tokens=max_tokens, timeout=timeout, use_fallback=False, cwd=cwd)
        else:
            return completion_utility(prompt, max_tokens=max_tokens, timeout=timeout, use_fallback=False, cwd=cwd)
    except Exception as e:
        # A raw TimeoutExpired can contain the whole CLI command (and thus the
        # prompt).  Completion() normalizes it, but preserve that guarantee for
        # injected/alternate callers too.
        err_msg = (
            f"CLI timed out after {timeout}s"
            if isinstance(e, subprocess.TimeoutExpired)
            else str(e)
        )
        # If it's a hard error like "CLI not found" AND not a limit error, raise it.
        # But if it's a limit, quota, timeout, or general failure, try fallback.
        if not _should_try_fallback(err_msg) and not isinstance(
            e,
            (OSError, subprocess.TimeoutExpired),
        ):
            raise
        
        logger.warning(f"Primary LLM failed: {err_msg[:100]}... Attempting fallback.")

    # 2. Try fallback providers in policy order (OpenAI/Codex, Claude, then agy/Gemini by default).
    fallbacks = _fallback_provider_sequence(_PROVIDER)
    
    last_err = None
    for provider in fallbacks:
        config = PROVIDER_MODELS.get(provider)
        if not config:
            continue
            
        cli = config["cli"]
        # Map tier to provider-specific model (though _build_command may ignore it for codex)
        model = _model_for_tier(config, tier)
            
        try:
            logger.info(f"Fallback: trying {provider} ({cli})...")
            return completion(prompt, model=model, cli=cli, max_tokens=max_tokens, timeout=timeout, cwd=cwd)
        except Exception as fe:
            logger.warning(f"Fallback to {provider} failed: {str(fe)[:100]}...")
            last_err = fe
            
    raise last_err or RuntimeError("Primary LLM and all fallbacks failed.")


def completion_for_critical_repair_result(
    prompt: str,
    *,
    max_tokens: int = 8192,
    timeout: int = 1800,
    cwd: str | None = None,
    provider_order: tuple[str, ...] | list[str] | None = None,
    on_provider_started: Callable[[str, int], bool] | None = None,
) -> CriticalRepairCompletion:
    """Run an explicitly constrained Codex/Claude critical-repair policy.

    This must not inherit the generic provider sequence: a critical repair
    failure is actionable for Chieh after Codex and Claude have both failed,
    and the caller then sends one Vessence alert while durable retries remain
    active.  In particular, do not silently route this policy through Gemini.
    """

    configured_order = provider_order or ("codex", "claude")
    provider_keys = {"codex": "openai", "claude": "claude"}
    normalized_order: list[str] = []
    for raw_provider in configured_order:
        provider = str(raw_provider or "").strip().lower()
        if provider not in provider_keys:
            raise ValueError("critical repair provider order contains an unsupported provider")
        if provider not in normalized_order:
            normalized_order.append(provider)
    if not normalized_order:
        raise ValueError("critical repair provider order is empty")

    attempts: list[dict[str, str]] = []
    for display_name in normalized_order:
        provider = provider_keys[display_name]
        config = PROVIDER_MODELS.get(provider)
        if not isinstance(config, dict):
            attempts.append({"provider": display_name, "error_type": "ProviderUnavailable"})
            continue
        cli = str(config.get("cli") or "").strip()
        model = str(config.get("smart") or config.get("cheap") or "").strip()
        if not cli or not model:
            attempts.append({"provider": display_name, "error_type": "ProviderUnavailable"})
            continue
        try:
            output = completion(
                prompt,
                model=model,
                cli=cli,
                max_tokens=max_tokens,
                timeout=timeout,
                cwd=cwd,
                detect_capacity_response=True,
                on_process_started=(
                    (lambda pid, name=display_name: on_provider_started(name, pid))
                    if on_provider_started is not None
                    else None
                ),
            )
            if _looks_like_provider_capacity_response(output):
                raise ProviderCapacityResponse("provider reported an exhausted token or usage limit")
            return CriticalRepairCompletion(
                output=output,
                provider=display_name,
                failed_attempts=tuple(attempts),
            )
        except Exception as exc:
            # Do not persist ``str(exc)``: timeout/CLI exceptions can contain
            # the complete command, including the private repair prompt.
            attempts.append({"provider": display_name, "error_type": type(exc).__name__})

    raise RepairProvidersExhausted(attempts)


def completion_for_critical_repair(
    prompt: str,
    *,
    max_tokens: int = 8192,
    timeout: int = 1800,
    cwd: str | None = None,
    provider_order: tuple[str, ...] | list[str] | None = None,
    on_provider_started: Callable[[str, int], bool] | None = None,
) -> str:
    """Compatibility wrapper returning only the private repair output."""
    return completion_for_critical_repair_result(
        prompt,
        max_tokens=max_tokens,
        timeout=timeout,
        cwd=cwd,
        provider_order=provider_order,
        on_provider_started=on_provider_started,
    ).output


def completion_orchestrator(
    prompt: str,
    *,
    max_tokens: int = 4096,
    timeout: int = 180,
    use_fallback: bool = True,
    cwd: str | None = None,
) -> str:
    """Uses the configured frontier model for complex reasoning/code."""
    if use_fallback:
        return completion_with_fallback(prompt, tier="orchestrator", max_tokens=max_tokens, timeout=timeout, cwd=cwd)
    return completion(prompt, model=FRONTIER_MODEL, max_tokens=max_tokens, timeout=timeout, cwd=cwd)


def completion_agent(
    prompt: str,
    *,
    max_tokens: int = 4096,
    timeout: int = 120,
    use_fallback: bool = True,
    cwd: str | None = None,
) -> str:
    """Uses the configured smart/frontier model for specialized research and archival."""
    if use_fallback:
        return completion_with_fallback(prompt, tier="agent", max_tokens=max_tokens, timeout=timeout, cwd=cwd)
    return completion(prompt, model=SMART_MODEL, max_tokens=max_tokens, timeout=timeout, cwd=cwd)


def completion_utility(
    prompt: str,
    *,
    max_tokens: int = 1024,
    timeout: int = 60,
    use_fallback: bool = True,
    cwd: str | None = None,
) -> str:
    """Uses the Utility-tier model (Haiku) for triage and simple tasks."""
    if use_fallback:
        return completion_with_fallback(prompt, tier="utility", max_tokens=max_tokens, timeout=timeout, cwd=cwd)
    return completion(prompt, model=CHEAP_MODEL, max_tokens=max_tokens, timeout=timeout, cwd=cwd)


def completion_smart(prompt: str, *, max_tokens: int = 4096, timeout: int = 120) -> str:
    """Legacy alias for completion_agent."""
    return completion_agent(prompt, max_tokens=max_tokens, timeout=timeout)


def completion_json(prompt: str, *, tier: str = "utility", timeout: int = 300) -> dict:
    """Send a prompt expecting JSON output. Defaults to Utility tier.
    Timeout increased to 300s for complex Agent-tier thematic archival."""
    if tier == "agent":
        text = completion_agent(prompt, max_tokens=4096, timeout=timeout)
    else:
        text = completion_utility(prompt, max_tokens=4096, timeout=timeout)
    
    return json.loads(_extract_json_text(text))
