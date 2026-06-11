from __future__ import annotations

import ast
import builtins
import re
import sys
import types
from pathlib import Path
from typing import Any, Callable
from unittest.mock import AsyncMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = (
    REPO_ROOT / "jane_web" / "jane_v2" / "classes" / "shopping_list" / "handler.py"
)
METADATA_PATH = MODULE_PATH.with_name("metadata.py")

from jane_web.jane_v2 import classes as class_registry
from jane_web.jane_v2 import stage2_dispatcher
from jane_web.jane_v2.classes.shopping_list import handler as shopping_handler
from jane_web.jane_v2.classes.shopping_list import metadata as shopping_metadata


DB_AND_LLM_IMPORT_ROOTS = {
    "anthropic",
    "chromadb",
    "google.generativeai",
    "httpx",
    "mysql",
    "openai",
    "psycopg",
    "psycopg2",
    "pymysql",
    "requests",
    "sqlite3",
    "sqlalchemy",
}

FALLBACK_CLASSES = {"delegate opus", "others", "unclear"}
DESTRUCTIVE_ACTIONS = {"remove", "clear"}


class FakeShoppingStore:
    def __init__(self, initial: list[str] | None = None) -> None:
        self.data: dict[str, list[str]] = {"default": list(initial or [])}
        self.calls: list[tuple[Any, ...]] = []

    def module(self) -> types.ModuleType:
        mod = types.ModuleType("agent_skills.shopping_list")
        mod.add_item = self.add_item
        mod.remove_item = self.remove_item
        mod.get_list = self.get_list
        mod.clear_list = self.clear_list
        return mod

    def get_list(self, list_name: str = "default") -> list[str]:
        self.calls.append(("get_list", list_name))
        return list(self.data.get(list_name.lower(), []))

    def add_item(self, item: str, list_name: str = "default") -> list[str]:
        self.calls.append(("add_item", item, list_name))
        key = list_name.lower()
        self.data.setdefault(key, [])
        clean = item.strip()
        if clean and clean.lower() not in [existing.lower() for existing in self.data[key]]:
            self.data[key].append(clean)
        return list(self.data[key])

    def remove_item(
        self, item: str, list_name: str = "default", *, confidence: float
    ) -> list[str]:
        self.calls.append(("remove_item", item, list_name, confidence))
        key = list_name.lower()
        self.data[key] = [
            existing
            for existing in self.data.get(key, [])
            if existing.lower() != item.strip().lower()
        ]
        return list(self.data.get(key, []))

    def clear_list(self, list_name: str = "default", *, confidence: float) -> None:
        self.calls.append(("clear_list", list_name, confidence))
        self.data[list_name.lower()] = []


@pytest.fixture
def module_source() -> str:
    return MODULE_PATH.read_text()


@pytest.fixture
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


@pytest.fixture
def install_store(monkeypatch: pytest.MonkeyPatch) -> Callable[..., FakeShoppingStore]:
    def _install(initial: list[str] | None = None) -> FakeShoppingStore:
        store = FakeShoppingStore(initial)
        fake_module = store.module()
        import agent_skills

        monkeypatch.setitem(sys.modules, "agent_skills.shopping_list", fake_module)
        monkeypatch.setattr(agent_skills, "shopping_list", fake_module, raising=False)
        return store

    return _install


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                roots.add(parts[0])
                if len(parts) >= 2:
                    roots.add(".".join(parts[:2]))
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            roots.add(parts[0])
            if len(parts) >= 2:
                roots.add(".".join(parts[:2]))
    return roots


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def _schema_actions() -> set[str]:
    schema = shopping_metadata.PARAMS_SCHEMA["action"]
    match = re.search(r"one of:\s*([^.]*)\.", schema)
    assert match, "PARAMS_SCHEMA action enum must be parseable"
    return {part.strip() for part in match.group(1).split("|")}


def _action_branch_literals(tree: ast.AST) -> set[str]:
    actions: set[str] = set()
    for node in ast.walk(tree):
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


