"""Auto-audit tests for jane_web.jane_v2.classes.shopping_list.handler."""

from __future__ import annotations

import ast
import builtins
import importlib
import inspect
import math
import re
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


VESSENCE_ROOT = Path(__file__).resolve().parents[1]
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

MODULE_NAME = "jane_web.jane_v2.classes.shopping_list.handler"
METADATA_MODULE_NAME = "jane_web.jane_v2.classes.shopping_list.metadata"
MODULE_PATH = VESSENCE_ROOT / "jane_web/jane_v2/classes/shopping_list/handler.py"
METADATA_PATH = VESSENCE_ROOT / "jane_web/jane_v2/classes/shopping_list/metadata.py"
TODO_HANDLER_PATH = VESSENCE_ROOT / "jane_web/jane_v2/classes/todo_list/handler.py"


class _FakeShoppingStore:
    def __init__(self, initial: list[str] | tuple[str, ...] = ()):
        self.items = list(initial)
        self.module = ModuleType("agent_skills.shopping_list")
        self.module.add_item = Mock(side_effect=self.add_item)
        self.module.remove_item = Mock(side_effect=self.remove_item)
        self.module.get_list = Mock(side_effect=self.get_list)
        self.module.clear_list = Mock(side_effect=self.clear_list)

    def add_item(self, item: str, list_name: str = "default") -> list[str]:
        self.items.append(item)
        return list(self.items)

    def remove_item(
        self,
        item: str,
        list_name: str = "default",
        *,
        confidence: float,
    ) -> list[str]:
        needle = item.strip().lower()
        self.items = [current for current in self.items if current.lower() != needle]
        return list(self.items)

    def get_list(self, list_name: str = "default") -> list[str]:
        return list(self.items)

    def clear_list(self, list_name: str = "default", *, confidence: float) -> None:
        self.items.clear()
        return None


@pytest.fixture
def shopping_handler():
    return importlib.import_module(MODULE_NAME)


@pytest.fixture
def shopping_metadata():
    return importlib.import_module(METADATA_MODULE_NAME)


@pytest.fixture
def fake_store(monkeypatch):
    store = _FakeShoppingStore()
    monkeypatch.setitem(sys.modules, "agent_skills.shopping_list", store.module)
    return store


def _install_fake_store(monkeypatch, initial=()):
    store = _FakeShoppingStore(initial)
    monkeypatch.setitem(sys.modules, "agent_skills.shopping_list", store.module)
    return store


def _module_ast() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text())


def _source(path: Path = MODULE_PATH) -> str:
    return path.read_text()


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _assert_text_response(result: dict | None) -> None:
    assert isinstance(result, dict)
    assert isinstance(result.get("text"), str)
    assert result["text"]


def _actions_from_metadata_schema(shopping_metadata) -> set[str]:
    action_schema = shopping_metadata.PARAMS_SCHEMA["action"]
    match = re.search(r"one of:\s*([^.]*)\.", action_schema)
    assert match is not None
    return {piece.strip() for piece in match.group(1).split("|")}


def _action_branch_literals() -> set[str]:
    actions: set[str] = set()
    for node in ast.walk(_module_ast()):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "action":
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if (
                isinstance(op, ast.Eq)
                and isinstance(comparator, ast.Constant)
                and isinstance(comparator.value, str)
            ):
                actions.add(comparator.value)
    return actions


def _string_literals_in_path(path: Path) -> set[str]:
    values: set[str] = set()
    for node in ast.walk(ast.parse(_source(path))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.add(node.value)
    return values


def test_docstring_is_the_params_driven_stage2_spec(shopping_handler):
    doc = inspect.getdoc(shopping_handler)

    assert doc is not None
    assert "params-driven" in doc
    assert 'params["action"]' in doc
    assert "no local LLM intent parse" in doc
    assert "Escalates to Stage 3" in doc
    assert "add/remove/view/clear/check" in doc


def test_public_handler_contract_is_async_and_params_driven(shopping_handler):
    signature = inspect.signature(shopping_handler.handle)

    assert inspect.iscoroutinefunction(shopping_handler.handle)
    assert list(signature.parameters) == ["prompt", "params"]
    assert signature.parameters["params"].default is None
    assert isinstance(shopping_handler._VALID_ACTIONS, set)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, []),
        ("", []),
        ("   ", []),
        (",,,", []),
        ("milk", ["milk"]),
        (" milk , eggs , bread ", ["milk", "eggs", "bread"]),
        ("milk,, eggs,  , bread", ["milk", "eggs", "bread"]),
        (["milk"], []),
        (123, []),
    ],
)
def test_split_items_handles_empty_malformed_and_comma_separated_input(
    shopping_handler,
    raw,
    expected,
):
    assert shopping_handler._split_items(raw) == expected


