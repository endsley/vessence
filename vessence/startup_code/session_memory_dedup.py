#!/usr/bin/env python3
"""Session-scoped memory dedup for memory_hook.sh.

Filters a memory dump to remove entries already seen this Claude Code session,
so repeated ChromaDB hits don't re-inject the same content on every turn.

Usage:
    echo "$MEMORY_TEXT" | python3 session_memory_dedup.py <session_id>

Outputs only the new entries (with section headers), or nothing if all seen.
Cache lives at /tmp/jane_mem_seen_<session_id>.txt — auto-cleaned by OS on reboot.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path


def _entry_key(line: str) -> str:
    """Stable hash of the first 120 chars of an entry line."""
    return hashlib.md5(line[:120].encode()).hexdigest()


def _load_seen(cache_path: Path) -> set[str]:
    if not cache_path.exists():
        return set()
    try:
        return set(cache_path.read_text().splitlines())
    except Exception:
        return set()


def _save_seen(cache_path: Path, seen: set[str]) -> None:
    try:
        cache_path.write_text("\n".join(seen))
    except Exception:
        pass


def _cleanup_old_caches(max_age_secs: int = 28800) -> None:
    """Delete session cache files older than 8 hours."""
    try:
        now = time.time()
        for f in Path("/tmp").glob("jane_mem_seen_*.txt"):
            if now - f.stat().st_mtime > max_age_secs:
                f.unlink(missing_ok=True)
    except Exception:
        pass


def dedup(memory_text: str, session_id: str) -> str:
    cache_path = Path(f"/tmp/jane_mem_seen_{session_id}.txt")
    seen = _load_seen(cache_path)
    new_seen: set[str] = set()

    lines = memory_text.splitlines()
    output_sections: list[tuple[str, list[str]]] = []  # (header, [entry_lines])
    current_header = ""
    current_entries: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("##") or stripped.startswith("#"):
            # Flush previous section
            if current_entries:
                output_sections.append((current_header, current_entries))
            current_header = line
            current_entries = []
        elif stripped.startswith("["):
            # Memory entry line
            key = _entry_key(stripped)
            if key not in seen:
                current_entries.append(line)
                new_seen.add(key)
            # else: already seen this session — skip
        elif stripped and current_header and not stripped.startswith("##"):
            # Continuation line of an entry (multi-line entries)
            if current_entries:
                current_entries[-1] += "\n" + line

    # Flush last section
    if current_entries:
        output_sections.append((current_header, current_entries))

    if not output_sections:
        return ""

    # Build output
    parts: list[str] = []
    for header, entries in output_sections:
        if header:
            parts.append(header)
        parts.extend(entries)

    # Save newly seen keys
    seen.update(new_seen)
    _save_seen(cache_path, seen)

    return "\n".join(parts)


def main() -> int:
    if len(sys.argv) < 2:
        # No session ID — pass through unchanged
        print(sys.stdin.read(), end="")
        return 0

    session_id = sys.argv[1].strip()
    if not session_id or not session_id.isdigit():
        print(sys.stdin.read(), end="")
        return 0

    _cleanup_old_caches()
    memory_text = sys.stdin.read()
    result = dedup(memory_text, session_id)
    if result.strip():
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
