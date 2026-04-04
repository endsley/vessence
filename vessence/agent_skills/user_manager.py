"""user_manager.py — Per-user configuration and space management.

Supports multi-user Vessence installations where each user gets their own
config, memory namespace, and personality setting.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import VESSENCE_DATA_HOME, VESSENCE_HOME

USERS_DIR = Path(VESSENCE_DATA_HOME) / "users"
PERSONALITIES_DIR = Path(VESSENCE_HOME) / "configs" / "personalities"

# Valid personality names (correspond to files in configs/personalities/)
VALID_PERSONALITIES = {"default", "professional", "casual", "technical"}


def get_user_config(user_id: str) -> dict:
    """Get per-user configuration (memory namespace, personality, etc.)."""
    config_path = USERS_DIR / user_id / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {"personality": "default", "memory_namespace": user_id}


def create_user_space(user_id: str, display_name: str):
    """Create per-user directories and config."""
    user_dir = USERS_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    config_path = user_dir / "config.json"
    if config_path.exists():
        return  # don't overwrite existing config
    config_path.write_text(json.dumps({
        "display_name": display_name,
        "personality": "default",
        "memory_namespace": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))


def set_user_personality(user_id: str, personality: str) -> bool:
    """Set a user's personality preference. Returns True on success."""
    if personality not in VALID_PERSONALITIES:
        return False
    config = get_user_config(user_id)
    config["personality"] = personality
    user_dir = USERS_DIR / user_id
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
    from auth import user_id_from_email
    user_id = user_id_from_email(email)
    if not display_name:
        display_name = email.split("@")[0]
    create_user_space(user_id, display_name)
    return user_id
