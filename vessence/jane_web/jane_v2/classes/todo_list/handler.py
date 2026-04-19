"""todo_list Stage 2 handler.

Supports both reading and editing the TODO list.

Reading (two-turn flow):
  Turn 1 — enter():
      If the user already named a category ("what's on my clinic list"),
      go straight to _speak_category. Otherwise ask which category and
      stash a STAGE2_FOLLOWUP pending_action so the next turn bypasses
      Stage 1 and lands back here with `pending=awaiting=category`.

  Turn 2 — _handle_resume():
      Match the user's reply to a category (fuzzy) and read back the
      items. If the reply does not strongly identify a category, abandon
      the pending action and route the question to Stage 3.

Editing:
  Detects add/remove intents in the first turn. If a category and item
  text are identifiable, edits the Google Doc directly via docs_tools
  and refreshes the local cache. If ambiguous, asks for clarification
  via a pending_action follow-up.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Edit intent detection ──────────────────────────────────────────────────
_ADD_PATTERNS = [
    re.compile(r"\badd\b.*\b(?:to.?do|list|task)", re.I),
    re.compile(r"\badd\b.*\b(?:to my|for my|under)", re.I),
    re.compile(r"\bput\b.*\bon my\b.*\blist", re.I),
    re.compile(r"\badd a task\b", re.I),
    re.compile(r"\badd\b.{1,80}(?:urgent|clinic|home|student)", re.I),
]
_REMOVE_PATTERNS = [
    re.compile(r"\b(?:remove|delete|cross off|mark.?done|check off|scratch)\b", re.I),
    re.compile(r"\btake\b.*\boff\b.*\blist", re.I),
]


def _detect_edit_intent(prompt: str) -> str | None:
    """Return 'add', 'remove', or None."""
    for pat in _ADD_PATTERNS:
        if pat.search(prompt):
            return "add"
    for pat in _REMOVE_PATTERNS:
        if pat.search(prompt):
            return "remove"
    return None


_PLACEHOLDER_ITEM_RE = re.compile(
    r"^(?:a|an|the|new)?\s*"
    r"(?:item|task|todo|to-do|thing|something)"
    r"(?:\s+(?:item|task|todo|to-do|thing))?$",
    re.I,
)


def _is_placeholder_item_text(text: str | None) -> bool:
    """True when the extracted add text is a slot placeholder, not a task."""
    if not text:
        return False
    cleaned = re.sub(r"[.?!,;:]+$", "", text.strip())
    return bool(_PLACEHOLDER_ITEM_RE.match(cleaned))


def _extract_item_text(prompt: str, edit_type: str) -> str | None:
    """Try to extract the item text from an add/remove request."""
    p = prompt.strip()
    if edit_type == "add":
        # "add 'call the plumber' to my home list"
        m = re.search(r"""['"\u2018\u2019\u201c\u201d](.+?)['"\u2018\u2019\u201c\u201d]""", p)
        if m:
            return m.group(1).strip()
        # "add a task for students: grade midterms"
        m = re.search(r":\s*(.+)$", p)
        if m:
            return m.group(1).strip()
        # "add buy milk to my to-do"
        m = re.search(r"\badd\s+(.+?)(?:\s+to\s+(?:my|the)\b|\s+(?:under|for)\s+)", p, re.I)
        if m:
            return m.group(1).strip()
        # Fallback: everything after "add"
        m = re.search(r"\badd\s+(.+)", p, re.I)
        if m:
            text = m.group(1).strip()
            text = re.sub(r"\s+(?:to|on|under|for)\s+(?:my|the)\s+.*$", "", text, flags=re.I)
            return text if text and not _is_placeholder_item_text(text) else None
    elif edit_type == "remove":
        # "remove 'curtain rods' from my clinic list"
        m = re.search(r"""['"\u2018\u2019\u201c\u201d](.+?)['"\u2018\u2019\u201c\u201d]""", p)
        if m:
            return m.group(1).strip()
        # "remove the curtain rods item"
        m = re.search(
            r"\b(?:remove|delete|cross off|check off|scratch)\s+(?:the\s+)?(.+?)(?:\s+(?:item|from|off)\b|$)",
            p, re.I,
        )
        if m:
            text = m.group(1).strip()
            text = re.sub(r"\s+(?:from|on|off)\s+(?:my|the)\s+.*$", "", text, flags=re.I)
            return text if text else None
    return None


