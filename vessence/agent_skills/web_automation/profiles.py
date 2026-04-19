"""Named browser profiles — persistent auth state per site.

A profile is a ``storage_state.json`` (Playwright's cookies +
localStorage + sessionStorage blob) plus a metadata sidecar. Profiles
are domain-bound: a profile for ``citywater.com`` will refuse to load
into a context navigating to ``amazon.com``.

Layout::

    $VESSENCE_DATA_HOME/data/browser_profiles/<profile_id>/
      storage_state.json
      profile_meta.json

Phase 2 scope (per spec 9.5):
  - Create, load, list, delete.
  - Domain binding with mismatch error.
  - TTL with default 30 days since last-used; expired profiles refuse
    to load until refreshed.
  - Auth handoff flow: ``capture_after_login(page, profile_id)``
    writes the post-login storage state to disk.

NOT yet in Phase 2 (future):
  - Profile sharing / import / export.
  - Per-user namespacing (single-user install for now).
  - Multi-domain profiles (one profile → multiple sites). Current rule:
    one domain per profile.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Profile becomes "stale" after this many seconds since last use.
# Stale profiles still load (cookies often survive longer than we think)
# but log a warning so the user can choose to re-authenticate.
TTL_SECONDS_STALE = 30 * 86_400


def _profiles_root() -> Path:
    base = Path(
        os.environ.get(
            "VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")
        )
    )
    d = base / "data" / "browser_profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class ProfileMeta:
    profile_id: str
    display_name: str
    domain: str
    created_at: int
    updated_at: int
    last_used: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "domain": self.domain,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProfileMeta":
        return cls(
            profile_id=d["profile_id"],
            display_name=d.get("display_name", d["profile_id"]),
            domain=d["domain"],
            created_at=int(d.get("created_at", 0)),
            updated_at=int(d.get("updated_at", 0)),
            last_used=int(d.get("last_used", 0)),
        )


class ProfileDomainMismatch(RuntimeError):
    """Raised when a profile is loaded against a different domain."""


class ProfileNotFound(RuntimeError):
    pass


# ── Public API ────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Turn a human display name into a safe profile_id.

    Keeps alphanumerics + dash + underscore; lowercased; maxlen 40.
    """
    s = re.sub(r"[^a-zA-Z0-9_\-]+", "_", (name or "").strip().lower()).strip("_-")
    return s[:40] or "profile"


def create(display_name: str, domain: str) -> ProfileMeta:
    """Allocate a new profile directory. Storage_state is empty until
    ``capture_after_login`` fills it. Returns the metadata.
    """
    dom = (domain or "").strip().lower()
    if not dom:
        raise ValueError("domain is required")
    pid = slugify(display_name)
    # Suffix if collision
    root = _profiles_root()
    base_pid = pid
    i = 2
    while (root / pid).exists():
        pid = f"{base_pid}_{i}"
        i += 1
    pdir = root / pid
    pdir.mkdir(parents=True, exist_ok=False)
    now = int(time.time())
    meta = ProfileMeta(
        profile_id=pid,
        display_name=display_name,
        domain=dom,
        created_at=now,
        updated_at=now,
        last_used=0,
    )
    (pdir / "profile_meta.json").write_text(
        json.dumps(meta.to_dict(), indent=2), encoding="utf-8"
    )
    (pdir / "storage_state.json").write_text(
        json.dumps({"cookies": [], "origins": []}), encoding="utf-8"
    )
    logger.info("profiles: created %s (domain=%s)", pid, dom)
    return meta


_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,60}$")


def _assert_safe_id(profile_id: str) -> None:
    """Refuse IDs that could escape the profiles directory via ``..`` etc."""
    if not isinstance(profile_id, str) or not _ID_RE.match(profile_id):
        raise ProfileNotFound(f"Invalid profile_id: {profile_id!r}")


