"""Comprehensive audit tests for jane_web.jane_v2.classes.shopping_list.handler.

Covers behavioral correctness, edge cases, integration mocks, and structural
invariants for the Stage 2 shopping_list handler (params-driven dispatcher
that operates on a JSON store via add/remove/view/clear/check actions).
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_VESSENCE = Path(__file__).resolve().parents[1]
for p in [str(_VESSENCE), str(_VESSENCE / "agent_skills")]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _isolate_handler():
    """Purge cached handler module so each test gets a fresh import."""
    key = "jane_web.jane_v2.classes.shopping_list.handler"
    cached = sys.modules.pop(key, None)
    yield
    if cached is not None:
        sys.modules[key] = cached


def _import_handler():
    from jane_web.jane_v2.classes.shopping_list.handler import (
        handle, _VALID_ACTIONS, _split_items,
    )
    return handle, _VALID_ACTIONS, _split_items


@pytest.fixture
def mock_store():
    """Patch agent_skills.shopping_list with an in-memory store."""
    store: dict[str, list[str]] = {"default": []}

    def _get_list(name="default"):
        return list(store.get(name, []))

    def _add_item(item, list_name="default"):
        if list_name not in store:
            store[list_name] = []
        if item.lower() not in [i.lower() for i in store[list_name]]:
            store[list_name].append(item)
        return list(store[list_name])

    def _remove_item(item, list_name="default"):
        if list_name in store:
            store[list_name] = [
                i for i in store[list_name] if i.lower() != item.lower()
            ]
        return list(store.get(list_name, []))

    def _clear_list(list_name="default"):
        store[list_name] = []

    mod = MagicMock()
    mod.get_list = MagicMock(side_effect=_get_list)
    mod.add_item = MagicMock(side_effect=_add_item)
    mod.remove_item = MagicMock(side_effect=_remove_item)
    mod.clear_list = MagicMock(side_effect=_clear_list)

    with patch.dict(sys.modules, {
        "agent_skills.shopping_list": mod,
        "agent_skills": MagicMock(),
    }):
        yield mod, store


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BEHAVIORAL TESTS — documented behavior from docstring
# ═══════════════════════════════════════════════════════════════════════════════


class TestViewAction:

    def test_view_empty_list(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("show my list", params={"action": "view"}))
        assert result == {"text": "Your shopping list is empty."}

    def test_view_populated_list(self, mock_store):
        _, store = mock_store
        store["default"] = ["milk", "eggs"]
        handle, *_ = _import_handler()
        result = _run(handle("show my list", params={"action": "view"}))
        assert result is not None
        assert "milk" in result["text"]
        assert "eggs" in result["text"]


class TestAddAction:

    def test_add_single_item(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("add milk", params={"action": "add", "items": "milk"}))
        assert result is not None
        assert "Added milk" in result["text"]
        assert "1 items" in result["text"]

    def test_add_multiple_items(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("add stuff", params={"action": "add", "items": "milk, eggs"}))
        assert "milk" in result["text"]
        assert "eggs" in result["text"]
        assert "2 items" in result["text"]

    def test_add_no_items_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("add", params={"action": "add"})) is None

    def test_add_null_items_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("add", params={"action": "add", "items": None})) is None

    def test_add_empty_string_items_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("add", params={"action": "add", "items": ""})) is None


class TestRemoveAction:

    def test_remove_existing_item(self, mock_store):
        _, store = mock_store
        store["default"] = ["milk", "eggs"]
        handle, *_ = _import_handler()
        result = _run(handle("remove milk", params={"action": "remove", "items": "milk"}))
        assert "Removed milk" in result["text"]

    def test_remove_multiple_items(self, mock_store):
        _, store = mock_store
        store["default"] = ["milk", "eggs", "bread"]
        handle, *_ = _import_handler()
        result = _run(handle("remove", params={"action": "remove", "items": "milk, eggs"}))
        assert "milk" in result["text"]
        assert "eggs" in result["text"]

    def test_remove_no_items_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("remove", params={"action": "remove"})) is None


class TestClearAction:

    def test_clear_wipes_list(self, mock_store):
        _, store = mock_store
        store["default"] = ["milk", "eggs", "bread"]
        handle, *_ = _import_handler()
        result = _run(handle("clear it", params={"action": "clear"}))
        assert result == {"text": "Your shopping list has been cleared."}
        assert store["default"] == []

    def test_clear_empty_list_still_responds(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("clear", params={"action": "clear"}))
        assert result == {"text": "Your shopping list has been cleared."}


class TestCheckAction:

    def test_check_present_item(self, mock_store):
        _, store = mock_store
        store["default"] = ["milk", "eggs"]
        handle, *_ = _import_handler()
        result = _run(handle("is milk there?", params={"action": "check", "items": "milk"}))
        assert "Yes" in result["text"]

    def test_check_missing_item(self, mock_store):
        _, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        result = _run(handle("is bread there?", params={"action": "check", "items": "bread"}))
        assert "No" in result["text"]

    def test_check_mixed_present_and_missing(self, mock_store):
        _, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        result = _run(handle("check", params={"action": "check", "items": "milk, bread"}))
        assert "Mixed" in result["text"]
        assert "milk" in result["text"]
        assert "bread" in result["text"]

    def test_check_no_items_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("check", params={"action": "check"})) is None


class TestEscalation:
    """Docstring: escalates to Stage 3 when params missing or action unknown."""

    def test_no_params_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("buy groceries", params=None)) is None

    def test_unknown_action_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("sort", params={"action": "sort"})) is None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_empty_params_dict_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("x", params={})) is None

    def test_action_is_none_escalates(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("x", params={"action": None})) is None

    def test_action_with_leading_trailing_whitespace(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("view", params={"action": "  view  "}))
        assert result is not None and "text" in result

    def test_action_uppercase(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("view", params={"action": "VIEW"}))
        assert result is not None

    def test_action_mixed_case(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("view", params={"action": "View"}))
        assert result is not None

    def test_items_with_extra_commas(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("add", params={"action": "add", "items": ",milk,,eggs,,"}))
        assert "2 items" in result["text"]

    def test_items_all_whitespace_commas(self, mock_store):
        handle, *_ = _import_handler()
        assert _run(handle("add", params={"action": "add", "items": " , , "})) is None

    def test_items_as_integer(self, mock_store):
        """_split_items casts via str(), so non-string types should work."""
        handle, *_ = _import_handler()
        result = _run(handle("add", params={"action": "add", "items": 42}))
        assert result is not None
        assert "42" in result["text"]

    def test_very_long_item_name(self, mock_store):
        handle, *_ = _import_handler()
        long_item = "a" * 5000
        result = _run(handle("add", params={"action": "add", "items": long_item}))
        assert result is not None
        assert "1 items" in result["text"]

    def test_200_items(self, mock_store):
        handle, *_ = _import_handler()
        items_str = ", ".join(f"item{i}" for i in range(200))
        result = _run(handle("add", params={"action": "add", "items": items_str}))
        assert "200 items" in result["text"]

    def test_prompt_text_irrelevant_to_dispatch(self, mock_store):
        """Handler ignores prompt — only params matter."""
        handle, *_ = _import_handler()
        result = _run(handle("completely unrelated text", params={"action": "view"}))
        assert result is not None

    def test_extra_params_keys_ignored(self, mock_store):
        handle, *_ = _import_handler()
        result = _run(handle("view", params={"action": "view", "foo": 1, "bar": "x"}))
        assert result is not None

    @pytest.mark.parametrize("action", [
        "sort", "buy", "update", "move", "merge", "share", "print",
        "viewx", "add!", "  ", "",
    ])
    def test_invalid_actions_escalate(self, mock_store, action):
        handle, *_ = _import_handler()
        assert _run(handle("x", params={"action": action})) is None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. INTEGRATION POINTS — mock agent_skills.shopping_list
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegrationPoints:

    def test_import_failure_escalates(self):
        """If agent_skills.shopping_list fails to import, handler returns None."""
        with patch.dict(sys.modules, {"agent_skills.shopping_list": None}):
            handle, *_ = _import_handler()
            result = _run(handle("view", params={"action": "view"}))
            assert result is None

    def test_add_calls_add_item_per_item(self, mock_store):
        mod, _ = mock_store
        handle, *_ = _import_handler()
        _run(handle("add", params={"action": "add", "items": "milk, eggs, bread"}))
        assert mod.add_item.call_count == 3
        called_items = [c.args[0] for c in mod.add_item.call_args_list]
        assert called_items == ["milk", "eggs", "bread"]

    def test_add_passes_default_list_name(self, mock_store):
        mod, _ = mock_store
        handle, *_ = _import_handler()
        _run(handle("add", params={"action": "add", "items": "milk"}))
        mod.add_item.assert_called_once_with("milk", "default")

    def test_remove_calls_remove_item_per_item(self, mock_store):
        mod, store = mock_store
        store["default"] = ["milk", "eggs"]
        handle, *_ = _import_handler()
        _run(handle("remove", params={"action": "remove", "items": "milk, eggs"}))
        assert mod.remove_item.call_count == 2

    def test_remove_passes_default_list_name(self, mock_store):
        mod, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        _run(handle("remove", params={"action": "remove", "items": "milk"}))
        mod.remove_item.assert_called_once_with("milk", "default")

    def test_clear_calls_clear_list(self, mock_store):
        mod, _ = mock_store
        handle, *_ = _import_handler()
        _run(handle("clear", params={"action": "clear"}))
        mod.clear_list.assert_called_once_with("default")

    def test_view_calls_get_list(self, mock_store):
        mod, _ = mock_store
        handle, *_ = _import_handler()
        _run(handle("view", params={"action": "view"}))
        mod.get_list.assert_called_once_with("default")

    def test_check_calls_get_list(self, mock_store):
        mod, _ = mock_store
        handle, *_ = _import_handler()
        _run(handle("check", params={"action": "check", "items": "milk"}))
        mod.get_list.assert_called_once_with("default")

    def test_add_then_view_reflects_state(self, mock_store):
        handle, *_ = _import_handler()
        _run(handle("add", params={"action": "add", "items": "milk, eggs"}))
        result = _run(handle("view", params={"action": "view"}))
        assert "milk" in result["text"]
        assert "eggs" in result["text"]

    def test_add_remove_view_sequence(self, mock_store):
        handle, *_ = _import_handler()
        _run(handle("add", params={"action": "add", "items": "milk, eggs, bread"}))
        _run(handle("remove", params={"action": "remove", "items": "eggs"}))
        result = _run(handle("view", params={"action": "view"}))
        assert "eggs" not in result["text"]
        assert "milk" in result["text"]
        assert "bread" in result["text"]

    def test_add_clear_view_empty(self, mock_store):
        handle, *_ = _import_handler()
        _run(handle("add", params={"action": "add", "items": "milk"}))
        _run(handle("clear", params={"action": "clear"}))
        result = _run(handle("view", params={"action": "view"}))
        assert result == {"text": "Your shopping list is empty."}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. STRUCTURAL INVARIANTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStructuralInvariants:

    # ── 4a. _VALID_ACTIONS registry consistency ────────────────────────────

    def test_valid_actions_matches_metadata_schema(self):
        """_VALID_ACTIONS must exactly match the enum in PARAMS_SCHEMA."""
        _, _VALID_ACTIONS, _ = _import_handler()
        expected = {"view", "add", "remove", "clear", "check"}
        assert _VALID_ACTIONS == expected

    def test_every_valid_action_has_handler_branch(self, mock_store):
        """Every key in _VALID_ACTIONS must produce a non-None result
        when given valid input (i.e., every key is reachable)."""
        _, store = mock_store
        store["default"] = ["testitem"]
        handle, _VALID_ACTIONS, _ = _import_handler()

        needs_items = {"add", "remove", "check"}
        for action in _VALID_ACTIONS:
            params = {"action": action}
            if action in needs_items:
                params["items"] = "testitem"
            result = _run(handle("test", params=params))
            assert result is not None, (
                f"Action '{action}' returned None with valid input — "
                f"dead key in _VALID_ACTIONS"
            )
            assert "text" in result, (
                f"Action '{action}' result missing 'text' key"
            )

    def test_no_action_outside_valid_set_returns_response(self, mock_store):
        """Only _VALID_ACTIONS keys can produce a response; everything
        else must escalate (return None)."""
        handle, _VALID_ACTIONS, _ = _import_handler()
        bogus_actions = [
            "sort", "update", "buy", "edit", "rename", "move",
            "merge", "share", "print", "export", "archive",
        ]
        for action in bogus_actions:
            assert action not in _VALID_ACTIONS
            result = _run(handle("x", params={"action": action, "items": "milk"}))
            assert result is None, (
                f"Action '{action}' NOT in _VALID_ACTIONS but still returned a response"
            )

    # ── 4b. Return shape: every branch returns {"text": str} or None ──────

    @pytest.mark.parametrize("action,items,seed", [
        ("view", None, []),
        ("view", None, ["milk"]),
        ("add", "milk", []),
        ("remove", "milk", ["milk"]),
        ("clear", None, ["milk"]),
        ("check", "milk", ["milk"]),
        ("check", "bread", ["milk"]),
        ("check", "milk, bread", ["milk"]),
    ])
    def test_return_shape_dict_with_text_or_none(self, mock_store, action, items, seed):
        _, store = mock_store
        store["default"] = list(seed)
        handle, *_ = _import_handler()
        params = {"action": action}
        if items is not None:
            params["items"] = items
        result = _run(handle("test", params=params))
        if result is not None:
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            assert "text" in result, f"Result missing 'text' key: {result}"
            assert isinstance(result["text"], str), f"'text' is not a string"

    # ── 4c. Destructive operations: clear and remove ──────────────────────

    def test_clear_is_destructive(self, mock_store):
        """clear wipes the entire list — verify it actually empties the store."""
        _, store = mock_store
        store["default"] = ["milk", "eggs", "bread"]
        handle, *_ = _import_handler()
        _run(handle("clear", params={"action": "clear"}))
        assert store["default"] == []

    def test_remove_nonexistent_item_succeeds_silently(self, mock_store):
        """Removing an item not on the list should not error."""
        _, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        result = _run(handle("remove", params={"action": "remove", "items": "bread"}))
        assert result is not None
        assert "Removed bread" in result["text"]

    # ── 4d. Read-only actions must not mutate ─────────────────────────────

    def test_view_does_not_mutate(self, mock_store):
        mod, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        _run(handle("view", params={"action": "view"}))
        mod.add_item.assert_not_called()
        mod.remove_item.assert_not_called()
        mod.clear_list.assert_not_called()

    def test_check_does_not_mutate(self, mock_store):
        mod, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        _run(handle("check", params={"action": "check", "items": "milk"}))
        mod.add_item.assert_not_called()
        mod.remove_item.assert_not_called()
        mod.clear_list.assert_not_called()

    def test_add_does_not_remove_or_clear(self, mock_store):
        mod, _ = mock_store
        handle, *_ = _import_handler()
        _run(handle("add", params={"action": "add", "items": "milk"}))
        mod.remove_item.assert_not_called()
        mod.clear_list.assert_not_called()

    def test_remove_does_not_add_or_clear(self, mock_store):
        mod, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        _run(handle("remove", params={"action": "remove", "items": "milk"}))
        mod.add_item.assert_not_called()
        mod.clear_list.assert_not_called()

    # ── 4e. Escalation paths: None means Stage 3 ─────────────────────────

    @pytest.mark.parametrize("params", [
        None,
        {},
        {"action": ""},
        {"action": "sort"},
        {"action": "buy"},
        {"action": "update"},
        {"action": "  "},
    ])
    def test_invalid_params_always_return_none(self, mock_store, params):
        handle, *_ = _import_handler()
        result = _run(handle("anything", params=params))
        assert result is None

    @pytest.mark.parametrize("action", ["add", "remove", "check"])
    def test_item_required_actions_escalate_without_items(self, mock_store, action):
        handle, *_ = _import_handler()
        assert _run(handle("test", params={"action": action})) is None
        assert _run(handle("test", params={"action": action, "items": None})) is None
        assert _run(handle("test", params={"action": action, "items": ""})) is None

    # ── 4f. Handler interface contract ────────────────────────────────────

    def test_handle_is_async(self):
        handle, *_ = _import_handler()
        assert asyncio.iscoroutinefunction(handle)

    def test_handle_signature(self):
        handle, *_ = _import_handler()
        sig = inspect.signature(handle)
        params = list(sig.parameters.keys())
        assert "prompt" in params
        assert "params" in params

    def test_handle_idempotent_view(self, mock_store):
        """Calling view multiple times yields identical results."""
        _, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        r1 = _run(handle("view", params={"action": "view"}))
        r2 = _run(handle("view", params={"action": "view"}))
        assert r1 == r2


# ═══════════════════════════════════════════════════════════════════════════════
# 5. _split_items unit tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSplitItems:

    def test_none_returns_empty(self):
        _, _, _split_items = _import_handler()
        assert _split_items(None) == []

    def test_empty_string_returns_empty(self):
        _, _, _split_items = _import_handler()
        assert _split_items("") == []

    def test_single_item(self):
        _, _, _split_items = _import_handler()
        assert _split_items("milk") == ["milk"]

    def test_multiple_comma_separated(self):
        _, _, _split_items = _import_handler()
        assert _split_items("milk, eggs, bread") == ["milk", "eggs", "bread"]

    def test_strips_whitespace(self):
        _, _, _split_items = _import_handler()
        assert _split_items("  milk ,  eggs  ") == ["milk", "eggs"]

    def test_filters_empty_segments(self):
        _, _, _split_items = _import_handler()
        assert _split_items(",,,milk,,,") == ["milk"]

    def test_all_commas_and_spaces(self):
        _, _, _split_items = _import_handler()
        assert _split_items(" , , , ") == []

    def test_non_string_coerced(self):
        _, _, _split_items = _import_handler()
        assert _split_items(123) == ["123"]

    def test_false_value_zero(self):
        _, _, _split_items = _import_handler()
        assert _split_items(0) == []

    def test_false_value_empty_list(self):
        _, _, _split_items = _import_handler()
        assert _split_items([]) == []


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Case sensitivity
# ═══════════════════════════════════════════════════════════════════════════════


class TestCaseSensitivity:

    def test_check_lowercase_query_uppercase_store(self, mock_store):
        _, store = mock_store
        store["default"] = ["Milk"]
        handle, *_ = _import_handler()
        result = _run(handle("check", params={"action": "check", "items": "milk"}))
        assert "Yes" in result["text"]

    def test_check_uppercase_query_lowercase_store(self, mock_store):
        _, store = mock_store
        store["default"] = ["milk"]
        handle, *_ = _import_handler()
        result = _run(handle("check", params={"action": "check", "items": "MILK"}))
        assert "Yes" in result["text"]

    def test_check_mixed_case(self, mock_store):
        _, store = mock_store
        store["default"] = ["MiLk"]
        handle, *_ = _import_handler()
        result = _run(handle("check", params={"action": "check", "items": "mIlK"}))
        assert "Yes" in result["text"]


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Metadata alignment
# ═══════════════════════════════════════════════════════════════════════════════


class TestMetadataAlignment:

    def test_params_schema_actions_match_valid_actions(self):
        """The PARAMS_SCHEMA enum values must match _VALID_ACTIONS exactly."""
        try:
            from jane_web.jane_v2.classes.shopping_list.metadata import PARAMS_SCHEMA
        except ImportError:
            pytest.skip("metadata.py not importable")
        _, _VALID_ACTIONS, _ = _import_handler()
        schema_action = PARAMS_SCHEMA.get("action", "")
        for action in _VALID_ACTIONS:
            assert action in schema_action, (
                f"Action '{action}' in _VALID_ACTIONS but not in PARAMS_SCHEMA"
            )

    def test_metadata_has_required_keys(self):
        try:
            from jane_web.jane_v2.classes.shopping_list.metadata import METADATA
        except ImportError:
            pytest.skip("metadata.py not importable")
        assert "few_shot" in METADATA
        assert "escalation_context" in METADATA
        assert callable(METADATA["escalation_context"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
