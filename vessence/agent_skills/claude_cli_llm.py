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
from jane.config import PROVIDER_CLI, CHEAP_MODEL, SMART_MODEL, _PROVIDER

# Tiered Model Mapping (as of 2026-03-27)
# Orchestrator: Primary Reasoning (Opus/Sonnet)
# Agent: Specialist (Sonnet/Pro)
# Utility: Background Worker (Haiku/Flash)


def _build_command(prompt: str, model: str, max_tokens: int) -> list[str]:
    """Build the CLI command for the active provider."""
    cli = os.environ.get("PROVIDER_CLI", PROVIDER_CLI)

    if "claude" in cli or cli == "claude":
        return [cli, "-p", prompt, "--output-format", "text",
                "--model", model]

    elif "codex" in cli or cli == "codex":
        # OpenAI Codex CLI
        return [cli, "exec", "--dangerously-bypass-approvals-and-sandbox",
                "-m", model, prompt]

    elif "gemini" in cli or cli == "gemini":
        # Gemini CLI
        return [cli, "-p", prompt]

    else:
        # Fallback: treat as claude-compatible
        return [cli, "-p", prompt, "--output-format", "text",
                "--model", model]


def completion(prompt: str, *, model: str | None = None,
               max_tokens: int = 1024, timeout: int = 60) -> str:
    """Send a single prompt to the active CLI and return the text response.

    Args:
        prompt: The full prompt text.
        model: Model to use. Defaults to CHEAP_MODEL (for background tasks).
        max_tokens: Max output tokens.
        timeout: Subprocess timeout in seconds.

    Returns:
        The assistant's response text, stripped.
    """
    model = model or CHEAP_MODEL
    cmd = _build_command(prompt, model, max_tokens)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, env=os.environ.copy(),
        )
    except FileNotFoundError:
        raise RuntimeError(f"CLI not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"CLI timed out after {timeout}s")

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "Unknown error").strip()[:300]
        raise RuntimeError(f"CLI failed (exit {result.returncode}): {err}")

    return result.stdout.strip()


def completion_orchestrator(prompt: str, *, max_tokens: int = 4096, timeout: int = 180) -> str:
    """Uses the highest-tier model (Opus/Sonnet) for complex reasoning/code."""
    # current JANE_BRAIN setting usually points to the orchestrator
    return completion(prompt, model=os.environ.get("BRAIN_HEAVY_CLAUDE", "claude-3-6-opus-20260320"), max_tokens=max_tokens, timeout=timeout)


def completion_agent(prompt: str, *, max_tokens: int = 4096, timeout: int = 120) -> str:
    """Uses the Agent-tier model (Sonnet) for specialized research and archival."""
    return completion(prompt, model=SMART_MODEL, max_tokens=max_tokens, timeout=timeout)


def completion_utility(prompt: str, *, max_tokens: int = 1024, timeout: int = 60) -> str:
    """Uses the Utility-tier model (Haiku) for triage and simple tasks."""
    return completion(prompt, model=CHEAP_MODEL, max_tokens=max_tokens, timeout=timeout)


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