def test_split_items_preserves_very_long_item_text(shopping_handler):
    long_item = "x" * 20_000

    assert shopping_handler._split_items(f" milk , {long_item} ") == [
        "milk",
        long_item,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [None, {}, []])
async def test_missing_or_empty_params_escalate_without_store_calls(
    shopping_handler,
    fake_store,
    params,
):
    result = await shopping_handler.handle("show my shopping list", params=params)

    assert result is None
    fake_store.module.add_item.assert_not_called()
    fake_store.module.remove_item.assert_not_called()
    fake_store.module.get_list.assert_not_called()
    fake_store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"items": "milk"},
        {"action": None, "items": "milk"},
        {"action": 123, "items": "milk"},
        {"action": ["add"], "items": "milk"},
        {"action": "archive", "items": "milk"},
        {"action": "others", "items": "milk"},
        {"action": "", "items": "milk"},
        {"action": "   ", "items": "milk"},
    ],
)
async def test_malformed_or_unknown_actions_escalate_without_store_calls(
    shopping_handler,
    fake_store,
    params,
):
    result = await shopping_handler.handle("shopping list", params=params)

    assert result is None
    fake_store.module.add_item.assert_not_called()
    fake_store.module.remove_item.assert_not_called()
    fake_store.module.get_list.assert_not_called()
    fake_store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
async def test_view_empty_list_returns_documented_text(shopping_handler, monkeypatch):
    store = _install_fake_store(monkeypatch, initial=())

    result = await shopping_handler.handle(
        "what is on my shopping list?",
        params={"action": "view", "items": None},
    )

    assert result == {"text": "Your shopping list is empty."}
    store.module.get_list.assert_called_once_with("default")
    store.module.add_item.assert_not_called()
    store.module.remove_item.assert_not_called()
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
async def test_view_populated_list_returns_joined_items(shopping_handler, monkeypatch):
    store = _install_fake_store(monkeypatch, initial=("milk", "eggs"))

    result = await shopping_handler.handle(
        "show my shopping list",
        params={"action": "view", "items": None},
    )

    assert result == {"text": "Your shopping list has: milk, eggs."}
    store.module.get_list.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_add_splits_items_writes_each_item_and_reports_count(
    shopping_handler,
    monkeypatch,
):
    store = _install_fake_store(monkeypatch, initial=("coffee",))

    result = await shopping_handler.handle(
        "add milk, eggs, bread",
        params={"action": " ADD ", "items": " milk, eggs,, bread "},
    )

    assert result == {
        "text": "Added milk, eggs, bread. Your shopping list now has 4 items."
    }
    assert store.items == ["coffee", "milk", "eggs", "bread"]
    assert store.module.add_item.call_args_list == [
        (("milk", "default"),),
        (("eggs", "default"),),
        (("bread", "default"),),
    ]
    store.module.get_list.assert_called_once_with("default")
    store.module.remove_item.assert_not_called()
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("items", [None, "", "   ", ",,,", 123])
async def test_add_without_items_escalates_without_mutating_store(
    shopping_handler,
    monkeypatch,
    items,
):
    store = _install_fake_store(monkeypatch, initial=("coffee",))

    result = await shopping_handler.handle(
        "add something",
        params={"action": "add", "items": items},
    )

    assert result is None
    assert store.items == ["coffee"]
    store.module.add_item.assert_not_called()
    store.module.get_list.assert_not_called()


