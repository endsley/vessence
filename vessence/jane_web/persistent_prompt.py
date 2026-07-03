"""Prompt preparation helpers for persistent brain sessions."""

from __future__ import annotations

from collections.abc import Callable


CodeMapLoader = Callable[[str], tuple[str, bool]]


def latest_user_prompt_from_transcript(transcript: str) -> str:
    """Extract the newest user turn from a built Jane transcript."""
    if not transcript:
        return ""
    _prefix, sep, tail = transcript.rpartition("User:")
    prompt = tail if sep else transcript
    for marker in ("\nJane:", "\nAssistant:"):
        marker_idx = prompt.find(marker)
        if marker_idx >= 0:
            prompt = prompt[:marker_idx]
            break
    return prompt.strip().removesuffix("Jane:").strip()


def persistent_turn_prompt(
    *,
    system_prompt: str,
    transcript: str,
    is_fresh: bool,
    code_map_loader: CodeMapLoader,
) -> tuple[str, bool]:
    """Return (prompt_text, code_map_loaded) for a persistent brain turn."""
    if is_fresh:
        return f"{system_prompt}\n\n{transcript}".strip(), False
    if not system_prompt:
        return transcript, False
    prompt_text = latest_user_prompt_from_transcript(transcript)
    return code_map_loader(prompt_text)