def _refresh_cache() -> None:
    """Re-run the fetch script to update the local cache after an edit."""
    import subprocess, sys
    venv_python = os.environ.get(
        "VENV_PYTHON",
        "/home/chieh/google-adk-env/adk-venv/bin/python",
    )
    fetch_script = os.path.join(
        os.environ.get("VESSENCE_HOME", "/home/chieh/ambient/vessence"),
        "agent_skills", "fetch_todo_list.py",
    )
    try:
        subprocess.run(
            [venv_python, fetch_script],
            capture_output=True, timeout=30,
        )
        logger.info("todo_list: cache refreshed after edit")
    except Exception as e:
        logger.warning("todo_list: cache refresh failed: %s", e)


async def _handle_edit(prompt: str, edit_type: str, categories: list[dict]) -> dict | None:
    """Handle an add or remove edit request."""
    item_text = _extract_item_text(prompt, edit_type)
    if _is_placeholder_item_text(item_text):
        item_text = None
    cat = _match_category(prompt, categories)

    if edit_type == "add":
        if not item_text and cat:
            ask = f"What item should I add to {_friendly_category_name(cat['name'])}?"
            return {
                "text": ask,
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add", "category": cat["name"]},
                    "pending_action": _pending(
                        "add_item_for_category",
                        {"action": "add", "category": cat["name"]},
                        question=ask,
                    ),
                },
            }
        if not item_text:
            cat_list = _speak_category_list(categories).replace(
                "Which one do you want to hear?",
                "Which category should I add it to?"
            )
            return {
                "text": cat_list,
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add"},
                    "pending_action": _pending(
                        "add_category_then_item",
                        {"action": "add"},
                        question=cat_list,
                    ),
                },
            }
        if not cat:
            cat_list = _speak_category_list(categories).replace(
                "Which one do you want to hear?",
                "Which category should I add it to?"
            )
            return {
                "text": cat_list,
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add", "item_text": item_text},
                    "pending_action": _pending(
                        "add_category",
                        {"action": "add", "item_text": item_text},
                        question=cat_list,
                    ),
                },
            }
        try:
            from agent_skills.docs_tools import todo_add_item
            result = todo_add_item(item_text, cat["name"])
            _refresh_cache()
            return {
                "text": f"Done. {result}",
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add", "category": cat["name"]},
                },
            }
        except Exception as e:
            logger.error("todo_list: add failed: %s", e)
            return {
                "text": f"I couldn't add that item. The error was: {e}",
                "structured": {"intent": "todo list"},
            }

    elif edit_type == "remove":
        if not item_text:
            ask = "Which item should I remove? Tell me the text or item number."
            return {
                "text": ask,
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "remove"},
                    "pending_action": _pending("remove_item", {"action": "remove"}, question=ask),
                },
            }
        try:
            from agent_skills.docs_tools import todo_remove_item
            result = todo_remove_item(item_text, category=cat["name"] if cat else None)
            _refresh_cache()
            return {
                "text": f"Done. {result}",
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "remove"},
                },
            }
        except Exception as e:
            logger.error("todo_list: remove failed: %s", e)
            return {
                "text": f"I couldn't remove that item. The error was: {e}",
                "structured": {"intent": "todo list"},
            }

    return None


_VESSENCE_DATA_HOME = Path(os.environ.get(
    "VESSENCE_DATA_HOME",
    str(Path.home() / "ambient" / "vessence-data"),
))
_CACHE_PATH = Path(os.environ.get(
    "TODO_CACHE_PATH",
    str(_VESSENCE_DATA_HOME / "todo_list_cache.json"),
))