@pytest.mark.asyncio
async def test_remove_requires_confidence_and_passes_it_to_store(
    shopping_handler,
    monkeypatch,
):
    store = _install_fake_store(monkeypatch, initial=("milk", "eggs", "Bread"))

    result = await shopping_handler.handle(
        "remove milk and bread",
        params={"action": "remove", "items": "milk, bread", "confidence": 0.80},
    )

    assert result == {"text": "Removed milk, bread from your shopping list."}
    assert store.items == ["eggs"]
    assert store.module.remove_item.call_args_list == [
        (("milk", "default"), {"confidence": 0.80}),
        (("bread", "default"), {"confidence": 0.80}),
    ]
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
async def test_clear_requires_confidence_and_passes_it_to_store(
    shopping_handler,
    monkeypatch,
):
    store = _install_fake_store(monkeypatch, initial=("milk", "eggs"))

    result = await shopping_handler.handle(
        "clear my shopping list",
        params={"action": "clear", "items": None, "confidence": 0.80},
    )

    assert result == {"text": "Your shopping list has been cleared."}
    assert store.items == []
    store.module.clear_list.assert_called_once_with("default", confidence=0.80)
    store.module.remove_item.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("items", [None, "", "   ", ",,,", 123])
async def test_remove_without_items_escalates_even_with_valid_confidence(
    shopping_handler,
    monkeypatch,
    items,
):
    store = _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        "remove it",
        params={"action": "remove", "items": items, "confidence": 0.80},
    )

    assert result is None
    assert store.items == ["milk"]
    store.module.remove_item.assert_not_called()
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
async def test_check_all_present_is_case_insensitive(shopping_handler, monkeypatch):
    store = _install_fake_store(monkeypatch, initial=("Milk", "Eggs"))

    result = await shopping_handler.handle(
        "do I need milk?",
        params={"action": "check", "items": "milk, EGGS"},
    )

    _assert_text_response(result)
    assert result["text"].startswith("Yes")
    assert "milk" in result["text"]
    assert "EGGS" in result["text"]
    store.module.get_list.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_check_all_missing_returns_no_text(shopping_handler, monkeypatch):
    _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        "do I need bread?",
        params={"action": "check", "items": "bread"},
    )

    _assert_text_response(result)
    assert result["text"].startswith("No")
    assert "bread" in result["text"]


@pytest.mark.asyncio
async def test_check_mixed_items_reports_present_and_missing(
    shopping_handler,
    monkeypatch,
):
    _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        "do I need milk or bread?",
        params={"action": "check", "items": "milk, bread"},
    )

    assert result == {"text": "Mixed: milk is on the list; bread is not."}


@pytest.mark.asyncio
@pytest.mark.parametrize("items", [None, "", "   ", ",,,", 123])
async def test_check_without_items_escalates_without_store_read(
    shopping_handler,
    monkeypatch,
    items,
):
    store = _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        "do I need it?",
        params={"action": "check", "items": items},
    )

    assert result is None
    store.module.get_list.assert_not_called()


@pytest.mark.asyncio
async def test_prompt_content_is_not_reparsed_when_params_are_complete(
    shopping_handler,
    monkeypatch,
):
    store = _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        "this prompt says clear, but params say view",
        params={"action": "view", "items": "ignored"},
    )

    assert result == {"text": "Your shopping list has: milk."}
    store.module.get_list.assert_called_once_with("default")
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
async def test_very_long_items_input_is_split_and_dispatched(
    shopping_handler,
    monkeypatch,
):
    item_names = [f"item{i}" for i in range(500)]
    store = _install_fake_store(monkeypatch)

    result = await shopping_handler.handle(
        "add many things",
        params={"action": "add", "items": ",".join(item_names)},
    )

    _assert_text_response(result)
    assert len(store.items) == len(item_names)
    assert store.items[:3] == ["item0", "item1", "item2"]
    assert store.items[-1] == "item499"
    assert store.module.add_item.call_count == 500


@pytest.mark.asyncio
async def test_agent_skills_import_failure_escalates(shopping_handler, monkeypatch):
    real_import = builtins.__import__

    def fail_shopping_list_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "agent_skills.shopping_list":
            raise ImportError("boom")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_shopping_list_import)

    result = await shopping_handler.handle(
        "show my shopping list",
        params={"action": "view", "items": None},
    )

    assert result is None


