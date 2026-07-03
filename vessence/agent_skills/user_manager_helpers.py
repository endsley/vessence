"""Pure helpers for user_manager.py."""

from __future__ import annotations

from typing import Any


AVAILABLE_CAPABILITIES = [
    {"id": "chat", "label": "Talk to Jane"},
    {"id": "memory", "label": "Personal memory"},
    {"id": "vault_read", "label": "Read vault files"},
    {"id": "vault_write", "label": "Upload and edit vault files"},
    {"id": "email", "label": "Email tools"},
    {"id": "calendar", "label": "Calendar tools"},
    {"id": "phone", "label": "Phone and SMS tools"},
    {"id": "web_search", "label": "Web search"},
    {"id": "code_assistant", "label": "Code assistant"},
    {"id": "essences", "label": "Essences"},
    {"id": "user_admin", "label": "Create users"},
]
DEFAULT_CAPABILITIES = ["chat", "memory", "vault_read", "vault_write"]


def normalize_plain_user_id(user_id: str) -> str:
    value = (user_id or "").strip().lower()
    if not value:
        return "user"
    return "_".join(value.replace("@", "_at_").replace(".", "_").split())


def validate_capabilities(capabilities: list[str] | None) -> list[str]:
    valid = {capability["id"] for capability in AVAILABLE_CAPABILITIES}
    requested = capabilities or DEFAULT_CAPABILITIES
    cleaned = []
    for capability in requested:
        if capability in valid and capability not in cleaned:
            cleaned.append(capability)
    return cleaned or list(DEFAULT_CAPABILITIES)


def default_user_config(normalized_id: str) -> dict[str, Any]:
    return {
        "user_id": normalized_id,
        "personality": "default",
        "memory_namespace": normalized_id,
        "capabilities": list(DEFAULT_CAPABILITIES),
        "managed": False,
    }


def config_with_defaults(
    config: dict[str, Any],
    normalized_id: str,
    vault_root_path: str,
) -> dict[str, Any]:
    config.setdefault("user_id", normalized_id)
    config.setdefault("personality", "default")
    config.setdefault("memory_namespace", normalized_id)
    config.setdefault("capabilities", list(DEFAULT_CAPABILITIES))
    config.setdefault("vault_root_path", vault_root_path)
    config.setdefault("managed", bool(config.get("memory_chromadb_path")))
    return config


def initial_seed_facts(display_name: str, seed_memories: list[str] | None = None) -> list[str]:
    seeds = [
        f"The active user's display name is {display_name}.",
        "This user has a private Jane memory space separate from other users.",
        "Jane should learn this user's preferences, history, and working context independently.",
    ]
    seeds.extend(seed_memories or [])
    return seeds


def personality_description(content: str) -> str:
    return content.split("\n")[0] if content else ""
