#!/usr/bin/env python3
"""consult_panel.py — Multi-model AI consultation tool.

Queries available frontier CLI models (gemini, codex, claude) in parallel
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

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Frontier CLIs to consider (name → binary)
FRONTIER_CLIS = {
    "gemini": "gemini",
    "codex": "codex",
    "claude": "claude",
}

# Skip these — not frontier-tier
SKIP_CLIS = {"ollama"}

# Timeout for each CLI query (seconds)
CLI_TIMEOUT = 120


def detect_available_clis(caller: str = "") -> list[dict]:
    """Detect which frontier CLIs are installed, excluding the caller and skipped CLIs."""
    available = []
    caller_lower = caller.lower().strip()
    for name, binary in FRONTIER_CLIS.items():
        if name == caller_lower:
            continue
        if name in SKIP_CLIS:
            continue
        path = shutil.which(binary)
        if path:
            available.append({"name": name, "binary": path})
    return available


def query_cli(cli: dict, prompt: str, context: str = "") -> dict:
    """Query a single CLI and return its response."""
    name = cli["name"]
    binary = cli["binary"]
    start = time.time()

    full_prompt = prompt
    if context:
        full_prompt = f"{prompt}\n\n---\nContext:\n{context}"

    try:
        env = {**os.environ, "TERM": "dumb"}
        # Use stdin for large prompts to avoid ARG_MAX limits
        use_stdin = len(full_prompt) > 4000

        if name == "gemini":
            if use_stdin:
                result = subprocess.run(
                    [binary], input=full_prompt,
                    capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
                )
            else:
                result = subprocess.run(
                    [binary, "-p", full_prompt],
                    capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
                )
        elif name == "codex":
            if use_stdin:
                result = subprocess.run(
                    [binary, "exec", "-"], input=full_prompt,
                    capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
                )
            else:
                result = subprocess.run(
                    [binary, "exec", full_prompt],
                    capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
                )
        elif name == "claude":
            if use_stdin:
                result = subprocess.run(
                    [binary, "-p", "-", "--output-format", "text"], input=full_prompt,
                    capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
                )
            else:
                result = subprocess.run(
                    [binary, "-p", full_prompt, "--output-format", "text"],
                    capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
                )
        else:
            return {"name": name, "error": f"Unknown CLI: {name}", "elapsed": 0}

        elapsed = round(time.time() - start, 1)
        output = result.stdout.strip()
        if result.returncode != 0 and not output:
            output = result.stderr.strip() or f"Exit code {result.returncode}"
            return {"name": name, "error": output, "elapsed": elapsed}

        return {"name": name, "response": output, "elapsed": elapsed}

    except subprocess.TimeoutExpired:
        return {"name": name, "error": f"Timed out after {CLI_TIMEOUT}s", "elapsed": CLI_TIMEOUT}
    except Exception as e:
        return {"name": name, "error": str(e), "elapsed": round(time.time() - start, 1)}


def synthesize(results: list[dict], caller: str) -> str:
    """Synthesize responses from multiple models into a summary."""
    successful = [r for r in results if "response" in r]
    failed = [r for r in results if "error" in r]

    if not successful:
        return "No peer models responded. Proceeding with own judgment."

    lines = []
    lines.append(f"## AI Panel Consultation (called by {caller})")
    lines.append("")

    for r in successful:
        lines.append(f"### {r['name'].title()} ({r['elapsed']}s)")
        lines.append(r["response"])
        lines.append("")

    if failed:
        lines.append("### Unavailable")
        for r in failed:
            lines.append(f"- {r['name']}: {r['error']}")
        lines.append("")

    # Agreement analysis
    if len(successful) >= 2:
        lines.append("### Synthesis")
        lines.append(f"Received {len(successful)} peer opinion(s). Review agreements and disagreements above.")
        lines.append("")

    return "\n".join(lines)


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

    # Build the prompt based on mode
    mode_prefix = {
        "review": "You are reviewing code written by another AI. Be critical and thorough. Point out bugs, edge cases, missing features, and security issues. Also check: 1) Are all external files/downloads verified as real (not HTML error pages or truncated)? 2) What could fail silently — working app but broken feature? 3) Review the full pipeline, not just logic. 4) Who else calls this code? Trace all callers — a class created in one place may also be created elsewhere. 5) What happens on rapid toggle/restart? Check teardown ordering — threads must be joined before closing resources they use. 6) Test the happy path mentally: if a user does X, does the code actually work end-to-end? Be concise.",
        "architecture": "You are reviewing an architecture decision. Evaluate the tradeoffs, suggest alternatives if better ones exist, and flag risks. Be concise.",
        "debug": "Another AI is stuck debugging this issue. Provide fresh analysis and suggest what they might be missing. Be concise.",
        "test": "Write tests for the following code. Focus on edge cases, error conditions, and scenarios the author might have missed. Be concise.",
    }.get(mode, "")

    full_question = f"{mode_prefix}\n\n{question}" if mode_prefix else question

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
