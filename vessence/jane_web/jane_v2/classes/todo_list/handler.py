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

from dataclasses import dataclass
import logging
import os

from .cache import TODO_CACHE_PATH as _CACHE_PATH, load_todo_cache as _load_cache
from .categories import (
    CATEGORY_ALIASES as _CATEGORY_ALIASES,
    category_by_name_or_alias as _category_by_name_or_alias,
    direct_category_query as _direct_category_query,
    friendly_category_name as _friendly_category_name,
    match_category as _match_category,
    normalize as _normalize,
    speak_category_list as _speak_category_list,
    speak_items as _speak_items,
    visible_categories as _visible_categories,
)
from .parsing import (
    detect_edit_intent as _detect_edit_intent,
    extract_item_text as _extract_item_text,
    is_placeholder_item_text as _is_placeholder_item_text,
)
from .responses import (
    ask_add_category_response as _ask_add_category_response,
    ask_add_item_response as _ask_add_item_response,
    ask_category_response as _ask_category_response,
    ask_item_for_category_response as _ask_item_for_category_response,
    ask_remove_item_response as _ask_remove_item_response,
    build_todo_pending as _pending,
    confirm_item_then_ask_category_response as _confirm_item_then_ask_category_response,
    done_response as _done_response,
    empty_list_response as _empty_list_response,
    missing_cache_response as _missing_cache_response,
    read_and_ask_another as _read_and_ask_another,
    simple_todo_response as _simple_todo_response,
    todo_pending_expires_at as _expires_at,
)

logger = logging.getLogger(__name__)


_EDIT_RESUME_AWAITING = {
    "add_category",
    "add_category_then_item",
    "add_item_for_category",
    "add_item",
    "remove_item",
}


@dataclass(frozen=True)
class _TodoActionParams:
    action: str | None = None
    item: str | None = None
    category: str | None = None


def _todo_action_params(params: dict | None) -> _TodoActionParams:
    if not params:
        return _TodoActionParams()
    return _TodoActionParams(
        action=(params.get("action") or "").strip().lower() or None,
        item=(params.get("item") or "").strip() or None,
        category=(params.get("category") or "").strip() or None,
    )


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


async def _handle_edit(
    prompt: str,
    edit_type: str,
    categories: list[dict],
    item_text: str | None = None,
    category_name: str | None = None,
    from_params: bool = False,
) -> dict | None:
    """Handle an add or remove edit request.

    When `from_params=True` (params-driven path), trust the provided
    item_text / category_name verbatim and skip the prompt-regex
    extraction. Otherwise fall back to extracting from the prompt —
    preserves the v2 (no-params) code path.
    """
    if not from_params and item_text is None:
        item_text = _extract_item_text(prompt, edit_type)
    if _is_placeholder_item_text(item_text):
        item_text = None
    cat = None
    if category_name:
        cat = _category_by_name_or_alias(category_name, categories)
    if cat is None:
        cat = _match_category(prompt, categories)

    if edit_type == "add":
        if not item_text and cat:
            return _ask_item_for_category_response(cat["name"])
        if not item_text:
            return _ask_add_category_response(categories)
        if not cat:
            return _ask_add_category_response(categories, item_text=item_text)
        try:
            from agent_skills.docs_tools import todo_add_item
            result = todo_add_item(item_text, cat["name"])
            _refresh_cache()
            return _done_response(result, entities={"action": "add", "category": cat["name"]})
        except Exception as e:
            logger.error("todo_list: add failed: %s", e)
            return _simple_todo_response(f"I couldn't add that item. The error was: {e}")

    elif edit_type == "remove":
        if not item_text:
            return _ask_remove_item_response()
        try:
            from agent_skills.docs_tools import todo_remove_item
            result = todo_remove_item(item_text, category=cat["name"] if cat else None)
            _refresh_cache()
            return _done_response(result, entities={"action": "remove"})
        except Exception as e:
            logger.error("todo_list: remove failed: %s", e)
            return _simple_todo_response(f"I couldn't remove that item. The error was: {e}")

    return None


def _todo_pending_data(pending: dict) -> dict:
    # The pipeline passes pending.data for Stage 2 follow-ups. Some tests and
    # older callers still pass the full pending_action wrapper, so accept both.
    if isinstance(pending.get("data"), dict):
        return pending["data"]
    return pending if isinstance(pending, dict) else {}


def _todo_pending_awaiting(pending: dict, pending_data: dict) -> str:
    return pending_data.get("awaiting", "") or pending.get("awaiting", "")


