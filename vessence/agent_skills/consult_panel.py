#!/usr/bin/env python3
"""consult_panel.py — Multi-model AI consultation tool.

Queries available frontier CLI models (agy, codex, claude) in parallel
for second opinions on architecture decisions, code review, or debugging.

Usage:
    # As a script
    python consult_panel.py "Should I use WebSocket or SSE for streaming?" --caller claude

    # As a library
    from agent_skills.consult_panel import consult_panel
    result = consult_panel("Review this code for bugs", context="def foo(): ...", caller="gemini")

The tool auto-detects which CLIs are installed, skips the caller's own CLI,
skips non-frontier models (e.g., Ollama), and queries peers in parallel.
"""

import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent_skills.consult_panel_helpers import (
    build_consult_prompt as _build_consult_prompt,
    cli_invocation as _cli_invocation,
    prompt_with_context as _prompt_with_context,
    should_consider_cli as _should_consider_cli,
    synthesize_results as _synthesize_results,
)
from agent_skills.cron_token_meter import log_llm_call as _log_llm_call

# Frontier CLIs to consider (name → binary).
# "agy" is Antigravity, Google's successor to the standalone gemini CLI.
FRONTIER_CLIS = {
    "agy": "agy",
    "codex": "codex",
    "claude": "claude",
}

# Skip these — not frontier-tier
SKIP_CLIS = {"ollama"}

# Timeout for each CLI query (seconds)
CLI_TIMEOUT = 600


def detect_available_clis(caller: str = "") -> list[dict]:
    """Detect which frontier CLIs are installed, excluding the caller and skipped CLIs."""
    available = []
    caller_lower = caller.lower().strip()
    for name, binary in FRONTIER_CLIS.items():
        if not _should_consider_cli(name, caller_lower, SKIP_CLIS):
            continue
        path = shutil.which(binary)
        if path:
            available.append({"name": name, "binary": path})
    return available


def query_cli(cli: dict, prompt: str, context: str = "") -> dict:
    """Query a single CLI and return its response."""
    name = cli["name"]
    binary = cli["binary"]
    start = time.perf_counter()
    output = ""
    elapsed = 0.0
    error = None

    full_prompt = _prompt_with_context(prompt, context)

    try:
        env = {**os.environ, "TERM": "dumb"}
        if name in ("agy", "gemini"):
            # Run agy under a minimal HOME so it skips the interactive Jane
            # persona bootstrap and returns a clean opinion (no memory dump).
            from jane.agy_env import agy_headless_home
            env["HOME"] = agy_headless_home()
        invocation = _cli_invocation(name, binary, full_prompt)
        if invocation is None:
            error = f"Unknown CLI: {name}"
            return {"name": name, "error": f"Unknown CLI: {name}", "elapsed": 0}
        result = subprocess.run(
            invocation.argv,
            input=invocation.input_text,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT,
            env=env,
        )

        elapsed = round(time.perf_counter() - start, 1)
        output = result.stdout.strip()
        if result.returncode != 0 and not output:
            output = result.stderr.strip() or f"Exit code {result.returncode}"
            error = output
            return {"name": name, "error": output, "elapsed": elapsed}

        return {"name": name, "response": output, "elapsed": elapsed}

    except subprocess.TimeoutExpired:
        error = f"Timed out after {CLI_TIMEOUT}s"
        return {"name": name, "error": f"Timed out after {CLI_TIMEOUT}s", "elapsed": CLI_TIMEOUT}
    except Exception as e:
        error = str(e)
        return {"name": name, "error": str(e), "elapsed": round(time.perf_counter() - start, 1)}
    finally:
        _log_llm_call(
            provider=name,
            model="",
            prompt_chars=len(full_prompt),
            response_chars=len(output),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            success=error is None,
            phase="consult_panel.query_cli",
            job=os.environ.get("CRON_JOB"),
            error=error,
        )


def synthesize(results: list[dict], caller: str) -> str:
    """Synthesize responses from multiple models into a summary."""
    return _synthesize_results(results, caller)


def consult_panel(
    question: str,
    context: str = "",
    caller: str = "claude",
    mode: str = "review",
) -> str:
    """Main entry point. Query available frontier CLIs and return synthesis.

    Args:
        question: The question or review request
        context: Optional code or additional context
        caller: Who's calling (to exclude from queries)
        mode: "review" (code review), "architecture" (design decision),
              "debug" (debugging help), "test" (generate tests)
    """
    available = detect_available_clis(caller)

    if not available:
        return "No peer frontier CLIs detected on this machine. Proceeding solo."

    full_question = _build_consult_prompt(question, mode)

    # Query all peers in parallel
    results = []
    with ThreadPoolExecutor(max_workers=len(available)) as executor:
        futures = {
            executor.submit(query_cli, cli, full_question, context): cli
            for cli in available
        }
        for future in as_completed(futures):
            results.append(future.result())

    return synthesize(results, caller)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Consult AI peer panel")
    parser.add_argument("question", nargs="?", default="", help="The question or review request")
    parser.add_argument("--context", "-c", default="", help="Code or context to include")
    parser.add_argument("--files", "-f", nargs="*", default=[], help="File paths to include as context")
    parser.add_argument("--caller", default="claude", help="Who's calling (excluded from queries)")
    parser.add_argument("--mode", default="review", choices=["review", "architecture", "debug", "test"])
    parser.add_argument("--list", action="store_true", help="Just list available CLIs")
    args = parser.parse_args()

    if args.list:
        available = detect_available_clis(args.caller)
        if available:
            print(f"Available peer CLIs (excluding {args.caller}):")
            for cli in available:
                print(f"  - {cli['name']} ({cli['binary']})")
        else:
            print("No peer frontier CLIs detected.")
        sys.exit(0)

    # Build context from --context and/or --files
    context_parts = []
    if args.context:
        context_parts.append(args.context)
    for fpath in args.files:
        try:
            with open(fpath) as f:
                content = f.read()
            context_parts.append(f"--- {fpath} ---\n{content}")
        except Exception as e:
            context_parts.append(f"--- {fpath} --- (error: {e})")
    full_context = "\n\n".join(context_parts)

    result = consult_panel(args.question, full_context, args.caller, args.mode)
    print(result)
