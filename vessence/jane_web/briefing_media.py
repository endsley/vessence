"""Validation and media-path helpers for briefing routes."""
from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path


_BRIEFING_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_ARCHIVE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def is_briefing_identifier(value: str | None) -> bool:
    return bool(_BRIEFING_IDENTIFIER_RE.match(value or ""))


def is_archive_date(value: str | None) -> bool:
    return bool(_ARCHIVE_DATE_RE.match(value or ""))


def daily_briefing_audio_dir(tools_dir: str | Path) -> str:
    return os.path.join(str(tools_dir), "daily_briefing", "essence_data", "audio")


def select_briefing_audio(
    audio_dir: str | Path,
    article_id: str,
    summary_type: str,
    *,
    is_file: Callable[[str], bool] = os.path.isfile,
) -> tuple[str, str] | None:
    ogg_path = os.path.join(str(audio_dir), f"{article_id}_{summary_type}.ogg")
    wav_path = os.path.join(str(audio_dir), f"{article_id}_{summary_type}.wav")
    if is_file(ogg_path):
        return (ogg_path, "audio/ogg")
    if is_file(wav_path):
        return (wav_path, "audio/wav")
    return None


def daily_briefing_image_dir(tools_dir: str | Path) -> Path:
    return Path(tools_dir) / "daily_briefing" / "essence_data" / "images"


def briefing_image_candidates(images_dir: Path, article_id: str) -> list[Path]:
    return [images_dir / f"{article_id}{ext}" for ext in _IMAGE_EXTENSIONS]


def briefing_archive_path(archive_dir: Path, date: str) -> Path:
    return archive_dir / f"{date}.json"