async def _resume_add_category(prompt: str, pending_data: dict, categories: list[dict]) -> dict | None:
    item_text = pending_data.get("item_text", "")
    cat = _match_category(prompt, categories)
    if cat is None:
        logger.info("todo_list: no category match for add -> abandon")
        return {"abandon_pending": True}
    try:
        from agent_skills.docs_tools import todo_add_item
        result = todo_add_item(item_text, cat["name"])
        _refresh_cache()
        return _done_response(result, entities={"action": "add", "category": cat["name"]})
    except Exception as e:
        logger.error("todo_list: add (resume) failed: %s", e)
        return _simple_todo_response(f"I couldn't add that. Error: {e}")


async def _resume_add_category_then_item(prompt: str, categories: list[dict]) -> dict | None:
    cat = _match_category(prompt, categories)
    if cat is None:
        logger.info("todo_list: no category match for add slot -> abandon")
        return {"abandon_pending": True}
    return _ask_item_for_category_response(cat["name"])


async def _resume_add_item_for_category(
    prompt: str,
    pending_data: dict,
    categories: list[dict],
) -> dict | None:
    item_text = prompt.strip()
    category_name = pending_data.get("category", "")
    if not item_text or _is_placeholder_item_text(item_text):
        return _ask_item_for_category_response(category_name)
    cat = next((c for c in categories if c.get("name") == category_name), None)
    if cat is None:
        logger.info("todo_list: saved add category missing -> abandon")
        return {"abandon_pending": True}
    try:
        from agent_skills.docs_tools import todo_add_item
        result = todo_add_item(item_text, cat["name"])
        _refresh_cache()
        return _done_response(
            result,
            entities={
                "action": "add",
                "category": cat["name"],
                "item_text": item_text,
            },
        )
    except Exception as e:
        logger.error("todo_list: add item for category failed: %s", e)
        return _simple_todo_response(f"Couldn't add that. Error: {e}")


async def _resume_add_item(prompt: str, categories: list[dict]) -> dict | None:
    item_text = prompt.strip()
    if _is_placeholder_item_text(item_text):
        return _ask_add_item_response()
    cat = _match_category(prompt, categories)
    if cat and (prompt.strip().lower() in {
        cat.get("name", "").strip().lower(),
        _friendly_category_name(cat.get("name", "")).strip().lower(),
        "urgent",
        "urgent stuff",
    }):
        return _ask_item_for_category_response(cat["name"])
    if not cat:
        return _confirm_item_then_ask_category_response(item_text)
    try:
        from agent_skills.docs_tools import todo_add_item
        result = todo_add_item(item_text, cat["name"])
        _refresh_cache()
        return _done_response(result)
    except Exception as e:
        return _simple_todo_response(f"Couldn't add that. Error: {e}")


async def _resume_remove_item(prompt: str) -> dict | None:
    try:
        from agent_skills.docs_tools import todo_remove_item
        result = todo_remove_item(prompt.strip())
        _refresh_cache()
        return _done_response(result)
    except Exception as e:
        return _simple_todo_response(f"Couldn't remove that. Error: {e}")


async def _handle_resume_edit(
    prompt: str,
    pending_data: dict,
    awaiting: str,
    categories: list[dict],
) -> tuple[bool, dict | None]:
    if awaiting not in _EDIT_RESUME_AWAITING:
        return False, None
    if awaiting == "add_category":
        return True, await _resume_add_category(prompt, pending_data, categories)
    if awaiting == "add_category_then_item":
        return True, await _resume_add_category_then_item(prompt, categories)
    if awaiting == "add_item_for_category":
        return True, await _resume_add_item_for_category(prompt, pending_data, categories)
    if awaiting == "add_item":
        return True, await _resume_add_item(prompt, categories)
    return True, await _resume_remove_item(prompt)


async def _handle_params_edit(
    prompt: str,
    categories: list[dict],
    parsed: _TodoActionParams,
) -> tuple[bool, dict | None]:
    if parsed.action not in {"add", "remove"}:
        return False, None

    logger.info("todo_list: params-driven edit → %s", parsed.action)
    return True, await _handle_edit(
        prompt,
        parsed.action,
        categories,
        item_text=parsed.item,
        category_name=parsed.category,
        from_params=True,
    )


def _should_decline_ambient_project(prompt: str) -> bool:
    p_lower = (prompt or "").lower()
    return "ambient" in p_lower and "project" in p_lower


def _shopping_list_params(params: dict | None) -> dict | None:
    if not params or params.get("action") not in {"add", "remove", "view", "clear", "check"}:
        return None
    action = params.get("action")
    return {
        "action": "add" if action == "add" else "remove" if action == "remove" else "view",
        "items": params.get("item"),
    }


async def _maybe_delegate_shopping_list(prompt: str, params: dict | None) -> tuple[bool, dict | None]:
    if "shopping" not in (prompt or "").lower():
        return False, None
    try:
        from jane_web.jane_v2.classes.shopping_list import handler as _shop
    except Exception as e:
        logger.warning("todo_list: shopping_list import failed: %s", e)
        return False, None

    logger.info("todo_list: shopping-list prompt detected -> delegate")
    return True, await _shop.handle(prompt, params=_shopping_list_params(params))


