from pathlib import Path

import pytest
from fastapi import HTTPException

from jane_web.user_access import (
    is_user_admin,
    public_user_config,
    request_vault_root,
    require_capability,
    user_memory_path,
    user_vault_context,
)


def _loader(*, managed_users=frozenset(), configs=None, capabilities=None):
    configs = configs or {}
    capabilities = capabilities or [{"id": "vault_read"}, {"id": "phone"}]

    def get_user_config(user_id):
        return configs[user_id]

    def is_managed_user(user_id):
        return user_id in managed_users

    return lambda: (capabilities, get_user_config, is_managed_user)


def test_user_vault_context_falls_back_when_user_manager_import_fails():
    def broken_loader():
        raise RuntimeError("missing user manager")

    context = user_vault_context(
        "session-1",
        vault_dir=Path("/vault"),
        get_session_user_fn=lambda session_id: "session-user",
        default_user_id_fn=lambda: "default-user",
        user_manager_loader=broken_loader,
    )

    assert context == ("/vault", [], False, "session-user")


def test_user_vault_context_grants_all_caps_to_unmanaged_users():
    context = user_vault_context(
        None,
        vault_dir="/vault",
        get_session_user_fn=lambda session_id: None,
        default_user_id_fn=lambda: "default-user",
        user_manager_loader=_loader(),
    )

    assert context == ("/vault", ["vault_read", "phone"], False, "default-user")


def test_user_vault_context_uses_managed_vault_and_capabilities():
    context = user_vault_context(
        "session-1",
        vault_dir="/vault",
        get_session_user_fn=lambda session_id: "child",
        default_user_id_fn=lambda: "default-user",
        user_manager_loader=_loader(
            managed_users={"child"},
            configs={
                "child": {
                    "vault_root_path": "/private/child",
                    "capabilities": ["vault_read"],
                }
            },
        ),
    )

    assert context == ("/private/child", ["vault_read"], True, "child")


def test_require_capability_only_blocks_missing_capability_for_managed_users():
    unmanaged = lambda session_id: ("/vault", [], False, "owner")
    assert require_capability("session-1", "phone", context_resolver=unmanaged) == (
        "/vault",
        [],
        False,
        "owner",
    )

    managed = lambda session_id: ("/private", ["vault_read"], True, "child")
    with pytest.raises(HTTPException) as exc:
        require_capability("session-1", "phone", context_resolver=managed)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Missing capability: phone"


def test_request_vault_root_returns_context_root_or_global_fallback():
    assert (
        request_vault_root(
            object(),
            vault_dir="/vault",
            get_session_id_fn=lambda request: "session-1",
            context_resolver=lambda session_id: ("/private", [], True, "child"),
        )
        == "/private"
    )

    assert (
        request_vault_root(
            object(),
            vault_dir="/vault",
            get_session_id_fn=lambda request: (_ for _ in ()).throw(RuntimeError("bad cookie")),
            context_resolver=lambda session_id: ("/private", [], True, "child"),
        )
        == "/vault"
    )


def test_user_memory_path_returns_only_managed_private_memory_path():
    loader = _loader(
        managed_users={"child"},
        configs={"child": {"memory_chromadb_path": "/memory/child"}},
    )

    assert user_memory_path(None, user_manager_loader=loader) == ""
    assert user_memory_path("owner", user_manager_loader=loader) == ""
    assert user_memory_path("child", user_manager_loader=loader) == "/memory/child"
    assert user_memory_path("child", user_manager_loader=lambda: (_ for _ in ()).throw(RuntimeError("boom"))) == ""


def test_public_user_config_filters_and_defaults_user_config_fields():
    payload = public_user_config({"user_id": "child", "capabilities": ["phone"], "extra": "secret"})

    assert payload == {
        "user_id": "child",
        "email": "",
        "display_name": "",
        "personality": "default",
        "memory_namespace": "child",
        "memory_chromadb_path": "",
        "vault_root_path": "",
        "capabilities": ["phone"],
        "created_at": "",
        "seeded_memory_count": 0,
    }


def test_is_user_admin_accepts_configured_admin_variant_without_user_manager():
    assert is_user_admin(
        "Admin@Example.com",
        identity_variants_fn=lambda user_id: {"admin@example.com"},
        configured_admin_variants_fn=lambda: {"admin@example.com"},
        admin_user_manager_loader=lambda: (_ for _ in ()).throw(AssertionError("should not load user manager")),
    )


def test_is_user_admin_reads_managed_user_admin_capability():
    def admin_loader():
        def get_user_config(user_id):
            return {"capabilities": ["vault_read", "user_admin"]}

        def user_config_exists(user_id):
            return user_id == "child"

        return get_user_config, user_config_exists

    assert is_user_admin(
        "child",
        identity_variants_fn=lambda user_id: {user_id or ""},
        configured_admin_variants_fn=set,
        admin_user_manager_loader=admin_loader,
    )


def test_is_user_admin_returns_false_for_missing_config_or_missing_capability():
    def missing_loader():
        return lambda user_id: {}, lambda user_id: False

    def non_admin_loader():
        return lambda user_id: {"capabilities": ["phone"]}, lambda user_id: True

    assert not is_user_admin(
        "child",
        identity_variants_fn=lambda user_id: {user_id or ""},
        configured_admin_variants_fn=set,
        admin_user_manager_loader=missing_loader,
    )
    assert not is_user_admin(
        "child",
        identity_variants_fn=lambda user_id: {user_id or ""},
        configured_admin_variants_fn=set,
        admin_user_manager_loader=non_admin_loader,
    )


def test_is_user_admin_logs_user_manager_failures_and_returns_false():
    class FakeLogger:
        def __init__(self):
            self.calls = []

        def exception(self, message, *args):
            self.calls.append((message, args))

    logger = FakeLogger()

    assert not is_user_admin(
        None,
        identity_variants_fn=lambda user_id: set(),
        configured_admin_variants_fn=set,
        admin_user_manager_loader=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        logger=logger,
    )
    assert logger.calls == [("Failed checking user_admin capability for %s", (None,))]
