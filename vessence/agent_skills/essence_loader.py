from jane.config import get_chroma_client
#!/usr/bin/env python3
"""
essence_loader.py — Loads, unloads, and manages Vessence essences.

Provides the core lifecycle for essences:
    - load_essence(path) -> EssenceState
    - unload_essence(name)
    - delete_essence(name, port_memory=False)
    - list_loaded_essences()
    - list_available_essences()
"""

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Add parent so we can import siblings
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_skills.validate_essence import validate_essence


# ---------------------------------------------------------------------------
# EssenceState dataclass
# ---------------------------------------------------------------------------

@dataclass
class EssenceState:
    """Runtime state for a loaded essence."""
    name: str
    role_title: str
    manifest: dict[str, Any]
    chromadb_client: Any  # Optional chromadb.Client — None if no DB present
    personality_prompt: str
    capabilities: dict[str, list[str]]
    essence_path: str = ""


# ---------------------------------------------------------------------------
# In-memory registry of loaded essences
# ---------------------------------------------------------------------------

_loaded_essences: dict[str, EssenceState] = {}


def _log_to_work_log(description: str, category: str = "general") -> None:
    """Log an activity to the Work Log if available."""
    try:
        from agent_skills.work_log_tools import log_activity
        log_activity(description, category=category)
    except Exception:
        pass


def _get_tools_dir() -> str:
    """Resolve the tools directory path (formerly essences/)."""
    home = str(Path.home())
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.join(home, "ambient"))
    return os.environ.get("TOOLS_DIR",
                          os.environ.get("ESSENCES_DIR",
                                         os.path.join(ambient_base, "skills")))


def _get_essences_dir() -> str:
    """Resolve the essences directory path (true AI agents)."""
    home = str(Path.home())
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.join(home, "ambient"))
    return os.path.join(ambient_base, "essences")


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def load_essence(essence_path: str) -> EssenceState:
    """
    Load an essence from its folder path.

    Parses and validates manifest.json, reads personality.md,
    initializes ChromaDB if knowledge/chromadb/ exists,
    and returns an EssenceState object.

    Raises:
        FileNotFoundError: if essence_path does not exist
        ValueError: if validation fails
    """
    essence_path = os.path.abspath(essence_path)

    if not os.path.isdir(essence_path):
        raise FileNotFoundError(f"Essence path does not exist: {essence_path}")

    # Validate
    is_valid, errors = validate_essence(essence_path)
    if not is_valid:
        raise ValueError(
            f"Essence validation failed for '{essence_path}':\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # Parse manifest
    manifest_path = os.path.join(essence_path, "manifest.json")
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    name = manifest["essence_name"]
    role_title = manifest.get("role_title", "assistant")
    capabilities = manifest.get("capabilities", {"provides": [], "consumes": []})

    # Read personality
    personality_path = os.path.join(essence_path, "personality.md")
    with open(personality_path, "r") as f:
        personality_prompt = f.read()

    # Initialize ChromaDB if available
    chromadb_client = None
    chromadb_path = os.path.join(essence_path, "knowledge", "chromadb")
    if os.path.isdir(chromadb_path):
        try:
            import chromadb
            chromadb_client = get_chroma_client(path=chromadb_path)
        except ImportError:
            pass  # chromadb not installed — skip
        except Exception:
            pass  # DB init failed — non-fatal, skip

    state = EssenceState(
        name=name,
        role_title=role_title,
        manifest=manifest,
        chromadb_client=chromadb_client,
        personality_prompt=personality_prompt,
        capabilities=capabilities,
        essence_path=essence_path,
    )

    _loaded_essences[name] = state
    return state


def unload_essence(essence_name: str) -> None:
    """
    Unload a previously loaded essence by name.
    Removes it from the in-memory registry. Does NOT delete files.
    """
    if essence_name not in _loaded_essences:
        raise KeyError(f"Essence '{essence_name}' is not loaded")

    state = _loaded_essences.pop(essence_name)

    # Close ChromaDB client if possible
    if state.chromadb_client is not None:
        try:
            # PersistentClient doesn't have a close(), but reset clears in-memory state
            del state.chromadb_client
        except Exception:
            pass


def delete_essence(essence_name: str, port_memory: bool = False) -> None:
    """
    Delete an essence entirely.

    If port_memory is True, the essence's ChromaDB knowledge is migrated
    to Jane's universal memory before deletion. (Migration is a placeholder
    for Phase 2 — currently logs a warning.)

    Removes the essence folder from disk.
    """
    # Search both tools/ and essences/ directories
    search_dirs = [_get_tools_dir(), _get_essences_dir()]

    # Find the essence folder
    essence_path = None
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for entry in os.listdir(search_dir):
            candidate = os.path.join(search_dir, entry)
            manifest_path = os.path.join(candidate, "manifest.json")
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path) as f:
                        m = json.load(f)
                    if m.get("essence_name") == essence_name:
                        essence_path = candidate
                        break
                except (json.JSONDecodeError, OSError):
                    continue
        if essence_path:
            break

    if essence_path is None:
        raise FileNotFoundError(f"No essence folder found for '{essence_name}'")

    # Unload if currently loaded
    if essence_name in _loaded_essences:
        unload_essence(essence_name)

    if port_memory:
        # Phase 2: migrate essence ChromaDB to Jane's universal memory
        print(f"[essence_loader] Memory porting for '{essence_name}' is not yet implemented (Phase 2)")

    # Delete the folder
    shutil.rmtree(essence_path)