# Pivot detection REMOVED 2026-04-17. Prefix/substring heuristics were
# brittle (new pivot phrases always leaked through) and duplicated across
# every handler. Detection is now centralized in
# stage2_dispatcher._continuation_check, which runs the qwen2.5:7b gate
# against the literal question stored in pending["question"]. See
# handler `_pending()` below.

# ── Cache I/O ───────────────────────────────────────────────────────────────
def _load_cache() -> dict | None:
    try:
        if not _CACHE_PATH.exists():
            return None
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("todo_list: cache read failed: %s", exc)
        return None


# ── Category matching ──────────────────────────────────────────────────────
# Chieh's canonical categories (from the Google Doc). Keys are match
# tokens; values are the exact category name to look up in the cache.
_CATEGORY_ALIASES = {
    # "Do it Immediately"
    "immediately": "Do it Immediately",
    "urgent": "Do it Immediately",
    "asap": "Do it Immediately",
    # "For my students"
    "student": "For my students",
    "students": "For my students",
    "school": "For my students",
    "teaching": "For my students",
    # "For our Home"
    "home": "For our Home",
    "house": "For our Home",
    "household": "For our Home",
    # "For the clinic"
    "clinic": "For the clinic",
    "kathia": "For the clinic",
    "water lily": "For the clinic",
    # "Ambient project goals" is intentionally NOT listed — it's a
    # Stage 3 topic, answered by Opus, not this fast handler.
}

# Short-response threshold: if the user's reply is this short, it's
# likely a direct answer to "which category?". Longer replies get
# stricter matching to avoid false positives from incidental words.
_SHORT_REPLY_WORDS = 6


# Category names that this handler DOES NOT read back. If the user's
# prompt points at one of these, we return None to escalate to Stage 3.
# "jane" is here because Chieh's Google Doc still uses the old header
# "Jane" for what he now calls "Ambient project goals". Once he renames
# the doc header, the "jane" alias can be dropped.
_EXCLUDED_CATEGORY_NAMES = {"ambient project goals", "jane"}


def _normalize(s: str) -> str:
    # Strip UTF-8 BOM that slipped through in older cache files.
    s = (s or "").lstrip("\ufeff")
    return re.sub(r"\s+", " ", s.lower().strip(".!?,"))


def _visible_categories(categories: list[dict]) -> list[dict]:
    """Filter out categories this handler doesn't answer from
    (e.g. Ambient project goals, which goes to Stage 3)."""
    return [
        c for c in categories
        if _normalize(c.get("name", "")) not in _EXCLUDED_CATEGORY_NAMES
    ]


def _match_category(prompt: str, categories: list[dict]) -> dict | None:
    """Return the best-matching category dict or None if ambiguous.

    Short replies (≤ _SHORT_REPLY_WORDS) get lenient matching (aliases,
    numbers). Longer replies only match on exact category names to avoid
    false positives when incidental words like "home" or "2" appear in
    an unrelated sentence.
    """
    if not categories:
        return None
    categories = _visible_categories(categories)
    p = _normalize(prompt)
    is_short = len(p.split()) <= _SHORT_REPLY_WORDS

    # Exact name match — always allowed regardless of length.
    for cat in categories:
        if _normalize(cat.get("name", "")) in p:
            return cat

    # Alias hit — only for short replies to avoid "stage 2" → "students"
    if is_short:
        for alias, canonical in _CATEGORY_ALIASES.items():
            if alias in p:
                for cat in categories:
                    if _normalize(cat.get("name", "")) == _normalize(canonical):
                        return cat

    # Numeric fallback — only for short replies like "2", "the third one"
    if is_short:
        m = re.search(r"\b(\d+)(?:st|nd|rd|th)?\b", p)
        if m:
            idx = int(m.group(1))
            if 1 <= idx <= len(categories):
                return categories[idx - 1]
        ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
        for word, n in ordinals.items():
            if re.search(rf"\b{word}\b", p):
                if n <= len(categories):
                    return categories[n - 1]
    return None


