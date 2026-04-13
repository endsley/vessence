"""Class registry for the v2 3-stage pipeline.

Each subdirectory of this package is a self-contained "class pack"
with a metadata.py file (and optionally a handler.py). At startup this
module walks the directory, imports every metadata.py it finds, and
assembles a registry that stage1_classifier.py and stage2_dispatcher.py
can use.

Design goals:
  - Adding a new class = adding one subdirectory. No edits to existing
    class packs, stage1_classifier.py, stage2_dispatcher.py, or
    pipeline.py.
  - Removing a class = deleting its subdirectory. Classifier prompt
    rebuilds automatically on next process start.
  - Order is controlled by the optional 'priority' field in metadata
    (lower number = appears earlier in the classifier prompt, like
    Unix nice levels; catch-all classes should use a high number).

metadata.py format:

    METADATA = {
        "name": "weather",           # classifier-facing label (may contain spaces)
        "priority": 10,              # higher = earlier in prompt (default 50)
        "description": "...",        # str OR zero-arg callable returning str
        "few_shot": [                # list of (prompt, "<class>:<confidence>")
            ("What's the temp?", "weather:High"),
        ],
        "ack": "Checking the weather…",         # optional — shown while handling
        "escalate_ack": "Let me dig deeper…",   # optional — shown when escalating
    }

handler.py format (optional):

    async def handle(prompt: str) -> dict | None:
        # Return:
        #   None                  -> pipeline will escalate to Stage 3
        #   {"text": str}         -> Stage 2 answer
        #   {"text": str, ...}    -> plus extra fields (e.g. playlist_id) that
        #                            the pipeline will merge into the response

    (Sync `def handle` is also supported — the dispatcher will offload it
    to a thread so it doesn't block the event loop.)
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_registry: dict[str, dict[str, Any]] | None = None


def _resolve_description(desc: Any) -> str:
    """Descriptions may be a str or a zero-arg callable (for dynamic text)."""
    if callable(desc):
        try:
            return str(desc())
        except Exception as e:
            logger.warning("class description callable raised: %s", e)
            return ""
    return str(desc or "")


def _load_one(subdir: Path) -> dict | None:
    pkg_name = subdir.name  # e.g. "weather"
    try:
        meta_mod = importlib.import_module(
            f"jane_web.jane_v2.classes.{pkg_name}.metadata"
        )
    except Exception as e:
        logger.warning("skipping class %r — metadata import failed: %s", pkg_name, e)
        return None

    metadata = getattr(meta_mod, "METADATA", None)
    if not isinstance(metadata, dict):
        logger.warning("skipping class %r — metadata.METADATA missing or not a dict", pkg_name)
        return None

    name = metadata.get("name") or pkg_name
    metadata = dict(metadata)  # shallow copy so we don't mutate the module
    metadata["name"] = name
    metadata["pkg_name"] = pkg_name
    metadata["priority"] = int(metadata.get("priority", 50))

    # Optional handler
    handler: Callable | None = None
    try:
        handler_mod = importlib.import_module(
            f"jane_web.jane_v2.classes.{pkg_name}.handler"
        )
        handler = getattr(handler_mod, "handle", None)
    except ModuleNotFoundError:
        pass
    except Exception as e:
        logger.warning("class %r handler import failed: %s", pkg_name, e)
    metadata["handler"] = handler

    return metadata


def get_registry(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Return the class registry, loading it on first call.

    Keys are the class 'name' (as the classifier emits it, e.g. "music play").
    """
    global _registry
    if _registry is not None and not refresh:
        return _registry

    classes_dir = Path(__file__).parent
    loaded = []
    for sub in sorted(classes_dir.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_") or sub.name.startswith("."):
            continue
        meta = _load_one(sub)
        if meta:
            loaded.append(meta)

    loaded.sort(key=lambda m: (m["priority"], m["name"]))
    _registry = {m["name"]: m for m in loaded}
    logger.info(
        "jane_v2 class registry: %d classes loaded: %s",
        len(_registry),
        ", ".join(_registry.keys()),
    )
    return _registry


def describe(name: str) -> str:
    reg = get_registry()
    meta = reg.get(name)
    if not meta:
        return ""
    return _resolve_description(meta.get("description", ""))