def list_loaded_essences() -> list[str]:
    """Return names of all currently loaded essences."""
    return list(_loaded_essences.keys())


def list_available_essences(type_filter: str = "all") -> list[dict[str, Any]]:
    """
    Scan the essences directory and return metadata for each valid essence.

    Args:
        type_filter: "all" (default), "tool", or "essence". Filters by the
                     manifest's ``type`` field. Items missing a ``type`` field
                     default to "tool" for backward compatibility.

    Returns a list of dicts with keys: name, role_title, version, description,
    type, has_brain, path.
    """
    # Scan both tools/ (type=tool) and essences/ (type=essence) directories
    scan_dirs = [_get_tools_dir(), _get_essences_dir()]
    results: list[dict[str, Any]] = []

    for scan_dir in scan_dirs:
        if not os.path.isdir(scan_dir):
            continue

        for entry in sorted(os.listdir(scan_dir)):
            candidate = os.path.join(scan_dir, entry)
            manifest_path = os.path.join(candidate, "manifest.json")
            if not os.path.isfile(manifest_path):
                continue

            try:
                with open(manifest_path) as f:
                    m = json.load(f)

                item_type = m.get("type", "tool")  # default to "tool" if missing
                has_brain = m.get("has_brain", False)

                # Apply filter
                if type_filter != "all" and item_type != type_filter:
                    continue

                results.append({
                    "name": m.get("essence_name", entry),
                    "role_title": m.get("role_title", ""),
                    "version": m.get("version", ""),
                    "description": m.get("description", ""),
                    "type": item_type,
                    "has_brain": has_brain,
                    "path": candidate,
                })
            except (json.JSONDecodeError, OSError):
                continue

    # Sort: Jane first, Work Log last, everything else alphabetically between
    def _sort_key(e: dict) -> tuple:
        name = e.get("name", "").lower()
        if name == "jane":
            return (0, "")
        elif name == "work log":
            return (2, "")
        else:
            return (1, name)

    results.sort(key=_sort_key)
    return results


def list_available(type_filter: str = "all") -> list[dict[str, Any]]:
    """Convenience alias for list_available_essences with a type filter.

    Args:
        type_filter: "all", "tool", or "essence".
    """
    return list_available_essences(type_filter=type_filter)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Simple CLI: list available essences or load one for testing."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python essence_loader.py list          — list available essences")
        print("  python essence_loader.py load <path>   — load and validate an essence")
        return 0

    cmd = sys.argv[1]

    if cmd == "list":
        essences = list_available_essences()
        if not essences:
            print("No essences found.")
            return 0
        for e in essences:
            loaded = " [LOADED]" if e["name"] in _loaded_essences else ""
            print(f"  {e['name']} (v{e['version']}) — {e['role_title']}{loaded}")
            print(f"    {e['description'][:80]}")
            print(f"    Path: {e['path']}")
        return 0

    elif cmd == "load":
        if len(sys.argv) < 3:
            print("Usage: python essence_loader.py load /path/to/essence", file=sys.stderr)
            return 1
        path = os.path.abspath(sys.argv[2])
        try:
            state = load_essence(path)
            print(f"Loaded: {state.name} ({state.role_title})")
            print(f"  Capabilities provides: {state.capabilities.get('provides', [])}")
            print(f"  Capabilities consumes: {state.capabilities.get('consumes', [])}")
            print(f"  ChromaDB: {'initialized' if state.chromadb_client else 'none'}")
            return 0
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
