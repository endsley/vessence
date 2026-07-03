"""Safe file-source readers for context_builder.py."""

from __future__ import annotations

import json
from pathlib import Path


def read_text_file(path: Path, max_chars: int) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars].strip()
    except Exception:
        return ""


def read_json_summary_file(path: Path, max_chars: int) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""
    return json.dumps(data, ensure_ascii=True)[:max_chars]
