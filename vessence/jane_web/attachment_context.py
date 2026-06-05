"""Attachment context expansion for Jane chat turns.

Android uploads send the chat route a markdown link such as
``[Attached file: photo.jpg](/api/files/serve/working_files/android_uploads/photo.jpg)``.
Stage 3 only receives text context, so image uploads need a compact OCR /
description block before Jane's brain sees the turn.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from jane.config import ENV_FILE_PATH, VAULT_DIR, VESSENCE_DATA_HOME

logger = logging.getLogger(__name__)

_SERVE_PATH_RE = re.compile(r"/api/files/serve/([^\s)]+)")
_IMAGE_MIME_PREFIX = "image/"
_CACHE_DIR = Path(VESSENCE_DATA_HOME) / "cache" / "attachment_context"


def copy_chat_body_with_updates(body: Any, **updates: Any) -> Any:
    """Return a chat request body with updated fields.

    Supports Pydantic v1/v2 objects, then falls back to in-place assignment.
    The fallback is intentional: FastAPI request models are mutable by default
    in this codebase, and preserving the request object is better than dropping
    expanded file context.
    """
    if not updates:
        return body
    try:
        if hasattr(body, "model_copy"):
            return body.model_copy(update=updates)
        if hasattr(body, "copy"):
            return body.copy(update=updates)
    except Exception as exc:
        logger.warning("attachment_context: chat body copy failed: %s", exc)
    for key, value in updates.items():
        try:
            setattr(body, key, value)
        except Exception:
            pass
    return body


def attachment_stage3_state() -> dict[str, Any]:
    """Synthetic router state for attachment turns.

    Attachments must bypass Stage 1/2 because the visible user text is often
    only a filename like ``photo.jpg``. Classifying that text can produce the
    unclear short-circuit before file context reaches Jane.
    """
    return {
        "cls": "attached_file",
        "conf": "High",
        "classification": "attached_file:High",
        "stage1_ms": 0,
        "stage2_ms": 0,
        "result": None,
        "stage2_ack": None,
        "fallback_ack": None,
        "force_stage3": True,
        "params": {"attachment": True},
    }


async def expand_file_context(file_context: str | None) -> str | None:
    """Expand markdown file links with text Jane can reason over."""
    if not file_context or "[Attachment analysis]" in file_context:
        return file_context
    return await asyncio.to_thread(_expand_file_context_sync, file_context)


def _expand_file_context_sync(file_context: str) -> str:
    details: list[str] = []
    seen: set[Path] = set()
    for target in _resolve_attached_files(file_context):
        if target in seen:
            continue
        seen.add(target)
        detail = _describe_attached_file(target)
        if detail:
            details.append(detail)
    if not details:
        return file_context
    return (
        f"{file_context.strip()}\n\n"
        "[Attachment analysis]\n"
        + "\n\n".join(details)
    ).strip()


def _resolve_attached_files(file_context: str) -> list[Path]:
    vault_root = Path(VAULT_DIR).resolve()
    resolved: list[Path] = []
    for match in _SERVE_PATH_RE.finditer(file_context):
        raw = match.group(1)
        parsed = urlparse(raw)
        rel = unquote(parsed.path or raw).lstrip("/")
        if not rel or ".." in Path(rel).parts:
            continue
        candidate = (vault_root / rel).resolve()
        try:
            candidate.relative_to(vault_root)
        except ValueError:
            logger.warning("attachment_context: rejected path outside vault: %s", candidate)
            continue
        if candidate.is_file():
            resolved.append(candidate)
    return resolved


def _describe_attached_file(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if mime.startswith(_IMAGE_MIME_PREFIX):
        analysis = _cached_image_analysis(path)
        if analysis:
            return f"File: {path.name}\nMIME: {mime}\nVision/OCR summary:\n{analysis}"
    return f"File: {path.name}\nMIME: {mime}\nLocal path: {path}"


def _cached_image_analysis(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return ""
    cache_key = hashlib.sha256(
        f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
    ).hexdigest()
    cache_path = _CACHE_DIR / f"{cache_key}.json"
    try:
        if cache_path.exists():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached = str(data.get("analysis") or "").strip()
            if cached:
                return cached
    except Exception as exc:
        logger.warning("attachment_context: cache read failed for %s: %s", path, exc)

    analysis = _analyze_image(path).strip()
    if analysis:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps({"path": str(path), "analysis": analysis}, ensure_ascii=True),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("attachment_context: cache write failed for %s: %s", path, exc)
    return analysis


def _google_api_key() -> str:
    key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if key:
        return key
    try:
        env_path = Path(ENV_FILE_PATH)
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if line.startswith("GOOGLE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _analyze_image(path: Path) -> str:
    key = _google_api_key()
    if not key:
        logger.warning("attachment_context: GOOGLE_API_KEY missing; image analysis skipped")
        return ""
    try:
        import google.generativeai as genai
        import PIL.Image

        genai.configure(api_key=key)
        model_name = os.environ.get("JANE_ATTACHMENT_VISION_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)
        image = PIL.Image.open(path)
        response = model.generate_content([
            (
                "Extract useful chat context from this uploaded image. If it is a "
                "document, ticket, bill, receipt, form, screenshot, sign, or label, "
                "transcribe visible text, numbers, dates, URLs, addresses, amounts, "
                "deadlines, reference numbers, and instructions. If anything is "
                "unclear, say it is unclear. Keep the result concise but include all "
                "actionable details. Do not invent details that are not visible."
            ),
            image,
        ])
        return (getattr(response, "text", "") or "").strip()
    except Exception as exc:
        logger.warning("attachment_context: image analysis failed for %s: %s", path, exc)
        return ""