def _first_turn_read_response(
    prompt: str,
    categories: list[dict],
    parsed_params: _TodoActionParams,
) -> dict:
    if not categories:
        return _empty_list_response()

    if parsed_params.category:
        cat = _category_by_name_or_alias(parsed_params.category, _visible_categories(categories))
        if cat is not None:
            logger.info("todo_list: params category hit -> %s", cat.get("name"))
            return _read_and_ask_another(cat, categories)

    direct = _direct_category_query(prompt, categories)
    if direct is not None:
        logger.info("todo_list: direct hit -> %s", direct.get("name"))
        return _read_and_ask_another(direct, categories)

    logger.info("todo_list: asking which category (%d available)", len(categories))
    return _ask_category_response(categories)


# Pivot detection REMOVED 2026-04-17. Prefix/substring heuristics were
# brittle (new pivot phrases always leaked through) and duplicated across
# every handler. Detection is now centralized in
# stage2_dispatcher._continuation_check, which runs the qwen2.5:7b gate
# against the literal question stored in pending["question"]. See
# handler `_pending()` below.


# ── Resume handler (follow-up turn after we asked "which?") ─────────────────
async def _handle_resume(prompt: str, pending: dict) -> dict | None:
    # Pivot detection is now the dispatcher's job — see
    # stage2_dispatcher._continuation_check, which runs the qwen2.5:7b gate
    # with the literal question we stored in `pending["question"]`. The
    # legacy `_looks_like_pivot` prefix heuristic was removed 2026-04-17.
    cache = _load_cache()
    if cache is None:
        return _missing_cache_response()

    categories = cache.get("categories") or []

    pending_data = _todo_pending_data(pending)
    awaiting = _todo_pending_awaiting(pending, pending_data)

    handled_edit, edit_response = await _handle_resume_edit(
        prompt,
        pending_data,
        awaiting,
        categories,
    )
    if handled_edit:
        return edit_response

    # End-of-conversation phrase: user is done with the list.
    from agent_skills import end_phrase
    from agent_skills.private_handler_utils import end_conversation

    if end_phrase.is_end(prompt):
        logger.info("todo_list: end-phrase on resume — closing conversation")
        return end_conversation("Ok.", structured={"intent": "todo list"})

    # Reading flow — match a category. The repeating-read pattern: after
    # we read items, we ask "want another?" via pending; the user's reply
    # comes back here and we either read another category or end.
    already_read = pending_data.get("already_read") or []
    cat = _match_category(prompt, categories)
    if cat is None:
        logger.info("todo_list: no category match on resume → escalate to Stage 3")
        return {"abandon_pending": True, "force_stage3": True}

    if cat.get("name") in already_read:
        logger.info("todo_list: user re-asked already-read category %s → escalate",
                    cat.get("name"))
        return {"abandon_pending": True, "force_stage3": True}

    logger.info("todo_list: resumed → %s", cat.get("name"))
    return _read_and_ask_another(cat, categories, already_read=already_read)


# ── Main entry ──────────────────────────────────────────────────────────────
async def handle(
    prompt: str,
    context: str = "",
    pending: dict | None = None,
    params: dict | None = None,
) -> dict | None:
    if pending:
        return await _handle_resume(prompt, pending)

    # Defense in depth: if Stage 1 classifier misroutes an Ambient-project
    # prompt to this handler (rare but possible on borderline phrasings),
    # decline so the pipeline escalates to Stage 3 instead of asking
    # "which category?" from the remaining visible categories.
    if _should_decline_ambient_project(prompt):
        logger.info("todo_list: ambient-project prompt detected -> escalate")
        return None

    # Stage 1 sometimes mis-embeds "shopping list" queries as todo_list
    # because both share the word "list". Hand off to the shopping_list
    # handler directly so the user gets a fast answer instead of a
    # "which todo category?" prompt.
    delegated, shopping_response = await _maybe_delegate_shopping_list(prompt, params)
    if delegated:
        return shopping_response

    cache = _load_cache()
    if cache is None:
        return _missing_cache_response()

    categories = cache.get("categories") or []

    # Resolve action / item / category from params first, then fall back
    # to regex extraction so the v2 (no-params) path keeps working.
    parsed_params = _todo_action_params(params)
    params_handled, params_response = await _handle_params_edit(
        prompt,
        categories,
        parsed_params,
    )
    if params_handled:
        return params_response

    if parsed_params.action is None:
        edit_type = _detect_edit_intent(prompt)
        if edit_type:
            logger.info("todo_list: edit intent (regex) → %s", edit_type)
            return await _handle_edit(prompt, edit_type, categories)

    return _first_turn_read_response(prompt, categories, parsed_params)
