"""Managed user vault, capability, and public config helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from fastapi import HTTPException

UserVaultContext = tuple[str, list[str], bool, str]
UserManagerLoader = Callable[
    [],
    tuple[
        Sequence[Mapping[str, Any]],
        Callable[[str], Mapping[str, Any]],
        Callable[[str], bool],
    ],
]
AdminUserManagerLoader = Callable[[], tuple[Callable[[str], Mapping[str, Any]], Callable[[str], bool]]]


def load_admin_user_manager():
    from agent_skills.user_manager import get_user_config, user_config_exists

    return get_user_config, user_config_exists


def load_user_manager():
    from agent_skills.user_manager import AVAILABLE_CAPABILITIES, get_user_config, is_managed_user

    return AVAILABLE_CAPABILITIES, get_user_config, is_managed_user


def user_vault_context(
    session_id: str | None,
    *,
    vault_dir: str | Any,
    get_session_user_fn: Callable[[str | None], str | None],
    default_user_id_fn: Callable[[], str],
    user_manager_loader: UserManagerLoader = load_user_manager,
) -> UserVaultContext:
    """Return (vault_root, capabilities, is_managed, user_id) for a session."""

    user_id = (get_session_user_fn(session_id) if session_id else None) or default_user_id_fn()
    try:
        available_capabilities, get_user_config, is_managed_user = user_manager_loader()
    except Exception:
        return str(vault_dir), [], False, user_id

    all_caps = [cap["id"] for cap in available_capabilities]
    if not is_managed_user(user_id):
        return str(vault_dir), all_caps, False, user_id

    config = get_user_config(user_id)
    vault_root = config.get("vault_root_path") or str(vault_dir)
    caps = list(config.get("capabilities") or [])
    return vault_root, caps, True, user_id


def require_capability(
    session_id: str | None,
    cap: str,
    *,
    context_resolver: Callable[[str | None], UserVaultContext],
) -> UserVaultContext:
    """Ensure a managed user has a required capability."""

    vault_root, caps, is_managed, user_id = context_resolver(session_id)
    if is_managed and cap not in caps:
        raise HTTPException(status_code=403, detail=f"Missing capability: {cap}")
    return vault_root, caps, is_managed, user_id


def request_vault_root(
    request: Any,
    *,
    vault_dir: str | Any,
    get_session_id_fn: Callable[[Any], str | None],
    context_resolver: Callable[[str | None], UserVaultContext],
) -> str:
    """Return the request's vault root, falling back to the global vault."""

    try:
        session_id = get_session_id_fn(request)
        vault_root, _caps, _managed, _uid = context_resolver(session_id)
        return vault_root
    except Exception:
        return str(vault_dir)


def user_memory_path(
    user_id: str | None,
    *,
    user_manager_loader: UserManagerLoader = load_user_manager,
) -> str:
    """Return the managed user's private ChromaDB path, or empty for legacy global memory."""

    if not user_id:
        return ""
    try:
        _available_capabilities, get_user_config, is_managed_user = user_manager_loader()
        if not is_managed_user(user_id):
            return ""
        config = get_user_config(user_id)
        return config.get("memory_chromadb_path") or ""
    except Exception:
        return ""


def public_user_config(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "user_id": config.get("user_id"),
        "email": config.get("email", ""),
        "display_name": config.get("display_name", ""),
        "personality": config.get("personality", "default"),
        "memory_namespace": config.get("memory_namespace", config.get("user_id", "")),
        "memory_chromadb_path": config.get("memory_chromadb_path", ""),
        "vault_root_path": config.get("vault_root_path", ""),
        "capabilities": config.get("capabilities", []),
        "created_at": config.get("created_at", ""),
        "seeded_memory_count": config.get("seeded_memory_count", 0),
    }


def normalize_managed_user_email(email: str | None) -> str:
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    return normalized


def managed_user_display_name(display_name: str | None, email: str) -> str:
    return (display_name or "").strip() or email.split("@", 1)[0]


def clean_seed_memories(seed_memories: Sequence[Any] | None) -> list[str]:
    return [memory.strip() for memory in (seed_memories or []) if str(memory or "").strip()]


def is_user_admin(
    user_id: str | None,
    *,
    identity_variants_fn: Callable[[str | None], set[str]],
    configured_admin_variants_fn: Callable[[], set[str]],
    admin_user_manager_loader: AdminUserManagerLoader = load_admin_user_manager,
    logger: Any = None,
) -> bool:
    variants = identity_variants_fn(user_id)
    if variants & configured_admin_variants_fn():
        return True

    lookup_id = user_id or ""
    try:
        get_user_config, user_config_exists = admin_user_manager_loader()
        if user_config_exists(lookup_id):
            config = get_user_config(lookup_id)
            return "user_admin" in (config.get("capabilities") or [])
    except Exception:
        if logger is not None:
            logger.exception("Failed checking user_admin capability for %s", user_id)
    return False
