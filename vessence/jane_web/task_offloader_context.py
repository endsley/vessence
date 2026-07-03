"""Context selection helpers for task_offloader.py."""

from __future__ import annotations

from typing import Any


def automation_prompt_context(message: str, context: Any) -> tuple[str, str]:
    system_prompt = getattr(context, "system_prompt", "") or ""
    transcript = getattr(context, "transcript", "") or ""
    prompt_text = transcript if transcript else message
    return prompt_text, system_prompt
