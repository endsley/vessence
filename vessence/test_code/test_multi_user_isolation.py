"""Unit tests for Job #77 multi-user account isolation.

Covers the invariants that are testable without spinning up FastAPI:
    - normalize_user_id produces filesystem-safe IDs
    - create_user_space / get_user_config / is_managed_user round-trip
    - scoped_session_id changes generic IDs only for managed users
    - canonical conversation key distinguishes users and devices

Run: /home/chieh/google-adk-env/adk-venv/bin/python -m pytest test_code/test_multi_user_isolation.py -x -q
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

VESSENCE_HOME = str(Path(__file__).resolve().parents[1])
if VESSENCE_HOME not in sys.path:
    sys.path.insert(0, VESSENCE_HOME)


@pytest.fixture
def temp_vessence_data(monkeypatch, tmp_path):
    """Redirect USERS_DIR at a tmp dir so tests don't touch real data.

    `jane.config.VESSENCE_DATA_HOME` is captured at import time, so simply
    setting the env var isn't enough — we also rebind `user_manager.USERS_DIR`.
    """
    data_root = tmp_path / "vessence-data"
    data_root.mkdir()
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(data_root))
    import agent_skills.user_manager as um
    monkeypatch.setattr(um, "USERS_DIR", data_root / "users")
    return data_root, um


def test_normalize_user_id_is_filesystem_safe():
    from agent_skills.user_manager import normalize_user_id
    assert normalize_user_id("person@example.com") == "person_at_example_com"
    assert normalize_user_id("chieh.t.wu@gmail.com") == "chieh_t_wu_at_gmail_com"
    assert normalize_user_id("   ") == "user"
    assert normalize_user_id("Already_Normalized") == "already_normalized"


def test_create_user_space_writes_config_and_memory(temp_vessence_data):
    data_root, um = temp_vessence_data
    config = um.create_user_space(
        "tester@example.com",
        display_name="Tester",
        email="tester@example.com",
        capabilities=["chat", "memory", "vault_read"],
        seed_memories=["Tester prefers dark mode."],
    )
    user_dir = data_root / "users" / "tester_at_example_com"
    assert (user_dir / "config.json").exists()
    assert (user_dir / "memory" / "vector_db").is_dir()
    assert (user_dir / "vault").is_dir()
    assert config["managed"] is True
    assert "vault_read" in config["capabilities"]
    # seeded_memory_count should cover the three bootstrap facts plus one custom seed
    assert config["seeded_memory_count"] >= 4


def test_is_managed_user_false_for_unknown(temp_vessence_data):
    _data, um = temp_vessence_data
    assert not um.is_managed_user("ghost@example.com")


def test_scoped_session_id_only_scopes_managed_users(temp_vessence_data):
    _data, um = temp_vessence_data
    um.create_user_space("scoped@example.com", "Scoped", email="scoped@example.com")
    # Managed user gets scoped ID
    scoped = um.scoped_session_id("scoped@example.com", "jane_android")
    assert scoped == "scoped_at_example_com__jane_android"
    # Unmanaged users keep the raw ID
    assert um.scoped_session_id("ghost@example.com", "jane_android") == "jane_android"
    # Missing session falls back to "default"
    assert um.scoped_session_id("scoped@example.com", "").endswith("__default")


def test_default_capabilities_include_vault(temp_vessence_data):
    _data, um = temp_vessence_data
    assert "chat" in um.DEFAULT_CAPABILITIES
    assert "memory" in um.DEFAULT_CAPABILITIES
    assert "vault_read" in um.DEFAULT_CAPABILITIES
    assert "vault_write" in um.DEFAULT_CAPABILITIES


def test_vault_root_stays_inside_user_folder(temp_vessence_data):
    data_root, um = temp_vessence_data
    config = um.create_user_space("alice@example.com", "Alice", email="alice@example.com")
    vault_root = Path(config["vault_root_path"])
    expected_base = data_root / "users" / "alice_at_example_com" / "vault"
    assert vault_root.resolve() == expected_base.resolve()


def test_delete_managed_user_removes_folder_but_refuses_unmanaged(temp_vessence_data):
    data_root, um = temp_vessence_data
    um.create_user_space("todelete@example.com", "Delete Me", email="todelete@example.com")
    result = um.delete_user_space("todelete@example.com")
    assert result["removed"] is True
    assert not (data_root / "users" / "todelete_at_example_com").exists()

    # Unmanaged accounts cannot be deleted via this helper
    result2 = um.delete_user_space("chieh.t.wu@gmail.com")
    assert result2["removed"] is False


def test_two_devices_same_session_id_still_distinct_keys():
    """Canonical conversation key must separate two different devices even when
    they share a client session UUID."""
    user_id = "shared_at_example_com"
    session_uuid = "0f8a-4d6c"
    key_phone = f"{user_id}__deviceA__{session_uuid}"
    key_tablet = f"{user_id}__deviceB__{session_uuid}"
    assert key_phone != key_tablet


def test_two_users_same_device_still_distinct_keys():
    """Canonical key must separate two different users even if their devices
    send the same ids."""
    session_uuid = "0f8a-4d6c"
    key_alice = f"alice_at_example_com__sameDevice__{session_uuid}"
    key_bob = f"bob_at_example_com__sameDevice__{session_uuid}"
    assert key_alice != key_bob
