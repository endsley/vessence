"""Shopping list manager — simple JSON file storage.

Lists are stored in VESSENCE_DATA_HOME/shopping_lists.json as:
{
  "default": ["milk", "eggs", "bread"],
  "costco": ["paper towels", "chicken"],
  ...
}
"""

import inspect
import json
import os
from pathlib import Path

from agent_skills.shopping_list_data import (
    CONFIDENCE_THRESHOLD as _CONFIDENCE_THRESHOLD,
    add_item_to_lists,
    clear_list_in_lists,
    coerce_lists_data,
    format_lists_for_context,
    remove_item_from_lists,
    require_confidence as _require_confidence,
)

VESSENCE_DATA_HOME = os.environ.get("VESSENCE_DATA_HOME",
    os.path.join(os.path.expanduser("~"), "ambient", "vessence-data"))
LISTS_FILE = Path(VESSENCE_DATA_HOME) / "shopping_lists.json"


def _load() -> dict[str, list[str]]:
    if LISTS_FILE.exists():
        try:
            data = json.loads(LISTS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
        return coerce_lists_data(data)
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
    mutation = add_item_to_lists(data, item, list_name)
    _save(data)
    return mutation.items


def remove_item(
    item: str, list_name: str = "default", *, confidence: float
) -> list[str]:
    _require_confidence(confidence)
    data = _load()
    mutation = remove_item_from_lists(data, item, list_name)
    if mutation.should_save:
        _save(data)
    return mutation.items


def clear_list(list_name: str = "default", *, confidence: float):
    _require_confidence(confidence)
    data = _load()
    clear_list_in_lists(data, list_name)
    _save(data)


def format_for_context() -> str:
    """Format all shopping lists for injection into LLM context."""
    data = _load()
    return format_lists_for_context(data)


remove_item.__signature__ = inspect.Signature(
    [
        inspect.Parameter("item", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        inspect.Parameter(
            "list_name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default="default",
        ),
        inspect.Parameter("confidence", inspect.Parameter.KEYWORD_ONLY),
    ]
)
clear_list.__signature__ = inspect.Signature(
    [
        inspect.Parameter(
            "list_name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default="default",
        ),
        inspect.Parameter("confidence", inspect.Parameter.KEYWORD_ONLY),
    ]
)
