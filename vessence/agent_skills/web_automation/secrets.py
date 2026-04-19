"""Encrypted secret storage with domain binding.

Per spec 9.5: filesystem-backed Fernet-encrypted blobs. Domain binding
is the core guardrail — ``get(secret_id, expected_domain)`` raises
``SecretDomainMismatch`` if the caller's current page domain doesn't
match the secret's registered domain. This is what blocks a prompt
injection from exfiltrating a banking password via a lookalike URL.

Layout::

    $VESSENCE_DATA_HOME/data/browser_secrets/
      <secret_id>.enc
      index.json
      audit.log
    $VESSENCE_DATA_HOME/config/secret_master.key   # 0600, excluded from backups

The master key is stored OUTSIDE ``data/`` so a stolen ``data/`` backup
yields ciphertext without keys. Lose the key → re-enter secrets.

Phase 2 scope:
  - create / get / list / delete
  - Domain binding (subdomain-permissive, same rule as profiles)
  - Audit log (append-only, one line per get())
  - Permission check on module load (refuse loose perms)

Out of scope for Phase 2:
  - Rotation (rotate_master_key) — Phase 3+
  - HSM / OS-keyring backends — rejected in spec (headless service)
  - Multi-user namespacing
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import secrets as _secrets
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._file_lock import exclusive

logger = logging.getLogger(__name__)


class SecretDomainMismatch(RuntimeError):
    """Raised when a get() is called against a domain the secret isn't bound to."""


class SecretNotFound(RuntimeError):
    pass


class SecretStoreMisconfigured(RuntimeError):
    """Permissions too loose or master key missing."""


def _data_base() -> Path:
    return Path(
        os.environ.get(
            "VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")
        )
    )


def _secrets_dir() -> Path:
    d = _data_base() / "data" / "browser_secrets"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Tighten perms in case mkdir raced.
    try:
        os.chmod(d, 0o700)
    except Exception:
        pass
    return d


def _key_path() -> Path:
    d = _data_base() / "config"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d / "secret_master.key"


