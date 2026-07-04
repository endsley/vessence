"""Pure helpers for Jane web file upload route planning."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


def parse_upload_descriptions(descriptions_json: str | None) -> list[Any]:
    """Parse the multi-upload descriptions payload as a list."""
    try:
        descriptions = json.loads(descriptions_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return descriptions if isinstance(descriptions, list) else []


def load_upload_hash_index(hash_index_path: Path) -> dict[str, Any]:
    try:
        with open(hash_index_path) as f:
            hash_index = json.load(f)
    except Exception:
        return {}
    return hash_index if isinstance(hash_index, dict) else {}


def write_upload_hash_index(hash_index_path: Path, hash_index: Mapping[str, Any]) -> None:
    try:
        with open(hash_index_path, "w") as f:
            json.dump(hash_index, f)
    except Exception:
        pass


def upload_description(descriptions: Sequence[Any], index: int) -> str:
    """Return the stripped description for an upload slot."""
    if index >= len(descriptions):
        return ""
    return str(descriptions[index] or "").strip()


def upload_subdir(
    destination: str | None,
    mime: str,
    route_subdir: Callable[[str], str],
) -> str:
    """Pick the upload subdirectory using the route's existing destination rules."""
    if destination:
        return destination.strip("/")
    return route_subdir(mime)


def upload_safe_name(
    filename: str | None,
    description: str,
    *,
    is_image_upload: bool,
    destination: str | None,
    descriptive_filename: Callable[[str, str], str],
) -> str:
    """Pick the stored filename using the route's existing image naming rules."""
    original = filename or "upload"
    if is_image_upload and not destination:
        return descriptive_filename(original, description)
    return Path(original).name


def next_available_path(dest_dir: Path, safe_name: str) -> Path:
    """Return a non-existing destination path, suffixing collisions with _N."""
    dest_path = dest_dir / safe_name
    if not dest_path.exists():
        return dest_path

    stem, suffix = dest_path.stem, dest_path.suffix
    counter = 1
    while dest_path.exists():
        dest_path = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return dest_path


def duplicate_upload_result(filename: str | None, existing: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": filename,
        "status": "duplicate",
        "existing_path": existing.get("path", ""),
    }


def hash_index_entry(dest_path: Path, rel_path: str, description: str) -> dict[str, str]:
    return {
        "filename": dest_path.name,
        "path": rel_path,
        "description": description,
    }


def upload_success_result(
    filename: str | None,
    dest_path: Path,
    rel_path: str,
    subdir: str,
    description: str,
) -> dict[str, Any]:
    return {
        "name": filename,
        "saved_name": dest_path.name,
        "status": "ok",
        "path": rel_path,
        "subdir": subdir,
        "description": description,
    }


def upload_memory_fact_text(source_label: str, filename: str, subdir: str) -> str:
    return f"File uploaded {source_label}: {filename} saved to vault/{subdir}/"


def upload_memory_fact_command(
    *,
    python_bin: str,
    add_fact_script: str,
    fact_text: str,
    user_id: str,
    memory_path: str | None = None,
) -> list[str]:
    command = [
        python_bin,
        add_fact_script,
        fact_text,
        "--topic", "vault", "--subtopic", "upload",
        "--user-id", user_id,
    ]
    if memory_path:
        command += ["--memory-path", memory_path]
    return command


def upload_work_activity_message(results: Sequence[Mapping[str, Any]]) -> str | None:
    uploaded_names = [
        str(result["saved_name"])
        for result in results
        if result.get("status") == "ok" and result.get("saved_name")
    ]
    if not uploaded_names:
        return None
    return f"File upload: {', '.join(uploaded_names[:3])}"
