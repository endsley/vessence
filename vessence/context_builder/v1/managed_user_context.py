"""Pure managed-user context formatting helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ManagedUserContext:
    memory_path: str | None
    context_block: str


def build_managed_user_context(
    config: Mapping[str, Any] | None,
    user_id: str,
    available_capabilities: Iterable[Mapping[str, str]],
) -> ManagedUserContext:
    """Build the managed-user runtime block from an already-loaded config."""
    if not config or not config.get("managed"):
        return ManagedUserContext(None, "")

    capability_labels = {cap["id"]: cap["label"] for cap in available_capabilities}
    capabilities = list(config.get("capabilities") or [])
    enabled_labels = [capability_labels.get(cap, cap) for cap in capabilities]
    memory_path = config.get("memory_chromadb_path") if "memory" in capabilities else None
    lines = [
        "## Active Managed User",
        f"User ID: {config.get('user_id') or user_id}",
        f"Display name: {config.get('display_name') or config.get('email') or user_id}",
        "Personal memory scope: private ChromaDB for this user"
        if memory_path
        else "Personal memory scope: disabled for this user",
        "Enabled capabilities: " + (", ".join(enabled_labels) if enabled_labels else "none"),
        (
            "Capability boundary: use only the enabled user-facing capabilities for this user. "
            "If a requested capability is not enabled, say it is not enabled for this user."
        ),
    ]
    return ManagedUserContext(memory_path, "\n".join(lines))
