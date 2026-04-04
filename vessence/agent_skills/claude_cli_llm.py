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


def completion_smart(prompt: str, *, max_tokens: int = 4096, timeout: int = 120) -> str:
    """Like completion() but uses the SMART model (for user-facing tasks)."""
    return completion(prompt, model=SMART_MODEL, max_tokens=max_tokens, timeout=timeout)


def completion_json(prompt: str, *, timeout: int = 120) -> dict:
    """Send a prompt expecting JSON output. Uses CHEAP model. Parses and returns dict."""
    text = completion(prompt, max_tokens=4096, timeout=timeout)
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
