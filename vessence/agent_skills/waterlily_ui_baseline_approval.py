"""Human-reviewed, fail-closed approval for Waterlily vendor UI baselines.

Nightly repair may diagnose vendor UI drift, but it must never turn an
unreviewed live page into the new definition of a healthy page.  This module
provides the narrow approval boundary used by Waterlily UI adapters: inspect a
privacy-safe structural profile, require a human's full hash acknowledgement,
then atomically commit it while holding the Waterlily-wide baseline lock.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable

from agent_skills.code_lock import code_edit_lock


_FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REVIEWER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,79}$")
_KIND_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")


class BaselineApprovalError(RuntimeError):
    """A baseline approval lacks a verified human-review acknowledgement."""


def canonical_profile_sha256(profile: dict[str, Any]) -> str:
    """Hash one JSON-safe, privacy-safe structural profile deterministically."""
    if not isinstance(profile, dict):
        raise BaselineApprovalError("UI baseline profile is invalid")
    try:
        payload = json.dumps(
            profile,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise BaselineApprovalError("UI baseline profile is invalid") from exc
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_approval_inputs(
    *,
    kind: str,
    reviewed_profile_sha256: str,
    reviewed_by: str,
) -> tuple[str, str, str]:
    if os.environ.get("JANE_SELF_HEAL_ACTIVE", "").strip():
        raise BaselineApprovalError("Autonomous repair may not approve a UI baseline")
    normalized_kind = str(kind or "").strip().lower()
    normalized_hash = str(reviewed_profile_sha256 or "").strip().lower()
    normalized_reviewer = str(reviewed_by or "").strip()
    if not _KIND_RE.fullmatch(normalized_kind):
        raise BaselineApprovalError("UI baseline approval kind is invalid")
    if not _FULL_SHA256_RE.fullmatch(normalized_hash):
        raise BaselineApprovalError("UI baseline approval requires a full reviewed profile SHA-256")
    if not _REVIEWER_RE.fullmatch(normalized_reviewer):
        raise BaselineApprovalError("UI baseline approval reviewer is invalid")
    return normalized_kind, normalized_hash, normalized_reviewer


def approve_reviewed_waterlily_profile(
    *,
    kind: str,
    reviewed_profile_sha256: str,
    reviewed_by: str,
    observe: Callable[[], dict[str, Any]],
    commit: Callable[[dict[str, Any], dict[str, str]], Any],
) -> dict[str, str]:
    """Observe and commit a reviewed profile under the Waterlily-wide lock.

    ``observe`` and ``commit`` run under one actual exclusive lock rather than
    checking a lock holder before writing.  This prevents a profile changing
    between human review and baseline write.  ``commit`` receives only the
    verified structural profile plus non-sensitive approval provenance.
    """
    normalized_kind, expected_hash, normalized_reviewer = _validate_approval_inputs(
        kind=kind,
        reviewed_profile_sha256=reviewed_profile_sha256,
        reviewed_by=reviewed_by,
    )
    with code_edit_lock("waterlily-ui-baseline-approval", project="waterlily"):
        profile = observe()
        observed_hash = canonical_profile_sha256(profile)
        if not hmac.compare_digest(observed_hash, expected_hash):
            raise BaselineApprovalError("Reviewed UI baseline profile hash does not match current observation")
        approval = {
            "kind": normalized_kind,
            "reviewed_by": normalized_reviewer,
            "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "observed_profile_sha256": observed_hash,
        }
        commit(profile, approval)
    return {
        "status": "approved",
        "kind": normalized_kind,
        "observed_profile_sha256": observed_hash,
    }