def _ensure_master_key() -> bytes:
    """Read the master Fernet key, creating it on first use.

    Creates the file with 0600 perms and random 32-byte key. Any future
    access that finds the perms loosened raises — we'd rather crash
    loudly than silently leak.
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:
        raise SecretStoreMisconfigured(
            "cryptography package is required. pip install cryptography"
        ) from e

    kp = _key_path()
    if not kp.exists():
        key = Fernet.generate_key()
        kp.write_bytes(key)
        try:
            os.chmod(kp, 0o600)
        except Exception:
            pass
        logger.info("secrets: generated new master key at %s", kp)

    mode = stat.S_IMODE(kp.stat().st_mode)
    if mode & 0o077:
        raise SecretStoreMisconfigured(
            f"Master key {kp} has insecure mode {oct(mode)}; "
            f"expected 0600. Tighten before continuing."
        )
    return kp.read_bytes()


def _cipher():
    from cryptography.fernet import Fernet
    return Fernet(_ensure_master_key())


def _index_path() -> Path:
    return _secrets_dir() / "index.json"


def _audit_path() -> Path:
    return _secrets_dir() / "audit.log"


class SecretIndexCorrupted(SecretStoreMisconfigured):
    """Raised when index.json fails to parse — safer to halt than wipe."""


def _load_index() -> dict[str, dict[str, Any]]:
    p = _index_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        # Never silently return {} — writing on top would erase every
        # existing entry. Halt so the user can recover from backup.
        raise SecretIndexCorrupted(
            f"Secret index at {p} failed to parse ({e}). "
            f"Refusing to proceed — operating on an empty map would "
            f"silently erase all existing credentials on the next save. "
            f"Restore the file from backup or delete it only if you're "
            f"certain there are no sealed .enc files to match."
        ) from e


def _save_index(idx: dict[str, dict[str, Any]]) -> None:
    p = _index_path()
    # Atomic write via temp + rename. Combined with the exclusive lock
    # in create/delete this prevents the last-write-wins race.
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(idx, indent=2), encoding="utf-8")
    tmp.replace(p)


_ID_RE = re.compile(r"^s_[a-f0-9]{16}$")


def _assert_safe_id(secret_id: str) -> None:
    if not isinstance(secret_id, str) or not _ID_RE.match(secret_id):
        raise SecretNotFound(f"Invalid secret_id: {secret_id!r}")


def _audit(line: str) -> None:
    try:
        with open(_audit_path(), "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
    except Exception as e:
        logger.warning("secrets: audit write failed: %s", e)


# ── Public API ────────────────────────────────────────────────────────────────

@dataclass
class SecretValue:
    """Decrypted credential — short-lived. Do NOT log this dataclass."""
    username: str
    password: str
    notes: str = ""


@dataclass
class SecretIndexEntry:
    secret_id: str
    domain: str
    label: str
    created_at: int
    last_used: int


def create(domain: str, label: str, username: str, password: str, notes: str = "") -> str:
    """Encrypt + persist a new credential. Returns the opaque ``secret_id``."""
    dom = (domain or "").strip().lower()
    if not dom:
        raise ValueError("domain is required")
    sid = "s_" + _secrets.token_hex(8)
    payload = json.dumps({"username": username, "password": password, "notes": notes})
    blob = _cipher().encrypt(payload.encode("utf-8"))
    (_secrets_dir() / f"{sid}.enc").write_bytes(blob)
    now = int(time.time())
    lock_path = _secrets_dir() / ".index.lock"
    with exclusive(lock_path):
        idx = _load_index()
        idx[sid] = {
            "domain": dom,
            "label": label,
            "created_at": now,
            "last_used": 0,
        }
        _save_index(idx)
    _audit(f"{_now_iso()}\tcreate\t{sid}\t{dom}\t{label}")
    logger.info("secrets: created %s (domain=%s)", sid, dom)
    return sid


def get(secret_id: str, *, expected_domain: str, caller: str = "unknown") -> SecretValue:
    """Fetch a secret. Raises if ``expected_domain`` doesn't match.

    ``expected_domain`` must be computed from the browser's CURRENT page
    URL at the exact moment of fill. Passing a stale or fabricated
    value is how credentials get stolen — callers: resist the urge to
    cache this.
    """
    _assert_safe_id(secret_id)
    dom = (expected_domain or "").strip().lower()
    if not dom:
        raise SecretDomainMismatch("expected_domain is required")

    idx = _load_index()
    entry = idx.get(secret_id)
    if entry is None:
        raise SecretNotFound(secret_id)

    bound = entry["domain"]
    if dom != bound and not dom.endswith("." + bound):
        raise SecretDomainMismatch(
            f"Secret {secret_id!r} is bound to {bound!r}, "
            f"refused access from {dom!r} (caller={caller})"
        )

    blob_path = _secrets_dir() / f"{secret_id}.enc"
    if not blob_path.exists():
        raise SecretNotFound(f"Secret blob missing for {secret_id!r}")
    try:
        payload = _cipher().decrypt(blob_path.read_bytes())
    except Exception as e:
        raise SecretStoreMisconfigured(
            f"Failed to decrypt {secret_id!r}: {e}. Master key may have rotated."
        ) from e
    data = json.loads(payload.decode("utf-8"))

    lock_path = _secrets_dir() / ".index.lock"
    with exclusive(lock_path):
        idx = _load_index()
        if secret_id in idx:
            idx[secret_id]["last_used"] = int(time.time())
            _save_index(idx)
    _audit(f"{_now_iso()}\tget\t{secret_id}\t{bound}\t{caller}")

    return SecretValue(
        username=data.get("username", ""),
        password=data.get("password", ""),
        notes=data.get("notes", ""),
    )


def list_secrets() -> list[SecretIndexEntry]:
    idx = _load_index()
    out = []
    for sid, e in idx.items():
        out.append(SecretIndexEntry(
            secret_id=sid,
            domain=e.get("domain", ""),
            label=e.get("label", ""),
            created_at=int(e.get("created_at", 0)),
            last_used=int(e.get("last_used", 0)),
        ))
    return sorted(out, key=lambda x: x.secret_id)


def delete(secret_id: str) -> None:
    _assert_safe_id(secret_id)
    blob = _secrets_dir() / f"{secret_id}.enc"
    lock_path = _secrets_dir() / ".index.lock"
    with exclusive(lock_path):
        idx = _load_index()
        if secret_id not in idx:
            raise SecretNotFound(secret_id)
        try:
            if blob.exists():
                blob.unlink()
        except Exception as e:
            logger.warning("secrets: failed to unlink %s: %s", blob, e)
        del idx[secret_id]
        _save_index(idx)
    _audit(f"{_now_iso()}\tdelete\t{secret_id}")
    logger.info("secrets: deleted %s", secret_id)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


__all__ = [
    "SecretDomainMismatch",
    "SecretIndexEntry",
    "SecretNotFound",
    "SecretStoreMisconfigured",
    "SecretValue",
    "create",
    "delete",
    "get",
    "list_secrets",
]
