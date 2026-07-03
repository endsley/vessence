"""Recent conversation transcript formatting helpers."""

from __future__ import annotations


def format_recent_history(history: list[dict], max_turns: int = 6, max_chars: int = 2400) -> str:
    if not history:
        return ""

    recent = history[-max_turns:]
    lines: list[str] = []
    remaining = max_chars

    for entry in recent:
        role = str(entry.get("role", "user")).strip().lower()
        content = " ".join(str(entry.get("content", "")).split()).strip()
        if not content:
            continue

        speaker = "Jane" if role == "assistant" else "User"
        line = f"{speaker}: {content}"
        if len(line) > remaining:
            if remaining <= len(speaker) + 2:
                break
            line = line[: remaining - 1].rstrip() + "..."
        lines.append(line)
        remaining -= len(line) + 1
        if remaining <= 0:
            break

    return "\n".join(lines).strip()


def build_user_transcript(message: str, recent_history: str) -> str:
    user_sections: list[str] = []
    if recent_history:
        user_sections.append(f"Recent Conversation:\n{recent_history}")
    user_sections.extend([f"User: {message}", "Jane:"])
    return "\n\n".join(user_sections).strip()