# ── Utterance asks for a SPECIFIC category up-front? ────────────────────────
def _direct_category_query(prompt: str, categories: list[dict]) -> dict | None:
    """If the first-turn prompt already specifies a category, skip the
    'which one?' question and answer directly."""
    hit = _match_category(prompt, categories)
    if hit:
        return hit
    return None


# ── Response builders ──────────────────────────────────────────────────────
def _friendly_category_name(raw: str) -> str:
    """Massage a category name into something natural for TTS.

    Doc headers are written for visual skim, not speech. "Do it
    Immediately" spoken literally is awkward ("for Do it Immediately");
    "your urgent list" sounds like a friend. Applies the same
    transforms we use when listing categories.
    """
    name = raw.strip()
    low = name.lower()
    if "immediately" in low:
        return "your urgent list"
    if low.startswith("for the "):
        return "the " + name[len("For the "):].lower()
    if low.startswith("for our "):
        return name[len("For our "):].lower()
    if low.startswith("for my "):
        return name[len("For my "):].lower()
    return name


def _speak_items(cat: dict) -> str:
    name = _friendly_category_name(cat.get("name", "that"))
    items = [it for it in (cat.get("items") or []) if it.strip()]
    if not items:
        return f"Nothing logged under {name} yet."
    if len(items) == 1:
        return f"For {name}: {items[0].rstrip('.').strip()}."
    if len(items) == 2:
        return (
            f"Two things for {name}. "
            f"First, {items[0].rstrip('.').strip()}. "
            f"And second, {items[1].rstrip('.').strip()}."
        )
    joined = "; ".join(it.rstrip(".").strip() for it in items[:-1])
    return (
        f"{len(items)} items for {name}. "
        f"{joined}; and finally, {items[-1].rstrip('.').strip()}."
    )


def _speak_category_list(categories: list[dict]) -> str:
    categories = _visible_categories(categories)
    names = [c.get("name", "").strip() for c in categories if c.get("items")]
    # Friendlier spoken versions — strip "For " prefix, rename "Do it
    # Immediately" to "immediate" for voice flow.
    friendly = []
    for n in names:
        low = n.lower()
        if "immediately" in low:
            friendly.append("the urgent stuff")
        elif low.startswith("for the "):
            friendly.append("the " + n[len("For the "):].lower())
        elif low.startswith("for our "):
            friendly.append(n[len("For our "):].lower())
        elif low.startswith("for my "):
            friendly.append(n[len("For my "):].lower())
        else:
            friendly.append(n.lower())
    if not friendly:
        return "Your list is empty right now."
    if len(friendly) == 1:
        return f"Just one category — {friendly[0]}. Want me to read it?"
    if len(friendly) == 2:
        return (
            f"Two categories: {friendly[0]} and {friendly[1]}. "
            f"Which one do you want to hear?"
        )
    return (
        f"{len(friendly)} categories: "
        + ", ".join(friendly[:-1])
        + f", and {friendly[-1]}. "
        + "Which one do you want to hear?"
    )


# ── pending_action helpers ──────────────────────────────────────────────────
def _expires_at(minutes: int = 2) -> str:
    return (_dt.datetime.utcnow() + _dt.timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _pending(awaiting: str, data: dict, question: str = "") -> dict:
    """Build a STAGE2_FOLLOWUP pending_action.

    `question` is the literal text Jane just asked — passed verbatim to the
    dispatcher's LLM pivot check in the next turn. If omitted, the check
    falls back to the class's generic description.
    """
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "todo list",
        "status": "awaiting_user",
        "awaiting": awaiting,
        "data": {**data, "awaiting": awaiting},
        "question": question,
        "expires_at": _expires_at(),
    }