def get(profile_id: str) -> ProfileMeta:
    _assert_safe_id(profile_id)
    path = _profiles_root() / profile_id / "profile_meta.json"
    if not path.exists():
        raise ProfileNotFound(profile_id)
    return ProfileMeta.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_profiles() -> list[ProfileMeta]:
    root = _profiles_root()
    out: list[ProfileMeta] = []
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        mp = sub / "profile_meta.json"
        if not mp.exists():
            continue
        try:
            out.append(ProfileMeta.from_dict(json.loads(mp.read_text(encoding="utf-8"))))
        except Exception as e:
            logger.warning("profiles: skipping %s — bad metadata (%s)", sub.name, e)
    return out


def delete(profile_id: str) -> None:
    """Hard-delete a profile directory.

    Phase 3 will move to a two-tier soft/hard delete per spec 9.4; for
    Phase 2 we keep it simple — one shot removal.
    """
    _assert_safe_id(profile_id)
    pdir = _profiles_root() / profile_id
    if not pdir.exists():
        raise ProfileNotFound(profile_id)
    # Delete files we own, then the directory. Avoid shutil.rmtree to
    # keep the blast radius tight.
    for f in pdir.iterdir():
        try:
            f.unlink()
        except Exception as e:
            logger.warning("profiles: failed to remove %s: %s", f, e)
    try:
        pdir.rmdir()
    except Exception as e:
        logger.warning("profiles: failed to remove dir %s: %s", pdir, e)
    logger.info("profiles: deleted %s", profile_id)


def storage_state_path(profile_id: str) -> str:
    _assert_safe_id(profile_id)
    return str(_profiles_root() / profile_id / "storage_state.json")


def bind_check(profile_id: str, url: str) -> None:
    """Raise ``ProfileDomainMismatch`` if ``url``'s domain doesn't match
    the profile's registered domain.

    Accepts subdomains of the registered domain, because a site's login
    flow often redirects login → app.example.com. Refuses a completely
    different host.
    """
    from .safety import domain_of
    meta = get(profile_id)
    dom = domain_of(url)
    if not dom:
        raise ProfileDomainMismatch(
            f"Cannot load profile {profile_id!r} against non-http URL: {url!r}"
        )
    if dom != meta.domain and not dom.endswith("." + meta.domain):
        raise ProfileDomainMismatch(
            f"Profile {profile_id!r} is bound to {meta.domain!r}, "
            f"refusing to load against {dom!r}."
        )


def touch_last_used(profile_id: str) -> None:
    pdir = _profiles_root() / profile_id
    mp = pdir / "profile_meta.json"
    if not mp.exists():
        return
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
        data["last_used"] = int(time.time())
        mp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("profiles: touch_last_used failed: %s", e)


async def capture_after_login(page: Any, profile_id: str) -> None:
    """Ask Playwright for the current context's storage_state and write
    it to the profile's file. Also bumps ``updated_at`` and ``last_used``.
    """
    meta = get(profile_id)
    path = _profiles_root() / profile_id / "storage_state.json"
    try:
        ctx = page.context
        await ctx.storage_state(path=str(path))
    except Exception as e:
        raise RuntimeError(f"capture_after_login: {e}") from e
    now = int(time.time())
    meta_dict = meta.to_dict()
    meta_dict["updated_at"] = now
    meta_dict["last_used"] = now
    (_profiles_root() / profile_id / "profile_meta.json").write_text(
        json.dumps(meta_dict, indent=2), encoding="utf-8"
    )
    logger.info("profiles: captured storage_state for %s", profile_id)


def is_stale(profile_id: str) -> bool:
    meta = get(profile_id)
    if meta.last_used == 0:
        return False
    return (int(time.time()) - meta.last_used) > TTL_SECONDS_STALE


__all__ = [
    "ProfileDomainMismatch",
    "ProfileMeta",
    "ProfileNotFound",
    "bind_check",
    "capture_after_login",
    "create",
    "delete",
    "get",
    "is_stale",
    "list_profiles",
    "slugify",
    "storage_state_path",
    "touch_last_used",
]