@pytest.mark.asyncio
async def test_view_integration_reads_json_store_adapter_without_writes(
    shopping_handler,
    monkeypatch,
):
    store = _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        "view",
        params={"action": "view", "items": None},
    )

    assert result == {"text": "Your shopping list has: milk."}
    store.module.get_list.assert_called_once_with("default")
    store.module.add_item.assert_not_called()
    store.module.remove_item.assert_not_called()
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
async def test_handler_has_no_db_or_llm_integration_calls(
    shopping_handler,
    monkeypatch,
):
    store = _install_fake_store(monkeypatch, initial=("milk",))

    forbidden_modules = {
        "openai": ModuleType("openai"),
        "ollama": ModuleType("ollama"),
        "httpx": ModuleType("httpx"),
        "sqlite3": ModuleType("sqlite3"),
        "pymysql": ModuleType("pymysql"),
        "sqlalchemy": ModuleType("sqlalchemy"),
    }
    for module in forbidden_modules.values():
        module.__getattr__ = Mock(
            side_effect=AssertionError("handler should not use DB or LLM modules")
        )
    for name, module in forbidden_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    result = await shopping_handler.handle(
        "prompt text is ignored",
        params={"action": "view", "items": None},
    )

    assert result == {"text": "Your shopping list has: milk."}
    store.module.get_list.assert_called_once_with("default")


def test_source_contains_no_db_or_llm_call_sites():
    tree = _module_ast()
    imported_roots: set[str] = set()
    call_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            call_names.add(_call_name(node.func).lower())

    assert imported_roots.isdisjoint(
        {"openai", "ollama", "httpx", "requests", "sqlite3", "pymysql", "sqlalchemy"}
    )
    assert not any(
        token in call_name
        for call_name in call_names
        for token in ("llm", "model", "completion", "chat", "execute", "query")
    )


def test_action_registry_matches_metadata_schema(shopping_handler, shopping_metadata):
    assert shopping_handler._VALID_ACTIONS == {
        "view",
        "add",
        "remove",
        "clear",
        "check",
    }
    assert shopping_handler._VALID_ACTIONS == _actions_from_metadata_schema(
        shopping_metadata
    )


def test_action_registry_has_no_fallback_or_confidence_labels(shopping_handler):
    contradictory_values = {
        "other",
        "others",
        "fallback",
        "unknown",
        "high",
        "medium",
        "low",
        "true",
        "false",
    }

    assert shopping_handler._VALID_ACTIONS.isdisjoint(contradictory_values)
    assert all(action == action.strip().lower() for action in shopping_handler._VALID_ACTIONS)


def test_every_action_branch_is_registered_and_every_registered_action_has_branch(
    shopping_handler,
):
    branch_actions = _action_branch_literals()

    assert branch_actions == shopping_handler._VALID_ACTIONS


def test_every_shopping_action_referenced_by_neighbor_handlers_is_registered(
    shopping_handler,
    shopping_metadata,
):
    metadata_actions = _actions_from_metadata_schema(shopping_metadata)
    todo_literals = _string_literals_in_path(TODO_HANDLER_PATH)
    todo_referenced_actions = {
        literal for literal in todo_literals if literal in metadata_actions
    }

    assert metadata_actions == shopping_handler._VALID_ACTIONS
    assert todo_referenced_actions
    assert todo_referenced_actions <= shopping_handler._VALID_ACTIONS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "params", "initial_items"),
    [
        ("view", {"action": "view", "items": None}, ("milk",)),
        ("add", {"action": "add", "items": "eggs"}, ("milk",)),
        ("remove", {"action": "remove", "items": "milk", "confidence": 0.80}, ("milk",)),
        ("clear", {"action": "clear", "items": None, "confidence": 0.80}, ("milk",)),
        ("check", {"action": "check", "items": "milk"}, ("milk",)),
    ],
)
async def test_every_registered_action_is_reachable_and_returns_text_shape(
    shopping_handler,
    monkeypatch,
    action,
    params,
    initial_items,
):
    assert action in shopping_handler._VALID_ACTIONS
    _install_fake_store(monkeypatch, initial=initial_items)

    result = await shopping_handler.handle(f"{action} shopping list", params=params)

    _assert_text_response(result)


def test_destructive_action_registry_matches_irreversible_store_calls(shopping_handler):
    source = _source()

    assert {"remove", "clear"} <= shopping_handler._VALID_ACTIONS
    assert "remove_item(" in source
    assert "clear_list(" in source
    assert "add_item(" in source
    assert "get_list(" in source


