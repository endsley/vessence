"""Pure parsing helpers for the essence builder interview."""

from __future__ import annotations

import re


KNOWN_SHARED_SKILLS = [
    "memory_read_write",
    "file_handling",
    "tts",
    "web_search",
    "screen_control",
    "microphone",
    "clipboard",
]

UI_TYPE_CANDIDATES = ("hybrid", "dashboard", "form_wizard", "card_grid", "chat")

KNOWN_PERMISSIONS = [
    "internet",
    "file_system",
    "clipboard",
    "microphone",
    "camera",
    "screen_control",
]

KNOWN_MODELS = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku",
    "gpt-4o",
    "gpt-4",
    "gemini-flash",
    "gemini-pro",
]


def extract_role_title(text: str) -> str:
    """Try to extract a role title like 'the accountant' from free text."""
    lower = text.lower()
    for marker in ("role title:", "role:", "title:"):
        if marker in lower:
            idx = lower.index(marker) + len(marker)
            fragment = text[idx:].strip().split("\n")[0].strip().rstrip(".")
            if fragment:
                frag = fragment.strip("'\"")
                if not frag.lower().startswith("the "):
                    frag = f"the {frag}"
                return frag

    match = re.search(r"\bthe\s+(\w+)", lower)
    if match:
        return f"the {match.group(1)}"
    return "the specialist"


def extract_list_from_answer(text: str, keyword: str) -> list[str]:
    """Extract a comma-separated or bullet list of items near a keyword."""
    items = []
    for line in text.split("\n"):
        lower = line.lower()
        if keyword in lower:
            after = line.split(":", 1)[-1] if ":" in line else line
            parts = [p.strip().strip("-•*").strip() for p in after.split(",")]
            items.extend(p for p in parts if p and len(p) < 80)

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("-", "*", "•")):
            item = stripped.lstrip("-*• ").strip()
            if item and len(item) < 80 and item not in items:
                items.append(item)
    return items if items else []


def extract_quoted_strings(text: str) -> list[str]:
    """Extract strings enclosed in quotes, or bullet items."""
    quoted = re.findall(r'["\']([^"\']{5,})["\']', text)
    if quoted:
        return quoted[:6]

    items = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("-", "*", "•", "1", "2", "3", "4")):
            item = stripped.lstrip("-*•0123456789. ").strip()
            if item and len(item) > 4:
                items.append(item)
    return items[:6] if items else []


def extract_section_fragment(text: str, keyword: str) -> str:
    """Extract lines from text that relate to a keyword."""
    lines = []
    for line in text.split("\n"):
        if keyword in line.lower():
            lines.append(f"- {line.strip()}")
    if lines:
        return "\n".join(lines)
    return "- (To be refined based on interview answers)"


def select_shared_skills(skills_answer: str) -> list[str]:
    normalized = skills_answer.lower().replace(" ", "_")
    return [skill for skill in KNOWN_SHARED_SKILLS if skill in normalized]


def candidate_mentioned(answer: str, candidate: str) -> bool:
    return candidate.replace("_", " ") in answer or candidate in answer


def select_ui_type(ui_answer: str) -> str:
    answer = ui_answer.lower()
    for candidate in UI_TYPE_CANDIDATES:
        if candidate_mentioned(answer, candidate):
            return candidate
    return "chat"


def select_permissions(permissions_answer: str) -> list[str]:
    answer = permissions_answer.lower()
    return [
        permission
        for permission in KNOWN_PERMISSIONS
        if candidate_mentioned(answer, permission)
    ]


def extract_model_id(model_answer: str, default: str = "claude-sonnet-4-6") -> str:
    normalized = model_answer.lower().replace(" ", "-")
    for known_model in KNOWN_MODELS:
        if known_model in normalized:
            return known_model
    return default


def trigger_list_from_answer(triggers_answer: str) -> list[dict[str, str]]:
    stripped = triggers_answer.strip()
    if stripped and stripped.lower() not in ("none", "n/a", "no"):
        return [{
            "condition": "custom",
            "description": stripped,
        }]
    return []


def credentials_from_answer(credentials_answer: str) -> list[dict[str, object]]:
    answer = credentials_answer.lower()
    if "api" in answer or "key" in answer or "credential" in answer:
        return [{
            "name": "CUSTOM_API_KEY",
            "description": credentials_answer.strip(),
            "required": "required" in answer,
        }]
    return []


def sanitize_essence_folder_name(essence_name: str) -> str:
    folder_name = essence_name.lower().replace(" ", "_").replace("-", "_")
    folder_name = "".join(c for c in folder_name if c.isalnum() or c == "_")
    return folder_name or "new_essence"