# ── Resume handler (follow-up turn after we asked "which?") ─────────────────
async def _handle_resume(prompt: str, pending: dict) -> dict | None:
    # Pivot detection is now the dispatcher's job — see
    # stage2_dispatcher._continuation_check, which runs the qwen2.5:7b gate
    # with the literal question we stored in `pending["question"]`. The
    # legacy `_looks_like_pivot` prefix heuristic was removed 2026-04-17.
    cache = _load_cache()
    if cache is None:
        return {
            "text": (
                "I don't have a cached copy of your TODO list yet. "
                "The cron job may not have run since Jane last started."
            ),
            "structured": {"intent": "todo list"},
        }

    categories = cache.get("categories") or []

    # The pipeline passes pending.data for Stage 2 follow-ups. Some tests and
    # older callers still pass the full pending_action wrapper, so accept both.
    pending_data = pending.get("data") if isinstance(pending.get("data"), dict) else pending
    awaiting = pending_data.get("awaiting", "") or pending.get("awaiting", "")

    if awaiting == "add_category":
        item_text = pending_data.get("item_text", "")
        cat = _match_category(prompt, categories)
        if cat is None:
            logger.info("todo_list: no category match for add → abandon")
            return {"abandon_pending": True}
        try:
            from agent_skills.docs_tools import todo_add_item
            result = todo_add_item(item_text, cat["name"])
            _refresh_cache()
            return {
                "text": f"Done. {result}",
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add", "category": cat["name"]},
                },
            }
        except Exception as e:
            logger.error("todo_list: add (resume) failed: %s", e)
            return {"text": f"I couldn't add that. Error: {e}", "structured": {"intent": "todo list"}}

    if awaiting == "add_category_then_item":
        cat = _match_category(prompt, categories)
        if cat is None:
            logger.info("todo_list: no category match for add slot → abandon")
            return {"abandon_pending": True}
        ask = f"What item should I add to {_friendly_category_name(cat['name'])}?"
        return {
            "text": ask,
            "structured": {
                "intent": "todo list",
                "entities": {"action": "add", "category": cat["name"]},
                "pending_action": _pending(
                    "add_item_for_category",
                    {"action": "add", "category": cat["name"]},
                    question=ask,
                ),
            },
        }

    if awaiting == "add_item_for_category":
        item_text = prompt.strip()
        if not item_text or _is_placeholder_item_text(item_text):
            category_name = pending_data.get("category", "")
            ask = f"What item should I add to {_friendly_category_name(category_name)}?"
            return {
                "text": ask,
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add", "category": category_name},
                    "pending_action": _pending(
                        "add_item_for_category",
                        {"action": "add", "category": category_name},
                        question=ask,
                    ),
                },
            }
        category_name = pending_data.get("category", "")
        cat = next((c for c in categories if c.get("name") == category_name), None)
        if cat is None:
            logger.info("todo_list: saved add category missing → abandon")
            return {"abandon_pending": True}
        try:
            from agent_skills.docs_tools import todo_add_item
            result = todo_add_item(item_text, cat["name"])
            _refresh_cache()
            return {
                "text": f"Done. {result}",
                "structured": {
                    "intent": "todo list",
                    "entities": {
                        "action": "add",
                        "category": cat["name"],
                        "item_text": item_text,
                    },
                },
            }
        except Exception as e:
            logger.error("todo_list: add item for category failed: %s", e)
            return {"text": f"Couldn't add that. Error: {e}", "structured": {"intent": "todo list"}}

    if awaiting == "add_item":
        item_text = prompt.strip()
        if _is_placeholder_item_text(item_text):
            ask = "What item should I add?"
            return {
                "text": ask,
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add"},
                    "pending_action": _pending("add_item", {"action": "add"}, question=ask),
                },
            }
        cat = _match_category(prompt, categories)
        if cat and (prompt.strip().lower() in {
            cat.get("name", "").strip().lower(),
            _friendly_category_name(cat.get("name", "")).strip().lower(),
            "urgent",
            "urgent stuff",
        }):
            ask = f"What item should I add to {_friendly_category_name(cat['name'])}?"
            return {
                "text": ask,
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add", "category": cat["name"]},
                    "pending_action": _pending(
                        "add_item_for_category",
                        {"action": "add", "category": cat["name"]},
                        question=ask,
                    ),
                },
            }
        if not cat:
            ask = f"Got it: '{item_text}'. Which category should I add it to?"
            return {
                "text": ask,
                "structured": {
                    "intent": "todo list",
                    "entities": {"action": "add", "item_text": item_text},
                    "pending_action": _pending(
                        "add_category",
                        {"action": "add", "item_text": item_text},
                        question=ask,
                    ),
                },
            }
        try:
            from agent_skills.docs_tools import todo_add_item
            result = todo_add_item(item_text, cat["name"])
            _refresh_cache()
            return {"text": f"Done. {result}", "structured": {"intent": "todo list"}}
        except Exception as e:
            return {"text": f"Couldn't add that. Error: {e}", "structured": {"intent": "todo list"}}

    if awaiting == "remove_item":
        try:
            from agent_skills.docs_tools import todo_remove_item
            result = todo_remove_item(prompt.strip())
            _refresh_cache()
            return {"text": f"Done. {result}", "structured": {"intent": "todo list"}}
        except Exception as e:
            return {"text": f"Couldn't remove that. Error: {e}", "structured": {"intent": "todo list"}}

    # Default: reading flow — match category
    cat = _match_category(prompt, categories)
    if cat is None:
        logger.info("todo_list: no strong category match → abandon to Stage 1")
        return {"abandon_pending": True}

    text = _speak_items(cat)
    logger.info("todo_list: resumed → %s", cat.get("name"))
    return {
        "text": text,
        "structured": {
            "intent": "todo list",
            "entities": {"category": cat.get("name", "")},
        },
    }


