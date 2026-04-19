"""Shopping list class — add/remove/view shopping items."""

import logging
import sys
from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parents[4] / "agent_skills"
if str(_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILLS_DIR))

_logger = logging.getLogger(__name__)


def _escalation_context() -> str:
    """Inject current shopping list state so Stage 3 (Opus) can view/edit."""
    try:
        from agent_skills.shopping_list import format_for_context
        return format_for_context()
    except Exception:
        pass
    # Fallback: try get_list directly
    try:
        from agent_skills.shopping_list import get_list
        items = get_list()
        if not items:
            return "Shopping list is currently empty."
        return "Current shopping list: " + ", ".join(items)
    except Exception as e:
        return f"Shopping list unavailable: {e}"


METADATA = {
    "name": "shopping list",
    "priority": 20,
    "description": (
        "[shopping list]\n"
        "User wants to view, add to, remove from, or clear their personal "
        "shopping list. The list lives in a local JSON store; a local LLM "
        "parses the action and Jane applies it directly — no Opus needed "
        "for simple list ops.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"add milk to my shopping list\"\n"
        "  - \"put eggs on the shopping list\"\n"
        "  - \"what's on my shopping list\"\n"
        "  - \"remove eggs from shopping\"\n"
        "  - \"do I need bread\"\n"
        "  - \"clear my shopping list\"\n"
        "  - \"add bananas, oranges, and bread\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'shopping list' but ARE NOT:\n"
        "  - \"add to my todo list\" → 'todo list' (errands, not groceries)\n"
        "  - \"what should I buy for dinner\" → 'others' (recipe recommendation)\n"
        "  - \"what's the cheapest brand of milk\" → 'others' (price question)\n"
        "  - \"remind me to buy milk\" → 'timer' or 'others' (reminder, not list add)\n"
        "  - \"where's the closest grocery\" → 'others' (location / maps)"
    ),
    "few_shot": [],
    "ack": None,
    "escalate_ack": None,
    "escalation_context": _escalation_context,
}