def _guard_external_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        parts = name.split(".")
        roots = {parts[0], ".".join(parts[:2]) if len(parts) >= 2 else parts[0], name}
        blocked = roots & DB_AND_LLM_IMPORT_ROOTS
        if blocked:
            raise AssertionError(f"unexpected DB/LLM import: {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


class TestDocumentedBehavior:
    def test_docstring_declares_params_driven_stage2_contract(
        self, module_source: str
    ) -> None:
        doc = ast.get_docstring(ast.parse(module_source))
        normalized_doc = " ".join((doc or "").split())

        assert doc is not None
        assert "params-driven" in normalized_doc
        assert "supplies `action` and `items`" in normalized_doc
        assert "dispatches directly on" in normalized_doc
        assert "no local LLM intent parse needed" in normalized_doc
        assert "Escalates to Stage 3" in normalized_doc

    @pytest.mark.asyncio
    async def test_view_empty_list_returns_text_dict(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        install_store([])

        result = await shopping_handler.handle(
            "what is on my shopping list", {"action": "view", "items": None}
        )

        assert result == {"text": "Your shopping list is empty."}

    @pytest.mark.asyncio
    async def test_view_existing_list_returns_joined_items(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        install_store(["milk", "eggs"])

        result = await shopping_handler.handle(
            "show my shopping list", {"action": "view", "items": None}
        )

        assert result == {"text": "Your shopping list has: milk, eggs."}

    @pytest.mark.asyncio
    async def test_add_splits_comma_separated_items_and_updates_store(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        store = install_store(["bread"])

        result = await shopping_handler.handle(
            "add milk and eggs",
            {"action": "add", "items": " milk, eggs ,, bread "},
        )

        assert result == {
            "text": "Added milk, eggs, bread. Your shopping list now has 3 items."
        }
        assert store.data["default"] == ["bread", "milk", "eggs"]
        assert ("add_item", "milk", "default") in store.calls
        assert ("add_item", "eggs", "default") in store.calls
        assert ("add_item", "bread", "default") in store.calls

    @pytest.mark.asyncio
    async def test_remove_uses_items_and_confidence_against_json_store(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        store = install_store(["milk", "eggs", "bread"])

        result = await shopping_handler.handle(
            "remove eggs",
            {"action": "remove", "items": "eggs", "confidence": 0.91},
        )

        assert result == {"text": "Removed eggs from your shopping list."}
        assert store.data["default"] == ["milk", "bread"]
        assert ("remove_item", "eggs", "default", 0.91) in store.calls

    @pytest.mark.asyncio
    async def test_clear_uses_confidence_and_clears_default_list(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        store = install_store(["milk", "eggs"])

        result = await shopping_handler.handle(
            "clear my shopping list",
            {"action": "clear", "items": None, "confidence": 0.99},
        )

        assert result == {"text": "Your shopping list has been cleared."}
        assert store.data["default"] == []
        assert ("clear_list", "default", 0.99) in store.calls

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("items", "expected_prefix", "expected_terms"),
        [
            ("milk", "Yes", ["milk"]),
            ("flour", "No", ["flour"]),
            ("MILK, flour", "Mixed:", ["MILK", "flour"]),
        ],
    )
    async def test_check_reports_present_missing_and_mixed_items(
        self,
        install_store: Callable[..., FakeShoppingStore],
        items: str,
        expected_prefix: str,
        expected_terms: list[str],
    ) -> None:
        install_store(["Milk", "eggs"])

        result = await shopping_handler.handle(
            "do I need this", {"action": "check", "items": items}
        )

        assert isinstance(result, dict)
        assert result["text"].startswith(expected_prefix)
        for term in expected_terms:
            assert term in result["text"]

    @pytest.mark.asyncio
    async def test_action_is_case_and_whitespace_normalized(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        store = install_store([])

        result = await shopping_handler.handle(
            "add apples", {"action": "  ADD  ", "items": "apples"}
        )

        assert isinstance(result, dict)
        assert result["text"].startswith("Added apples.")
        assert store.data["default"] == ["apples"]


class TestEdgeCases:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt", [None, "", "   ", "\n\t"])
    async def test_missing_params_escalates_before_store_import(
        self, monkeypatch: pytest.MonkeyPatch, prompt: str | None
    ) -> None:
        _guard_external_imports(monkeypatch)

        result = await shopping_handler.handle(prompt, None)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"action": None},
            {"action": 12},
            {"action": ["add"]},
            {"action": "archive", "items": "milk"},
            {"action": "others", "items": "milk"},
            {"action": "delegate opus", "items": "milk"},
        ],
    )
    async def test_empty_malformed_and_unknown_actions_escalate_without_store_import(
        self, monkeypatch: pytest.MonkeyPatch, params: dict[str, Any]
    ) -> None:
        _guard_external_imports(monkeypatch)

        result = await shopping_handler.handle("shopping list request", params)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw_items", [None, "", "   ", [], {}, 42, False])
    @pytest.mark.parametrize("action", ["add", "check"])
    async def test_item_actions_decline_empty_or_malformed_items(
        self,
        install_store: Callable[..., FakeShoppingStore],
        raw_items: Any,
        action: str,
    ) -> None:
        store = install_store(["milk"])

        result = await shopping_handler.handle(
            "shopping list request", {"action": action, "items": raw_items}
        )

        assert result is None
        assert not any(call[0] in {"add_item", "remove_item"} for call in store.calls)

    @pytest.mark.asyncio
    async def test_remove_declines_missing_items_even_with_high_confidence(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        store = install_store(["milk"])

        result = await shopping_handler.handle(
            "remove something", {"action": "remove", "items": None, "confidence": 0.99}
        )

        assert result is None
        assert not any(call[0] == "remove_item" for call in store.calls)

    @pytest.mark.asyncio
    async def test_empty_prompt_still_dispatches_when_params_are_complete(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        install_store(["rice"])

        result = await shopping_handler.handle("", {"action": "view", "items": None})

        assert result == {"text": "Your shopping list has: rice."}

    @pytest.mark.asyncio
    async def test_very_long_prompt_does_not_change_params_driven_dispatch(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        install_store(["rice"])
        prompt = "show my shopping list " + ("x " * 10000)

        result = await shopping_handler.handle(prompt, {"action": "view", "items": None})

        assert result == {"text": "Your shopping list has: rice."}

    @pytest.mark.asyncio
    async def test_very_long_item_is_passed_to_store_without_truncation(
        self, install_store: Callable[..., FakeShoppingStore]
    ) -> None:
        store = install_store([])
        item = "x" * 10000

        result = await shopping_handler.handle(
            "add a long item", {"action": "add", "items": item}
        )

        assert isinstance(result, dict)
        assert result["text"].endswith("now has 1 items.")
        assert store.data["default"] == [item]

    def test_split_items_handles_none_non_string_and_extra_commas(self) -> None:
        assert shopping_handler._split_items(None) == []
        assert shopping_handler._split_items(123) == []
        assert shopping_handler._split_items(" milk, eggs ,, bread ") == [
            "milk",
            "eggs",
            "bread",
        ]


class TestIntegrationPoints:
    @pytest.mark.asyncio
    async def test_json_store_skill_is_the_only_runtime_dependency_for_add(
        self,
        install_store: Callable[..., FakeShoppingStore],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _guard_external_imports(monkeypatch)
        store = install_store([])

        result = await shopping_handler.handle(
            "add milk", {"action": "add", "items": "milk"}
        )

        assert isinstance(result, dict)
        assert result["text"] == "Added milk. Your shopping list now has 1 items."
        assert store.calls == [
            ("add_item", "milk", "default"),
            ("get_list", "default"),
        ]

    @pytest.mark.asyncio
    async def test_store_import_failure_escalates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original_import = builtins.__import__

        def failing_import(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> Any:
            if name == "agent_skills.shopping_list":
                raise ImportError("store unavailable")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", failing_import)

        result = await shopping_handler.handle(
            "show my shopping list", {"action": "view", "items": None}
        )

        assert result is None

    def test_handler_has_no_direct_db_or_llm_imports(self, module_ast: ast.Module) -> None:
        assert _import_roots(module_ast).isdisjoint(DB_AND_LLM_IMPORT_ROOTS)

    def test_handler_does_not_call_db_or_llm_client_methods(
        self, module_ast: ast.Module
    ) -> None:
        db_llm_call_names = {
            "AsyncClient",
            "Client",
            "chat",
            "connect",
            "create",
            "execute",
            "generate",
            "post",
            "query",
            "request",
        }

        assert _called_names(module_ast).isdisjoint(db_llm_call_names)

    @pytest.mark.asyncio
    async def test_stage2_dispatcher_passes_params_to_registered_handler(
        self,
        install_store: Callable[..., FakeShoppingStore],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        install_store(["milk"])
        gate = AsyncMock(return_value=True)
        monkeypatch.setattr(stage2_dispatcher, "_gate_check", gate)
        monkeypatch.setattr(
            class_registry,
            "get_registry",
            lambda refresh=False: {
                "shopping list": {"handler": shopping_handler.handle}
            },
        )

        result = await stage2_dispatcher.dispatch(
            "shopping list",
            "show my shopping list",
            params={"action": "view", "items": None},
        )

        assert result == {"text": "Your shopping list has: milk."}
        gate.assert_awaited_once()


class TestStructuralInvariants:
    def test_metadata_schema_actions_match_handler_registry_and_branches(
        self, module_ast: ast.Module
    ) -> None:
        schema_actions = _schema_actions()
        valid_actions = set(shopping_handler._VALID_ACTIONS)
        branch_actions = _action_branch_literals(module_ast)

        assert valid_actions == {"view", "add", "remove", "clear", "check"}
        assert schema_actions == valid_actions
        assert branch_actions == valid_actions

    def test_valid_actions_do_not_contain_fallback_or_escalation_classes(self) -> None:
        assert set(shopping_handler._VALID_ACTIONS).isdisjoint(FALLBACK_CLASSES)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("params", "initial"),
        [
            ({"action": "view", "items": None}, ["milk"]),
            ({"action": "add", "items": "eggs"}, ["milk"]),
            ({"action": "remove", "items": "milk", "confidence": 0.80}, ["milk"]),
            ({"action": "clear", "items": None, "confidence": 0.80}, ["milk"]),
            ({"action": "check", "items": "milk"}, ["milk"]),
        ],
    )
    async def test_every_valid_action_is_reachable_and_returns_text_shape(
        self,
        install_store: Callable[..., FakeShoppingStore],
        params: dict[str, Any],
        initial: list[str],
    ) -> None:
        install_store(initial)

        result = await shopping_handler.handle("shopping list request", params)

        assert isinstance(result, dict)
        assert set(result) == {"text"}
        assert isinstance(result["text"], str)
        assert result["text"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", sorted(DESTRUCTIVE_ACTIONS))
    @pytest.mark.parametrize(
        "confidence",
        [None, True, False, "High", "0.99", -1, 0, 0.79, 0.799999],
    )
    async def test_destructive_actions_require_numeric_confidence_at_least_080(
        self,
        install_store: Callable[..., FakeShoppingStore],
        action: str,
        confidence: Any,
    ) -> None:
        store = install_store(["milk"])
        params: dict[str, Any] = {"action": action, "items": "milk", "confidence": confidence}

        result = await shopping_handler.handle("destructive request", params)

        assert result is None
        destructive_calls = {"remove_item", "clear_list"}
        assert not any(call[0] in destructive_calls for call in store.calls)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", sorted(DESTRUCTIVE_ACTIONS))
    async def test_destructive_actions_allow_exact_threshold_080(
        self, install_store: Callable[..., FakeShoppingStore], action: str
    ) -> None:
        store = install_store(["milk"])
        params: dict[str, Any] = {"action": action, "items": "milk", "confidence": 0.80}

        result = await shopping_handler.handle("destructive request", params)

        assert isinstance(result, dict)
        if action == "remove":
            assert ("remove_item", "milk", "default", 0.80) in store.calls
        else:
            assert ("clear_list", "default", 0.80) in store.calls

    def test_destructive_store_calls_pass_confidence_keyword(
        self, module_ast: ast.Module
    ) -> None:
        destructive_calls: list[ast.Call] = []
        for node in ast.walk(module_ast):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in {
                "remove_item",
                "clear_list",
            }:
                destructive_calls.append(node)

        assert len(destructive_calls) == 2
        for call in destructive_calls:
            assert any(keyword.arg == "confidence" for keyword in call.keywords)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "params",
        [
            {"action": "remove", "items": "", "confidence": 0.99},
            {"action": "remove", "items": "   ", "confidence": 0.99},
            {"action": "remove", "items": [], "confidence": 0.99},
            {"action": "remove", "items": "milk", "confidence": 0.799999},
            {"action": "clear", "items": None, "confidence": 0.799999},
        ],
    )
    async def test_destructive_actions_cannot_fire_on_ambiguous_or_borderline_input(
        self,
        install_store: Callable[..., FakeShoppingStore],
        params: dict[str, Any],
    ) -> None:
        store = install_store(["milk"])

        result = await shopping_handler.handle("ambiguous destructive request", params)

        assert result is None
        assert not any(call[0] in {"remove_item", "clear_list"} for call in store.calls)

    def test_shopping_list_class_is_registered_with_handler(self) -> None:
        registry = class_registry.get_registry(refresh=True)
        meta = registry["shopping list"]

        assert meta["name"] == "shopping list"
        assert meta["handler"] is not None
        assert meta["handler"].__module__ == shopping_handler.handle.__module__
        assert meta["handler"].__name__ == "handle"

    def test_shopping_list_metadata_documents_params_and_no_handler_gap(self) -> None:
        assert shopping_metadata.METADATA["name"] == "shopping list"
        assert shopping_metadata.METADATA["params_schema"] is shopping_metadata.PARAMS_SCHEMA
        assert set(shopping_metadata.PARAMS_SCHEMA) == {"action", "items"}
        assert "no handler" not in shopping_metadata.METADATA["description"].lower()