# ── Main entry ──────────────────────────────────────────────────────────────
async def handle(
    prompt: str,
    context: str = "",
    pending: dict | None = None,
) -> dict | None:
    if pending:
        return await _handle_resume(prompt, pending)

    # Defense in depth: if Stage 1 classifier misroutes an Ambient-project
    # prompt to this handler (rare but possible on borderline phrasings),
    # decline so the pipeline escalates to Stage 3 instead of asking
    # "which category?" from the remaining visible categories.
    p_lower = (prompt or "").lower()
    if "ambient" in p_lower and "project" in p_lower:
        logger.info("todo_list: ambient-project prompt detected → escalate")
        return None

    # Stage 1 sometimes mis-embeds "shopping list" queries as todo_list
    # because both share the word "list". Hand off to the shopping_list
    # handler directly so the user gets a fast answer instead of a
    # "which todo category?" prompt.
    if "shopping" in p_lower:
        try:
            from jane_web.jane_v2.classes.shopping_list import handler as _shop
        except Exception as e:
            logger.warning("todo_list: shopping_list import failed: %s", e)
        else:
            logger.info("todo_list: shopping-list prompt detected → delegate")
            return await _shop.handle(prompt, context=context)

    cache = _load_cache()
    if cache is None:
        return {
            "text": (
                "I don't have a cached copy of your TODO list yet. "
                "The cron job may not have run since Jane last started."
            ),
            "structured": {"intent": "todo list"},
        }

    categories = cache.get("categories") or []

    # Edit intent: add or remove items
    edit_type = _detect_edit_intent(prompt)
    if edit_type:
        logger.info("todo_list: edit intent detected → %s", edit_type)
        return await _handle_edit(prompt, edit_type, categories)

    if not categories:
        return {
            "text": "Your TODO list looks empty right now.",
            "structured": {"intent": "todo list"},
        }

    # Shortcut: user already named a specific category in their opener.
    direct = _direct_category_query(prompt, categories)
    if direct is not None:
        text = _speak_items(direct)
        logger.info("todo_list: direct hit → %s", direct.get("name"))
        return {
            "text": text,
            "structured": {
                "intent": "todo list",
                "entities": {"category": direct.get("name", "")},
            },
        }

    # Ask which category.
    text = _speak_category_list(categories)
    logger.info("todo_list: asking which category (%d available)", len(categories))
    return {
        "text": text,
        "structured": {
            "intent": "todo list",
            "entities": {"stage": "await_category"},
            "pending_action": _pending("category", {}, question=text),
        },
    }
