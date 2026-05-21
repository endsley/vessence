"""Provider-agnostic CLI wrapper for LLM completions.

Uses the user's existing subscription (Claude Pro/Max, OpenAI Plus, or Gemini)
via their CLI binary. No separate API keys needed — just a subscription and the
CLI installed.

Supports: claude, codex (OpenAI), gemini CLIs.
"""

import os
import subprocess
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import PROVIDER_CLI, CHEAP_MODEL, SMART_MODEL, FRONTIER_MODEL, _PROVIDER, PROVIDER_MODELS

# Tiered Model Mapping (as of 2026-03-27)
# Orchestrator: Primary Reasoning (Opus/Sonnet)
# Agent: Specialist (Sonnet/Pro)
# Utility: Background Worker (Haiku/Flash)


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

    elif "gemini" in cli or cli == "gemini":
        # Gemini CLI
        # Use --prompt for non-interactive
        return [cli, "--prompt", prompt]

    else:
        # Fallback: treat as claude-compatible
        return [cli, "-p", prompt, "--output-format", "text",
                "--model", model]


def completion(prompt: str, *, model: str | None = None,
               max_tokens: int = 1024, timeout: int = 60,
               cli: str | None = None,
               cwd: str | None = None) -> str:
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
    if len(prompt) > 32000:
        prompt = prompt[:1000] + "\n... [TRUNCATED] ...\n" + prompt[-31000:]
        
    model = model or CHEAP_MODEL
    cmd = _build_command(prompt, model, max_tokens, cli=cli, cwd=cwd)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, env=os.environ.copy(),
            cwd=cwd if not ("codex" in cmd[0] or cmd[0] == "codex") else None,
        )
    except FileNotFoundError:
        raise RuntimeError(f"CLI not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"CLI timed out after {timeout}s")

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "Unknown error").strip()[:500]
        raise RuntimeError(f"CLI ({cmd[0]}) failed (exit {result.returncode}): {err}")

    return result.stdout.strip()


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
    except RuntimeError as e:
        err_msg = str(e)
        # If it's a hard error like "CLI not found" AND not a limit error, raise it.
        # But if it's a limit, quota, timeout, or general failure, try fallback.
        is_limit = "limit" in err_msg.lower() or "quota" in err_msg.lower()
        is_timeout = "timed out" in err_msg.lower()
        
        if not (is_limit or is_timeout or "failed" in err_msg.lower()):
            raise e
        
        logger.warning(f"Primary LLM failed: {err_msg[:100]}... Attempting fallback.")

    # 2. Try Fallbacks (Codex then Gemini)
    fallback_sequence = ["openai", "gemini", "claude"]
    # Filter out current provider
    fallbacks = [p for p in fallback_sequence if p != _PROVIDER]
    
    last_err = None
    for provider in fallbacks:
        config = PROVIDER_MODELS.get(provider)
        if not config:
            continue
            
        cli = config["cli"]
        # Map tier to provider-specific model (though _build_command may ignore it for codex)
        if tier == "orchestrator" or tier == "agent":
            model = config["smart"]
        else:
            model = config["cheap"]
            
        try:
            logger.info(f"Fallback: trying {provider} ({cli})...")
            return completion(prompt, model=model, cli=cli, max_tokens=max_tokens, timeout=timeout, cwd=cwd)
        except Exception as fe:
            logger.warning(f"Fallback to {provider} failed: {str(fe)[:100]}...")
            last_err = fe
            
    raise last_err or RuntimeError("Primary LLM and all fallbacks failed.")


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
    
    # Strip markdown code fences if present
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    
    return json.loads(text)
