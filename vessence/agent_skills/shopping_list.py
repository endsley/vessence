"""Shopping list manager — simple JSON file storage.

Lists are stored in VESSENCE_DATA_HOME/shopping_lists.json as:
{
  "default": ["milk", "eggs", "bread"],
  "costco": ["paper towels", "chicken"],
  ...
}
"""

import json
import os
from pathlib import Path

VESSENCE_DATA_HOME = os.environ.get("VESSENCE_DATA_HOME",
    os.path.join(os.path.expanduser("~"), "ambient", "vessence-data"))
LISTS_FILE = Path(VESSENCE_DATA_HOME) / "shopping_lists.json"


def _load() -> dict[str, list[str]]:
    if LISTS_FILE.exists():
        try:
            return json.loads(LISTS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save(data: dict[str, list[str]]):
    LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LISTS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def get_all_lists() -> dict[str, list[str]]:
    return _load()


def get_list(name: str = "default") -> list[str]:
    return _load().get(name.lower(), [])


def add_item(item: str, list_name: str = "default") -> list[str]:
    data = _load()
    key = list_name.lower()
    if key not in data:
        data[key] = []
    item = item.strip()
    if item and item.lower() not in [i.lower() for i in data[key]]:
        data[key].append(item)
    _save(data)
    return data[key]


def remove_item(item: str, list_name: str = "default") -> list[str]:
    data = _load()
    key = list_name.lower()
    if key in data:
        data[key] = [i for i in data[key] if i.lower() != item.strip().lower()]
        _save(data)
    return data.get(key, [])


def clear_list(list_name: str = "default"):
    data = _load()
    key = list_name.lower()
    data[key] = []
    _save(data)


def format_for_context() -> str:
    """Format all shopping lists for injection into LLM context."""
    data = _load()
    if not data:
        return "No shopping lists exist yet. The user can ask you to create one."
    parts = []
    for name, items in data.items():
        if items:
            item_list = "\n".join(f"  - {i}" for i in items)
            parts.append(f"**{name.title()} list:**\n{item_list}")
        else:
            parts.append(f"**{name.title()} list:** (empty)")
    return "\n\n".join(parts)
