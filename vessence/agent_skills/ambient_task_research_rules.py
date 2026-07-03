"""Pure task-selection rules for ambient_task_research.py."""
from __future__ import annotations

import datetime
import re


_PROGRESS_TRACKER_RE = re.compile(
    r"^##\s+(?:\d+\.\s*)?Progress Tracker\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def extract_unchecked_tasks_from_text(content: str) -> list[dict]:
    """
    Parse a spec's Progress Tracker and return unchecked tasks with phase labels.

    Supports both numbered headings such as "## 11. Progress Tracker" and
    unnumbered headings such as "## Progress Tracker".
    """
    tracker_match = _PROGRESS_TRACKER_RE.search(content)
    if tracker_match is None:
        return []

    tracker_content = content[tracker_match.start():]
    tasks = []
    current_phase = "Unknown Phase"

    for line in tracker_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            current_phase = stripped.lstrip("#").strip()
        elif stripped.startswith("- [ ]"):
            task_text = stripped[6:].strip()
            if task_text:
                tasks.append({"phase": current_phase, "task": task_text})

    return tasks


def task_cache_key(task: str) -> str:
    """Stable cache key from task text."""
    return task.lower().replace(" ", "_").replace("/", "_")[:80]


def is_cache_stale(
    cache: dict,
    key: str,
    *,
    ttl_days: int = 7,
    now: datetime.datetime | None = None,
) -> bool:
    if key not in cache:
        return True
    try:
        last = datetime.datetime.fromisoformat(cache[key]["last_researched"])
        current = now or datetime.datetime.now()
        return (current - last).days >= ttl_days
    except Exception:
        return True


def build_search_query(phase: str, task: str) -> str:
    """
    Generate a targeted search query for how others have implemented this task.
    Adds Flutter / cross-platform context where relevant.
    """
    task_lower = task.lower()

    context = "Flutter cross-platform"
    if any(k in task_lower for k in ["sqlite", "sqflite", "database", "persistence", "history"]):
        context = "Flutter SQLite"
    elif any(k in task_lower for k in ["stream", "sse", "server-sent"]):
        context = "Flutter SSE streaming ADK"
    elif any(k in task_lower for k in ["markdown", "code block", "syntax highlight"]):
        context = "Flutter markdown rendering"
    elif any(k in task_lower for k in ["tts", "speech", "voice", "audio", "whisper", "vad"]):
        context = "Python TTS voice assistant"
    elif any(k in task_lower for k in ["tailscale", "remote", "vpn", "tunnel"]):
        context = "Tailscale self-hosted remote access"
    elif any(k in task_lower for k in ["wake word", "porcupine", "standby"]):
        context = "Picovoice Porcupine wake word Python"
    elif any(k in task_lower for k in ["android", "apk"]):
        context = "Flutter Android"
    elif any(k in task_lower for k in ["linux", "desktop"]):
        context = "Flutter Linux desktop"
    elif any(k in task_lower for k in ["notification", "push"]):
        context = "Flutter push notifications"
    elif any(k in task_lower for k in ["auth", "invite", "user", "register"]):
        context = "FastAPI user authentication"
    elif any(k in task_lower for k in ["theme", "dark", "color"]):
        context = "Flutter dark theme ChatGPT UI"

    return f"{context} {task} implementation tutorial 2024 2025"


def openai_synthesis_messages(phase: str, task: str, web_data: str) -> list[dict[str, str]]:
    """
    Build the OpenAI chat messages used to synthesize task research notes.
    """
    system = (
        "You are a Senior Software Engineer advising on 'Project Ambient' — "
        "a cross-platform Flutter app (Linux, Windows, Android, macOS) that provides "
        "a ChatGPT-like interface to a local Google ADK AI server (Amber, running at localhost:8000). "
        "Your job: given a specific development task, explain how others have implemented this "
        "and give a concrete, actionable approach for this project. "
        "Be specific: include package names, versions, code patterns, and pitfalls to avoid. "
        "Format in clean Markdown. Keep it under 400 words."
    )
    web_section = f"\n\nWeb search results:\n{web_data[:6000]}" if web_data else ""
    user_msg = (
        f"Phase: {phase}\n"
        f"Task: {task}\n\n"
        f"How have others implemented this? What's the best approach for our project?{web_section}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def task_research_discord_summary(
    researched: list[dict],
    *,
    total_tasks: int,
    generated_label: str,
    cache_path: str,
) -> str:
    lines = [f"🔬 **Ambient Task Research** ({generated_label})"]
    lines.append(f"Researched **{len(researched)}/{total_tasks} tasks** remaining in the spec.\n")

    for item in researched:
        note_preview = "\n".join(str(item["note"]).splitlines()[:3])
        lines.append(f"**[{item['phase']}]** `{item['task']}`")
        lines.append(f"> {note_preview[:200]}")
        lines.append("")

    lines.append(f"_Full notes in `{cache_path}`_")
    return "\n".join(lines)
