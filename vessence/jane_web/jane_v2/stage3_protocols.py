"""Stage 3 class protocol lookup and synthesis helpers."""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CLASSES_DIR = (Path(__file__).parent / "classes").resolve()
CLASS_NAME_RE = re.compile(r"^[a-z0-9_]+$")

# Keyed by class_name -> (mtime_ns, text_or_None).
PROTOCOL_CACHE: dict[str, tuple[int, str | None]] = {}


def strip_escalation_reason_suffix(base: str) -> str:
    for suffix in ("_fallback", "_declined", "_decline"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


def reason_to_class(reason: str) -> str | None:
    """Map a Stage 3 escalation reason to a class folder name."""
    if not reason:
        return None
    base = reason.split(":", 1)[0].strip().lower().replace(" ", "_")
    base = strip_escalation_reason_suffix(base)
    if not base or base == "others":
        return None
    if not CLASS_NAME_RE.match(base):
        logger.warning("stage3_escalate: rejecting malformed class name %r", base)
        return None
    return base


def metadata_for_class_pkg(class_name: str) -> dict | None:
    """Return registry metadata for a class package name, e.g. todo_list."""
    try:
        from . import classes as class_registry
        reg = class_registry.get_registry()
    except Exception as e:
        logger.warning("stage3_escalate: class registry unavailable: %s", e)
        return None
    for meta in reg.values():
        if meta.get("pkg_name") == class_name:
            return meta
    return None


def synthesize_class_protocol(class_name: str) -> str | None:
    """Build Stage 3 protocol from the same metadata Stage 1/2 use."""
    meta = metadata_for_class_pkg(class_name)
    if not meta:
        return None
    try:
        from . import classes as class_registry
        desc = class_registry.describe(meta.get("name", ""))
    except Exception:
        raw_desc = meta.get("description", "")
        desc = raw_desc() if callable(raw_desc) else str(raw_desc or "")

    has_handler = bool(meta.get("handler"))
    lines = [
        "AUTHORITATIVE class contract (generated live from registry — supersedes any prior summary).",
        f"- Class name: {meta.get('name', class_name)}",
        f"- Package: {class_name}",
        f"- Stage 2 handler: {'YES — handler exists and is registered' if has_handler else 'NO — no handler'}",
    ]
    if desc.strip():
        lines.extend(["", "Stage 1/2 description:", desc.strip()])

    escalation_context = meta.get("escalation_context")
    if escalation_context:
        ctx = escalation_context() if callable(escalation_context) else str(escalation_context)
        if ctx and ctx.strip():
            lines.extend(["", "Escalation context:", ctx.strip()])

    few_shot = meta.get("few_shot") or []
    if few_shot:
        lines.append("")
        lines.append("Classifier examples:")
        for prompt, label in few_shot[:12]:
            lines.append(f"- {prompt!r} -> {label}")

    return "\n".join(lines).strip() or None


def load_protocol_extension(class_name: str) -> str | None:
    """Read optional `classes/<class_name>/protocol.md`, cached by mtime."""
    if not CLASS_NAME_RE.match(class_name):
        return None
    path = CLASSES_DIR / class_name / "protocol.md"
    try:
        resolved = path.resolve()
    except Exception:
        return None
    if not str(resolved).startswith(str(CLASSES_DIR) + "/"):
        logger.warning("stage3_escalate: %s escapes classes dir, refusing", resolved)
        return None
    try:
        mtime = path.stat().st_mtime_ns
    except FileNotFoundError:
        return None
    cached = PROTOCOL_CACHE.get(class_name)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        text = path.read_text(encoding="utf-8").strip() or None
    except Exception as e:
        logger.warning("stage3_escalate: failed to read %s: %s", path, e)
        text = None
    PROTOCOL_CACHE[class_name] = (mtime, text)
    return text


def load_class_protocol(class_name: str) -> str | None:
    """Return generated metadata protocol plus optional protocol.md."""
    generated = synthesize_class_protocol(class_name)
    extension = load_protocol_extension(class_name)
    parts = [part for part in (generated, extension) if part]
    if not parts:
        return None
    return "\n\n".join(parts)