def test_destructive_confidence_guard_is_structurally_before_store_import():
    source = _source()

    confidence_guard_index = source.index('if action in {"remove", "clear"}:')
    threshold_index = source.index("confidence < 0.80")
    import_index = source.index("from agent_skills.shopping_list import")
    remove_call_index = source.index("remove_item(item, list_name, confidence=confidence)")
    clear_call_index = source.index("clear_list(list_name, confidence=confidence)")

    assert confidence_guard_index < threshold_index < import_index
    assert import_index < remove_call_index
    assert import_index < clear_call_index
    assert "isinstance(confidence, bool)" in source


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["remove", "clear"])
@pytest.mark.parametrize(
    "confidence",
    [None, True, False, "High", "0.95", object(), -1, 0, 0.79, 0.799999],
)
async def test_destructive_actions_block_non_numeric_and_borderline_confidence(
    shopping_handler,
    monkeypatch,
    action,
    confidence,
):
    store = _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        f"{action} shopping list",
        params={"action": action, "items": "milk", "confidence": confidence},
    )

    assert result is None
    assert store.items == ["milk"]
    store.module.remove_item.assert_not_called()
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["remove", "clear"])
@pytest.mark.parametrize("confidence", [math.nan, float("nan")])
async def test_destructive_actions_block_nan_confidence_as_ambiguous_input(
    shopping_handler,
    monkeypatch,
    action,
    confidence,
):
    store = _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        f"{action} shopping list",
        params={"action": action, "items": "milk", "confidence": confidence},
    )

    assert result is None
    assert store.items == ["milk"]
    store.module.remove_item.assert_not_called()
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("confidence", [0.80, 0.800001, 1, 1.0])
async def test_remove_allows_exact_threshold_and_above(
    shopping_handler,
    monkeypatch,
    confidence,
):
    store = _install_fake_store(monkeypatch, initial=("milk", "eggs"))

    result = await shopping_handler.handle(
        "remove milk",
        params={"action": "remove", "items": "milk", "confidence": confidence},
    )

    assert result == {"text": "Removed milk from your shopping list."}
    assert store.items == ["eggs"]
    store.module.remove_item.assert_called_once_with(
        "milk",
        "default",
        confidence=confidence,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("confidence", [0.80, 0.800001, 1, 1.0])
async def test_clear_allows_exact_threshold_and_above(
    shopping_handler,
    monkeypatch,
    confidence,
):
    store = _install_fake_store(monkeypatch, initial=("milk", "eggs"))

    result = await shopping_handler.handle(
        "clear shopping list",
        params={"action": "clear", "items": None, "confidence": confidence},
    )

    assert result == {"text": "Your shopping list has been cleared."}
    assert store.items == []
    store.module.clear_list.assert_called_once_with(
        "default",
        confidence=confidence,
    )


@pytest.mark.asyncio
async def test_destructive_action_with_unknown_action_name_cannot_fire(
    shopping_handler,
    monkeypatch,
):
    store = _install_fake_store(monkeypatch, initial=("milk",))

    result = await shopping_handler.handle(
        "delete all shopping items",
        params={"action": "delete", "items": "milk", "confidence": 1.0},
    )

    assert result is None
    assert store.items == ["milk"]
    store.module.remove_item.assert_not_called()
    store.module.clear_list.assert_not_called()


@pytest.mark.asyncio
async def test_registered_handler_results_have_documented_shape_for_all_actions(
    shopping_handler,
    monkeypatch,
):
    cases = [
        ({"action": "view", "items": None}, ("milk",)),
        ({"action": "add", "items": "eggs"}, ("milk",)),
        ({"action": "remove", "items": "milk", "confidence": 0.80}, ("milk",)),
        ({"action": "clear", "items": None, "confidence": 0.80}, ("milk",)),
        ({"action": "check", "items": "milk"}, ("milk",)),
    ]

    for params, initial_items in cases:
        store = _install_fake_store(monkeypatch, initial=initial_items)
        result = await shopping_handler.handle("shopping list", params=params)
        _assert_text_response(result)
        sys.modules["agent_skills.shopping_list"] = store.module
