from context_builder.v1 import context_builder
from context_builder.v1.managed_user_context import (
    ManagedUserContext,
    build_managed_user_context,
)


def test_context_builder_uses_managed_user_context_helper():
    assert context_builder._build_managed_user_context is build_managed_user_context


def test_build_managed_user_context_formats_labels_and_memory_scope():
    result = build_managed_user_context(
        {
            "managed": True,
            "user_id": "child",
            "display_name": "Child User",
            "email": "child@example.com",
            "capabilities": ["memory", "phone", "custom"],
            "memory_chromadb_path": "/tmp/user-memory",
        },
        "fallback",
        [
            {"id": "memory", "label": "Personal memory"},
            {"id": "phone", "label": "Phone and SMS tools"},
        ],
    )

    assert result.memory_path == "/tmp/user-memory"
    assert result.context_block == (
        "## Active Managed User\n"
        "User ID: child\n"
        "Display name: Child User\n"
        "Personal memory scope: private ChromaDB for this user\n"
        "Enabled capabilities: Personal memory, Phone and SMS tools, custom\n"
        "Capability boundary: use only the enabled user-facing capabilities for this user. "
        "If a requested capability is not enabled, say it is not enabled for this user."
    )


def test_build_managed_user_context_disables_memory_without_memory_capability():
    result = build_managed_user_context(
        {
            "managed": True,
            "email": "child@example.com",
            "capabilities": [],
            "memory_chromadb_path": "/tmp/user-memory",
        },
        "fallback",
        [{"id": "memory", "label": "Personal memory"}],
    )

    assert result.memory_path is None
    assert "Display name: child@example.com" in result.context_block
    assert "Personal memory scope: disabled for this user" in result.context_block
    assert "Enabled capabilities: none" in result.context_block


def test_build_managed_user_context_ignores_unmanaged_config():
    assert build_managed_user_context(
        {"managed": False, "capabilities": ["memory"], "memory_chromadb_path": "/tmp/user-memory"},
        "fallback",
        [{"id": "memory", "label": "Personal memory"}],
    ) == ManagedUserContext(None, "")
