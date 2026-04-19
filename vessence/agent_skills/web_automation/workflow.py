"""Named workflows — save a scripted plan, replay it by name.

Per spec sections 3, 9.4, 9.10:
  - Flat ``steps`` array (DAG upgrade deferred to Phase 4).
  - ``index.json`` name → workflow_id (O(1) name lookup + rapidfuzz-ready).
  - Opaque workflow_id (``secrets.token_hex(8)``) decoupled from name.
  - Soft-delete (move to ``archived/``) restorable for 30 days.
  - ``schema_version`` field enables future migrations.

Phase 3 scope (minimum viable):
  - save(name, description, steps, ...) → workflow_id
  - load(name_or_id) → dict
  - list() → summary list
  - delete(name_or_id) → soft delete
  - restore(workflow_id) / purge(workflow_id)
  - run(workflow_id, inputs) via skill.run_task

Phase 4 (or later):
  - Recording flow: capture steps during an ad-hoc session.
  - Self-healing on broken selectors (semantic.py re-match).
  - Schedule fields (cron-triggered runs).

Storage root: ``$VESSENCE_DATA_HOME/data/browser_workflows/``
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets as _secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._file_lock import exclusive

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class WorkflowNotFound(RuntimeError):
    pass


class WorkflowIndexError(RuntimeError):
    pass


def _root() -> Path:
    base = Path(
        os.environ.get(
            "VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")
        )
    )
    d = base / "data" / "browser_workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / "archived").mkdir(exist_ok=True)
    return d


def _index_path() -> Path:
    return _root() / "index.json"


class WorkflowIndexCorrupted(WorkflowIndexError):
    """Index.json failed to parse — halt rather than silently wipe."""


def _load_index() -> dict[str, str]:
    """name_normalized → workflow_id."""
    p = _index_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise WorkflowIndexCorrupted(
            f"Workflow index at {p} failed to parse ({e}). "
            f"Use workflow.rebuild_index() to regenerate from wf_*.json, "
            f"or restore the file from backup. Refusing to continue — "
            f"saving on top would erase every existing name mapping."
        ) from e


def _save_index(idx: dict[str, str]) -> None:
    p = _index_path()
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(idx, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


_WORKFLOW_ID_RE = re.compile(r"^wf_[a-f0-9]{16}$")


def _assert_safe_wid(workflow_id: str) -> None:
    if not isinstance(workflow_id, str) or not _WORKFLOW_ID_RE.match(workflow_id):
        raise WorkflowNotFound(f"Invalid workflow_id: {workflow_id!r}")


def _normalize_name(name: str) -> str:
    # Lowercase, collapse whitespace, keep [a-z0-9 _-]
    s = re.sub(r"\s+", " ", (name or "").strip().lower())
    s = re.sub(r"[^a-z0-9 _-]+", "", s)
    return s


def _wf_path(workflow_id: str, archived: bool = False) -> Path:
    base = _root() / ("archived" if archived else "")
    return base / f"{workflow_id}.json"


# ── Public API ────────────────────────────────────────────────────────────────

@dataclass
class WorkflowSummary:
    workflow_id: str
    name: str
    description: str
    created_at: int
    updated_at: int
    step_count: int


def save(
    *,
    name: str,
    description: str,
    steps: list[dict[str, Any]],
    allowed_domains: list[str] | None = None,
    browser_profile_id: str | None = None,
    inputs_schema: dict[str, Any] | None = None,
) -> str:
    """Create or overwrite a workflow with the given name.

    If ``name`` already exists in the index, the SAME workflow_id is
    reused (edit semantics — spec 9.4). Otherwise a new id is minted.
    Serialized via exclusive file lock so concurrent saves don't
    clobber each other's index entries.
    """
    norm = _normalize_name(name)
    if not norm:
        raise ValueError("workflow name required")

    # Normalize step shape — require each step to have ``action``.
    # Doing this OUTSIDE the lock keeps the critical section tiny and
    # surfaces step validation errors without touching the index file.
    clean_steps: list[dict[str, Any]] = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict) or "action" not in s:
            raise ValueError(f"step {i} missing 'action'")
        clean_steps.append({
            "id": s.get("id") or f"step_{i + 1:02d}",
            "label": s.get("label") or s["action"],
            "intent": s.get("intent") or "",
            "action": s["action"],
            "args": s.get("args") or {},
            "selector_candidates": s.get("selector_candidates") or [],
            "preconditions": s.get("preconditions") or [],
            "postconditions": s.get("postconditions") or [],
            "retry_policy": s.get("retry_policy") or {"max_attempts": 1},
            "requires_confirmation": bool(s.get("requires_confirmation", False)),
        })

    with exclusive(_root() / ".index.lock"):
        idx = _load_index()
        workflow_id = idx.get(norm) or ("wf_" + _secrets.token_hex(8))
        now = int(time.time())

        path = _wf_path(workflow_id)
        existing_created = now
        if path.exists():
            try:
                existing_created = int(
                    json.loads(path.read_text(encoding="utf-8")).get("created_at", now)
                )
            except Exception:
                pass

        doc = {
            "schema_version": SCHEMA_VERSION,
            "id": workflow_id,
            "name": name,
            "description": description,
            "created_at": existing_created,
            "updated_at": now,
            "allowed_domains": allowed_domains or [],
            "browser_profile_id": browser_profile_id,
            "inputs_schema": inputs_schema or {"type": "object", "properties": {}},
            "steps": clean_steps,
        }
        # Atomic write via temp + rename.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        tmp.replace(path)

        idx[norm] = workflow_id
        _save_index(idx)
    logger.info("workflow: saved %s (id=%s, %d steps)", name, workflow_id, len(clean_steps))
    return workflow_id


def load(name_or_id: str) -> dict[str, Any]:
    """Fetch a workflow by human name OR opaque id."""
    candidate = (name_or_id or "").strip()
    if not candidate:
        raise WorkflowNotFound("")
    # Try id first (exact file).
    if candidate.startswith("wf_") and _wf_path(candidate).exists():
        return json.loads(_wf_path(candidate).read_text(encoding="utf-8"))
    # Then by normalized name via index.
    idx = _load_index()
    wid = idx.get(_normalize_name(candidate))
    if wid and _wf_path(wid).exists():
        return json.loads(_wf_path(wid).read_text(encoding="utf-8"))
    raise WorkflowNotFound(candidate)


def list_workflows() -> list[WorkflowSummary]:
    out: list[WorkflowSummary] = []
    root = _root()
    for f in sorted(root.glob("wf_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append(WorkflowSummary(
                workflow_id=d["id"],
                name=d["name"],
                description=d.get("description", ""),
                created_at=int(d.get("created_at", 0)),
                updated_at=int(d.get("updated_at", 0)),
                step_count=len(d.get("steps", [])),
            ))
        except Exception as e:
            logger.warning("workflow: skipping %s — bad JSON (%s)", f.name, e)
    return out


def delete(name_or_id: str) -> None:
    """Soft delete — move to archived/. Restorable for 30 days."""
    doc = load(name_or_id)
    wid = doc["id"]
    _assert_safe_wid(wid)
    src = _wf_path(wid)
    dst = _wf_path(wid, archived=True)
    with exclusive(_root() / ".index.lock"):
        try:
            src.rename(dst)
        except Exception as e:
            raise WorkflowIndexError(f"delete failed: {e}")
        idx = _load_index()
        norm = _normalize_name(doc["name"])
        idx.pop(norm, None)
        _save_index(idx)
    logger.info("workflow: soft-deleted %s", wid)


def restore(workflow_id: str) -> None:
    _assert_safe_wid(workflow_id)
    src = _wf_path(workflow_id, archived=True)
    dst = _wf_path(workflow_id)
    if not src.exists():
        raise WorkflowNotFound(workflow_id)
    with exclusive(_root() / ".index.lock"):
        # Guard against a name collision: if a new workflow has taken
        # the name slot while the old one was archived, refuse rather
        # than clobber.
        doc = json.loads(src.read_text(encoding="utf-8"))
        norm = _normalize_name(doc["name"])
        idx = _load_index()
        if norm in idx and idx[norm] != workflow_id:
            raise WorkflowIndexError(
                f"Cannot restore {workflow_id}: name {doc['name']!r} "
                f"is now taken by {idx[norm]!r}. Rename first."
            )
        src.rename(dst)
        idx[norm] = workflow_id
        _save_index(idx)
    logger.info("workflow: restored %s", workflow_id)


def purge(workflow_id: str) -> None:
    """Hard delete from archive."""
    _assert_safe_wid(workflow_id)
    src = _wf_path(workflow_id, archived=True)
    if src.exists():
        src.unlink()
        logger.info("workflow: purged %s", workflow_id)


def rebuild_index() -> int:
    """Rescan wf_*.json on disk and rebuild index.json.

    Returns number of workflows indexed.
    """
    idx: dict[str, str] = {}
    for f in _root().glob("wf_*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            idx[_normalize_name(d["name"])] = d["id"]
        except Exception as e:
            logger.warning("workflow: skipping %s during rebuild (%s)", f.name, e)
    _save_index(idx)
    return len(idx)


async def run(name_or_id: str) -> Any:
    """Execute a saved workflow via the Phase 1 skill runner.

    Phase 3 MVP — treats the workflow's ``steps`` as a direct plan.
    Self-healing (Phase 3 stretch) and input substitution land later.
    """
    from .browser_session import SessionOptions
    from .skill import TaskStep, run_task
    doc = load(name_or_id)
    steps = [
        TaskStep(
            action=s["action"],
            args=s.get("args") or {},
            confirm=bool(s.get("requires_confirmation", False)),
        )
        for s in doc.get("steps", [])
    ]
    # Load profile if specified.
    storage_state = None
    profile_id = doc.get("browser_profile_id")
    if profile_id:
        from . import profiles as _profiles
        try:
            storage_state = _profiles.storage_state_path(profile_id)
            _profiles.touch_last_used(profile_id)
        except Exception as e:
            logger.warning("workflow: profile load failed: %s", e)
    opts = SessionOptions(storage_state_path=storage_state)
    return await run_task(steps, label=_normalize_name(doc["name"])[:20], options=opts)


__all__ = [
    "SCHEMA_VERSION",
    "WorkflowNotFound",
    "WorkflowSummary",
    "delete",
    "list_workflows",
    "load",
    "purge",
    "rebuild_index",
    "restore",
    "run",
    "save",
]
