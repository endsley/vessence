"""Shopping List Stage 2 handler.

Uses a local LLM to determine the action (add/remove/view/clear) and
executes it directly against the shopping_list JSON store. Fast path —
no Opus needed for simple list operations.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import httpx

_SKILLS_DIR = Path(__file__).resolve().parents[4] / "agent_skills"
if str(_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILLS_DIR))

logger = logging.getLogger(__name__)

from jane_web.jane_v2.models import (  # noqa: E402
    LOCAL_LLM as MODEL,
    LOCAL_LLM_NUM_CTX,
    LOCAL_LLM_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_URL,
)

_EXTRACT_PROMPT = """\
The classifier thinks the user wants to interact with their shopping list.
First, confirm: is the user actually asking to add/remove/view items on a shopping list?
If NOT (e.g., asking about recipes, cooking, or something unrelated), output ONLY: WRONG_CLASS

If YES, determine the action and items. Output EXACTLY these lines — nothing else:

ACTION: add | remove | view | clear
ITEMS: <comma-separated items, or "none" for view/clear>
LIST: <list name if mentioned, or "default">

Example 1:
User: add milk and eggs to my shopping list
ACTION: add
ITEMS: milk, eggs
LIST: default

Example 2:
User: what's on my shopping list
ACTION: view
ITEMS: none
LIST: default

Example 3:
User: remove bread from my costco list
ACTION: remove
ITEMS: bread
LIST: costco

Example 4:
User: clear my shopping list
ACTION: clear
ITEMS: none
LIST: default

Use the recent conversation below to interpret follow-ups like \
"add that one too" or "actually remove it".

{context_block}User: {prompt}"""


_WRONG_CLASS_SENTINEL = {"wrong_class": True}


def _parse_extraction(raw: str) -> dict | None:
    if "WRONG_CLASS" in raw.upper():
        return _WRONG_CLASS_SENTINEL
    action = items = list_name = None
    # Normalize: split on newlines AND on pipe/slash separators (some LLMs
    # collapse the 3 fields onto one line using "|" or "/" as a separator).
    import re
    normalized = re.sub(r"\s*[|/]\s*(?=[A-Z]+:)", "\n", raw.strip())
    for line in normalized.splitlines():
        line = line.strip()
        if line.upper().startswith("ACTION:"):
            action = line.split(":", 1)[1].strip().lower()
        elif line.upper().startswith("ITEMS:"):
            items = line.split(":", 1)[1].strip()
        elif line.upper().startswith("LIST:"):
            list_name = line.split(":", 1)[1].strip().lower()
    if not action:
        return None
    return {
        "action": action,
        "items": [i.strip() for i in (items or "").split(",") if i.strip() and i.strip().lower() != "none"],
        "list_name": list_name or "default",
    }


async def handle(prompt: str, context: str = "") -> dict | None:
    """Parse shopping list action and execute it."""
    context_block = ""
    if context and context.strip():
        context_block = f"Recent conversation:\n{context.strip()}\n\n"
    extract_prompt = _EXTRACT_PROMPT.format(prompt=prompt.strip(), context_block=context_block)
    body = {
        "model": MODEL,
        "prompt": extract_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 60, "num_ctx": LOCAL_LLM_NUM_CTX},
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }

    try:
        async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            raw = (r.json().get("response") or "").strip()
    except Exception as e:
        logger.warning("shopping_list handler: LLM failed: %s", e)
        return None

    parsed = _parse_extraction(raw)
    if parsed is _WRONG_CLASS_SENTINEL:
        logger.info("shopping_list handler: LLM says WRONG_CLASS — escalating with self-correct")
        return _WRONG_CLASS_SENTINEL
    if not parsed:
        logger.warning("shopping_list handler: parse failed: %r", raw[:200])
        return None

    action = parsed["action"]
    items = parsed["items"]
    list_name = parsed["list_name"]

    try:
        from agent_skills.shopping_list import (
            add_item, remove_item, get_list, clear_list, format_for_context,
        )
    except Exception as e:
        logger.warning("shopping_list handler: import failed: %s", e)
        return None

    if action == "view":
        current = get_list(list_name)
        if not current:
            return {"text": f"Your {list_name} list is empty."}
        formatted = ", ".join(current)
        return {"text": f"Your {list_name} list has: {formatted}."}

    elif action == "add":
        if not items:
            return None  # escalate — user didn't specify what to add
        for item in items:
            add_item(item, list_name)
        added = ", ".join(items)
        current = get_list(list_name)
        return {"text": f"Added {added}. Your {list_name} list now has {len(current)} items."}

    elif action == "remove":
        if not items:
            return None
        for item in items:
            remove_item(item, list_name)
        removed = ", ".join(items)
        return {"text": f"Removed {removed} from your {list_name} list."}

    elif action == "clear":
        clear_list(list_name)
        return {"text": f"Your {list_name} list has been cleared."}

    return None  # unknown action → escalate
