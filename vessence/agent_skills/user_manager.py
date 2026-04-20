"""user_manager.py — Per-user configuration and space management.

Supports multi-user Vessence installations where each user gets their own
config, memory namespace, and personality setting.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import (
    CHROMA_COLLECTION_USER_MEMORIES,
    VESSENCE_DATA_HOME,
    VESSENCE_HOME,
    get_chroma_client,
)

USERS_DIR = Path(VESSENCE_DATA_HOME) / "users"
PERSONALITIES_DIR = Path(VESSENCE_HOME) / "configs" / "personalities"

# Valid personality names (correspond to files in configs/personalities/)
VALID_PERSONALITIES = {"default", "professional", "casual", "technical"}

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
DEFAULT_CAPABILITIES = ["chat", "memory"]


def normalize_user_id(user_id: str) -> str:
    """Normalize session identifiers and emails into stable user directory IDs."""
    value = (user_id or "").strip().lower()
    if not value:
        return "user"
    if "@" in value:
        from vault_web.auth import user_id_from_email
        return user_id_from_email(value)
    return "_".join(value.replace("@", "_at_").replace(".", "_").split())


def _config_path(user_id: str) -> Path:
    return USERS_DIR / normalize_user_id(user_id) / "config.json"


def _memory_path(user_id: str) -> Path:
    return USERS_DIR / normalize_user_id(user_id) / "memory" / "vector_db"


def _vault_path(user_id: str) -> Path:
    return USERS_DIR / normalize_user_id(user_id) / "vault"


def user_config_exists(user_id: str) -> bool:
    return _config_path(user_id).exists()


def is_managed_user(user_id: str) -> bool:
    if not user_config_exists(user_id):
        return False
    try:
        return bool(get_user_config(user_id).get("managed"))
    except Exception:
        return False


def scoped_session_id(user_id: str | None, session_id: str | None) -> str:
    """Namespace conversation state for managed users to prevent cross-user bleed."""
    base = (session_id or "").strip() or "default"
    if user_id and is_managed_user(user_id):
        return f"{normalize_user_id(user_id)}__{base}"
    return base


def get_user_config(user_id: str) -> dict:
    """Get per-user configuration (memory namespace, personality, etc.)."""
    normalized_id = normalize_user_id(user_id)
    config_path = _config_path(normalized_id)
    if config_path.exists():
        config = json.loads(config_path.read_text())
        config.setdefault("user_id", normalized_id)
        config.setdefault("personality", "default")
        config.setdefault("memory_namespace", normalized_id)
        config.setdefault("capabilities", list(DEFAULT_CAPABILITIES))
        config.setdefault("vault_root_path", str(_vault_path(normalized_id)))
        config.setdefault("managed", bool(config.get("memory_chromadb_path")))
        return config
    return {
        "user_id": normalized_id,
        "personality": "default",
        "memory_namespace": normalized_id,
        "capabilities": list(DEFAULT_CAPABILITIES),
        "managed": False,
    }


def _validate_capabilities(capabilities: list[str] | None) -> list[str]:
    valid = {cap["id"] for cap in AVAILABLE_CAPABILITIES}
    requested = capabilities or DEFAULT_CAPABILITIES
    cleaned = []
    for cap in requested:
        if cap in valid and cap not in cleaned:
            cleaned.append(cap)
    return cleaned or list(DEFAULT_CAPABILITIES)


def seed_user_memory(user_id: str, facts: list[str], *, author: str = "jane") -> int:
    """Seed a managed user's private Chroma memory collection."""
    normalized_id = normalize_user_id(user_id)
    cleaned = [fact.strip() for fact in facts if str(fact or "").strip()]
    if not cleaned:
        return 0
    memory_path = _memory_path(normalized_id)
    memory_path.mkdir(parents=True, exist_ok=True)
    client = get_chroma_client(path=str(memory_path))
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_USER_MEMORIES,
        metadata={"hnsw:space": "cosine"},
    )
    now = datetime.now(timezone.utc).isoformat()
    collection.add(
        documents=cleaned,
        ids=[str(uuid.uuid4()) for _ in cleaned],
        metadatas=[
            {
                "user_id": normalized_id,
                "author": author,
                "topic": "user_seed",
                "memory_type": "long_term",
                "timestamp": now,
            }
            for _ in cleaned
        ],
    )
    return len(cleaned)


def create_user_space(
    user_id: str,
    display_name: str,
    *,
    email: str | None = None,
    capabilities: list[str] | None = None,
    seed_memories: list[str] | None = None,
    overwrite: bool = False,
) -> dict:
    """Create per-user directories and config."""
    normalized_id = normalize_user_id(user_id)
    user_dir = USERS_DIR / normalized_id
    memory_path = _memory_path(normalized_id)
    vault_path = _vault_path(normalized_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    memory_path.mkdir(parents=True, exist_ok=True)
    vault_path.mkdir(parents=True, exist_ok=True)
    config_path = user_dir / "config.json"
    if config_path.exists() and not overwrite:
        return get_user_config(normalized_id)

    initial_seeds = [
        f"The active user's display name is {display_name}.",
        "This user has a private Jane memory space separate from other users.",
        "Jane should learn this user's preferences, history, and working context independently.",
    ]
    initial_seeds.extend(seed_memories or [])
    seeded_count = seed_user_memory(normalized_id, initial_seeds)

    config = {
        "user_id": normalized_id,
        "email": (email or "").strip().lower(),
        "display_name": display_name,
        "personality": "default",
        "memory_namespace": normalized_id,
        "memory_chromadb_path": str(memory_path),
        "vault_root_path": str(vault_path),
        "capabilities": _validate_capabilities(capabilities),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seeded_at": datetime.now(timezone.utc).isoformat(),
        "seeded_memory_count": seeded_count,
        "managed": True,
    }
    config_path.write_text(json.dumps(config, indent=2))
    return config


def list_users() -> list[dict]:
    """List managed users with non-sensitive runtime metadata."""
    users = []
    for config_path in sorted(USERS_DIR.glob("*/config.json")):
        try:
            config = json.loads(config_path.read_text())
        except Exception:
            continue
        config.setdefault("user_id", config_path.parent.name)
        config.setdefault("capabilities", list(DEFAULT_CAPABILITIES))
        config.setdefault("managed", bool(config.get("memory_chromadb_path")))
        users.append(config)
    return users


def set_user_personality(user_id: str, personality: str) -> bool:
    """Set a user's personality preference. Returns True on success."""
    if personality not in VALID_PERSONALITIES:
        return False
    config = get_user_config(user_id)
    config["personality"] = personality
    user_dir = USERS_DIR / normalize_user_id(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "config.json").write_text(json.dumps(config, indent=2))
    return True


def get_personality_content(personality: str) -> str:
    """Load the personality markdown file content."""
    if personality not in VALID_PERSONALITIES:
        personality = "default"
    personality_file = PERSONALITIES_DIR / f"{personality}.md"
    if personality_file.exists():
        return personality_file.read_text()
    return ""


def list_personalities() -> list[dict]:
    """List all available personalities with their descriptions."""
    result = []
    for name in sorted(VALID_PERSONALITIES):
        content = get_personality_content(name)
        # First line is the description
        desc = content.split("\n")[0] if content else ""
        result.append({"id": name, "description": desc})
    return result


def ensure_user_space_from_email(email: str, display_name: str | None = None) -> str:
    """Ensure a user space exists for the given email. Returns user_id."""
    from vault_web.auth import user_id_from_email
    user_id = user_id_from_email(email)
    if not display_name:
        display_name = email.split("@")[0]
    create_user_space(user_id, display_name, email=email)
    return user_id
