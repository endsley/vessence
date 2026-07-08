"""Prompt and decision helpers for conversation archival."""

from __future__ import annotations

import re
from collections.abc import Iterable


TRIAGE_NOISE_PATTERNS = (
    r"^User logged in with Google account.*",
    r"^System in 'Waiting for auth' state.*",
    r"^User interface ready for interaction.*",
    r"^Deprecation warning for --allowed-tools.*",
    r"^Automatic Gemini CLI update.*",
    r"^Gemini CLI update available.*",
    r"^What does Jane web streaming mean\?.*",
    r"^User interface includes YOLO shortcut.*",
    r"^No relevant context found.*",
    r"^jane you still thinking\?.*",
    r"^jane/.*",
)

TRIAGE_DECISIONS = {"Keep", "Forgettable", "Discard"}


def triage_prefilter_decision(memory_content: str) -> str | None:
    text = str(memory_content or "").strip()
    for pattern in TRIAGE_NOISE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "Discard"
    return None


def archivist_triage_prompt(memory_content: str) -> str:
    return (
        "You are The Archivist. Respond with ONLY one word: 'Keep', 'Forgettable', or 'Discard'.\n\n"
        "Rules:\n"
        "- Keep: permanent-ish facts — user-specific details (family, profession, preferences), "
        "architecture changes, project goals, fixed root causes, and hard-won implementation "
        "knowledge. If it's something the user explicitly wants me to remember, classify it as Keep.\n"
        "- Forgettable: temporary context — current session progress, recent code changes, "
        "bugs just fixed, test results. These will expire after about one month.\n"
        "- Discard: noise, greetings, trivial state updates (e.g., 'system ready', 'login successful'), "
        "filler, and redundant repetition of things I already know.\n\n"
        "BE RUTHLESS. When in doubt, Discard or Forgettable. Only Keep durable, high-value knowledge.\n\n"
        f"Memory: {memory_content}"
    )


def normalize_triage_decision(decision: str) -> str:
    return decision if decision in TRIAGE_DECISIONS else "Retry"


def conversation_summary_prompt(content: str) -> str:
    return (
        "You are a summarizer. Output ONLY a concise factual summary "
        "of the conversation below. Do NOT respond to the content, "
        "do NOT ask questions, do NOT ask for clarification, do NOT "
        "include system metadata or protocol descriptions. Just "
        "summarize what the user and assistant discussed: topics, "
        "decisions, and outcomes. Neutral, 3rd person, 2-4 sentences "
        "max.\n\n" + content
    )


def should_reject_generated_summary(summary: str, bad_patterns: Iterable[str]) -> bool:
    summary_lower = summary.lower()
    return any(pattern.lower() in summary_lower for pattern in bad_patterns)


def should_wait_for_smart_archival(
    *,
    current_hour: int,
    idle_seconds: float,
    smart_after_hour: int,
    smart_idle_seconds: float,
) -> bool:
    return current_hour >= smart_after_hour and idle_seconds < smart_idle_seconds


def select_archivist_model(
    *,
    current_hour: int,
    idle_seconds: float,
    smart_after_hour: int,
    smart_idle_seconds: float,
    default_model: str,
    smart_model: str,
) -> str:
    if current_hour >= smart_after_hour and idle_seconds >= smart_idle_seconds:
        return smart_model
    return default_model
