"""Pure prompt, command, and synthesis helpers for consult_panel.py."""

from __future__ import annotations

from dataclasses import dataclass


STDIN_PROMPT_THRESHOLD = 4000

MODE_PREFIXES = {
    "review": "You are reviewing code written by another AI. Be critical and thorough. Point out bugs, edge cases, missing features, and security issues. Also check: 1) Are all external files/downloads verified as real (not HTML error pages or truncated)? 2) What could fail silently — working app but broken feature? 3) Review the full pipeline, not just logic. 4) Who else calls this code? Trace all callers — a class created in one place may also be created elsewhere. 5) What happens on rapid toggle/restart? Check teardown ordering — threads must be joined before closing resources they use. 6) Test the happy path mentally: if a user does X, does the code actually work end-to-end? Be concise.",
    "architecture": "You are reviewing an architecture decision. Evaluate the tradeoffs, suggest alternatives if better ones exist, and flag risks. Be concise.",
    "debug": "Another AI is stuck debugging this issue. Provide fresh analysis and suggest what they might be missing. Be concise.",
    "test": "Write tests for the following code. Focus on edge cases, error conditions, and scenarios the author might have missed. Be concise.",
}


@dataclass(frozen=True)
class CliInvocation:
    argv: list[str]
    input_text: str | None = None


def should_consider_cli(name: str, caller: str, skip_clis: set[str]) -> bool:
    return name != caller.lower().strip() and name not in skip_clis


def prompt_with_context(prompt: str, context: str = "") -> str:
    if context:
        return f"{prompt}\n\n---\nContext:\n{context}"
    return prompt


def should_use_stdin(prompt: str, threshold: int = STDIN_PROMPT_THRESHOLD) -> bool:
    return len(prompt) > threshold


def cli_invocation(name: str, binary: str, full_prompt: str) -> CliInvocation | None:
    use_stdin = should_use_stdin(full_prompt)
    if name == "gemini":
        if use_stdin:
            return CliInvocation([binary], full_prompt)
        return CliInvocation([binary, "-p", full_prompt])
    if name == "codex":
        if use_stdin:
            return CliInvocation([binary, "exec", "-"], full_prompt)
        return CliInvocation([binary, "exec", full_prompt])
    if name == "claude":
        if use_stdin:
            return CliInvocation(
                [binary, "-p", "-", "--output-format", "text"],
                full_prompt,
            )
        return CliInvocation([binary, "-p", full_prompt, "--output-format", "text"])
    return None


def build_consult_prompt(question: str, mode: str = "review") -> str:
    mode_prefix = MODE_PREFIXES.get(mode, "")
    return f"{mode_prefix}\n\n{question}" if mode_prefix else question


def synthesize_results(results: list[dict], caller: str) -> str:
    successful = [r for r in results if "response" in r]
    failed = [r for r in results if "error" in r]

    if not successful:
        return "No peer models responded. Proceeding with own judgment."

    lines = []
    lines.append(f"## AI Panel Consultation (called by {caller})")
    lines.append("")

    for result in successful:
        lines.append(f"### {result['name'].title()} ({result['elapsed']}s)")
        lines.append(result["response"])
        lines.append("")

    if failed:
        lines.append("### Unavailable")
        for result in failed:
            lines.append(f"- {result['name']}: {result['error']}")
        lines.append("")

    if len(successful) >= 2:
        lines.append("### Synthesis")
        lines.append(
            f"Received {len(successful)} peer opinion(s). "
            "Review agreements and disagreements above."
        )
        lines.append("")

    return "\n".join(lines)
