from __future__ import annotations

import ast
import importlib
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = (
    REPO_ROOT / "jane_web" / "jane_v2" / "classes" / "shopping_list" / "handler.py"
)
METADATA_PATH = (
    REPO_ROOT / "jane_web" / "jane_v2" / "classes" / "shopping_list" / "metadata.py"
)

from jane_web.jane_v2.classes.shopping_list import handler as shopping_handler
from jane_web.jane_v2.classes.shopping_list import metadata as shopping_metadata


EXPECTED_ACTIONS = {"view", "add", "remove", "clear", "check"}
DESTRUCTIVE_ACTIONS = {"remove", "clear"}


@pytest.fixture
def module_source() -> str:
    return MODULE_PATH.read_text()


@pytest.fixture
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


@pytest.fixture
def fake_shopping_skill(monkeypatch):
    state = {"default": []}
    fake_module = types.ModuleType("agent_skills.shopping_list")

    def normalize(name: str = "default") -> str:
        return (name or "default").lower()

    def get_list_impl(list_name: str = "default") -> list[str]:
        return list(state.get(normalize(list_name), []))

    def add_item_impl(item: str, list_name: str = "default") -> list[str]:
        key = normalize(list_name)
        state.setdefault(key, [])
        item = item.strip()
        if item and item.lower() not in [i.lower() for i in state[key]]:
            state[key].append(item)
        return list(state[key])

    def remove_item_impl(
        item: str,
        list_name: str = "default",
        *,
        confidence: float | None = None,
    ) -> list[str]:
        key = normalize(list_name)
        item = item.strip()
        if key in state:
            state[key] = [i for i in state[key] if i.lower() != item.lower()]
        return list(state.get(key, []))

    def clear_list_impl(
        list_name: str = "default",
        *,
        confidence: float | None = None,
    ) -> None:
        state[normalize(list_name)] = []

    fake_module.get_list = Mock(side_effect=get_list_impl)
    fake_module.add_item = Mock(side_effect=add_item_impl)
    fake_module.remove_item = Mock(side_effect=remove_item_impl)
    fake_module.clear_list = Mock(side_effect=clear_list_impl)

    monkeypatch.setitem(sys.modules, "agent_skills.shopping_list", fake_module)

    return SimpleNamespace(
        state=state,
        module=fake_module,
        get_list=fake_module.get_list,
        add_item=fake_module.add_item,
        remove_item=fake_module.remove_item,
        clear_list=fake_module.clear_list,
    )


def _all_store_mocks(fake_shopping_skill) -> tuple[Mock, Mock, Mock, Mock]:
    return (
        fake_shopping_skill.get_list,
        fake_shopping_skill.add_item,
        fake_shopping_skill.remove_item,
        fake_shopping_skill.clear_list,
    )


def _assert_text_result(result: dict | None) -> None:
    assert isinstance(result, dict)
    assert isinstance(result.get("text"), str)
    assert result["text"]


def _handle_function(tree: ast.Module) -> ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle":
            return node
    raise AssertionError("handle() function was not found")


def _action_branch_literals(tree: ast.Module) -> set[str]:
    actions = set()
    for node in ast.walk(_handle_function(tree)):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "action":
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
            actions.add(comparator.value)
    return actions


def _calls_to(tree: ast.Module, function_name: str) -> list[ast.Call]:
    calls = []
    for node in ast.walk(_handle_function(tree)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == function_name:
            calls.append(node)
        elif isinstance(func, ast.Attribute) and func.attr == function_name:
            calls.append(node)
    return calls


def _imported_or_called_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0].lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            names.update(part.lower() for part in parts)
            names.update(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id.lower())
            elif isinstance(func, ast.Attribute):
                names.add(func.attr.lower())
    return names


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, []),
        ("", []),
        ("   ", []),
        ("milk", ["milk"]),
        (" milk, eggs ,, bread ", ["milk", "eggs", "bread"]),
    ],
)
def test_split_items_trims_comma_separated_schema_values(raw, expected):
    assert shopping_handler._split_items(raw) == expected


@pytest.mark.asyncio
async def test_missing_params_escalates_without_touching_store(fake_shopping_skill):
    result = await shopping_handler.handle("what is on my shopping list", None)

    assert result is None
    assert not any(mock.called for mock in _all_store_mocks(fake_shopping_skill))


@pytest.mark.asyncio
async def test_empty_params_escalates_without_touching_store(fake_shopping_skill):
    result = await shopping_handler.handle("what is on my shopping list", {})

    assert result is None
    assert not any(mock.called for mock in _all_store_mocks(fake_shopping_skill))


@pytest.mark.asyncio
async def test_unknown_action_escalates_without_touching_store(fake_shopping_skill):
    result = await shopping_handler.handle(
        "buy milk",
        {"action": "buy", "items": "milk"},
    )

    assert result is None
    assert not any(mock.called for mock in _all_store_mocks(fake_shopping_skill))


@pytest.mark.asyncio
async def test_view_empty_list_returns_documented_text(fake_shopping_skill):
    result = await shopping_handler.handle(
        "what is on my shopping list",
        {"action": "view", "items": None},
    )

    assert result == {"text": "Your shopping list is empty."}
    fake_shopping_skill.get_list.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_view_populated_list_returns_items(fake_shopping_skill):
    fake_shopping_skill.state["default"] = ["milk", "eggs"]

    result = await shopping_handler.handle(
        "what is on my shopping list",
        {"action": "view", "items": None},
    )

    assert result == {"text": "Your shopping list has: milk, eggs."}
    fake_shopping_skill.get_list.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_add_dispatches_each_trimmed_item_and_reports_new_count(fake_shopping_skill):
    result = await shopping_handler.handle(
        "add milk eggs and bread",
        {"action": "add", "items": " milk, eggs ,, bread "},
    )

    assert result == {
        "text": "Added milk, eggs, bread. Your shopping list now has 3 items."
    }
    assert fake_shopping_skill.add_item.call_args_list == [
        call("milk", "default"),
        call("eggs", "default"),
        call("bread", "default"),
    ]
    fake_shopping_skill.get_list.assert_called_once_with("default")
    assert fake_shopping_skill.state["default"] == ["milk", "eggs", "bread"]


@pytest.mark.asyncio
async def test_action_is_case_and_whitespace_normalized(fake_shopping_skill):
    result = await shopping_handler.handle(
        "add milk",
        {"action": "  ADD  ", "items": "milk"},
    )

    assert result == {
        "text": "Added milk. Your shopping list now has 1 items."
    }
    fake_shopping_skill.add_item.assert_called_once_with("milk", "default")


@pytest.mark.asyncio
async def test_add_without_items_escalates_without_mutating(fake_shopping_skill):
    result = await shopping_handler.handle(
        "add something to my shopping list",
        {"action": "add", "items": " , , "},
    )

    assert result is None
    fake_shopping_skill.add_item.assert_not_called()
    assert fake_shopping_skill.state["default"] == []


@pytest.mark.asyncio
async def test_remove_dispatches_each_item_and_reports_completion(fake_shopping_skill):
    fake_shopping_skill.state["default"] = ["milk", "eggs", "bread"]

    result = await shopping_handler.handle(
        "remove milk and bread",
        {"action": "remove", "items": "milk, bread", "confidence": 0.95},
    )

    assert result == {"text": "Removed milk, bread from your shopping list."}
    assert fake_shopping_skill.remove_item.call_args_list == [
        call("milk", "default", confidence=0.95),
        call("bread", "default", confidence=0.95),
    ]
    assert fake_shopping_skill.state["default"] == ["eggs"]


@pytest.mark.asyncio
async def test_remove_without_items_escalates_without_mutating(fake_shopping_skill):
    fake_shopping_skill.state["default"] = ["milk"]

    result = await shopping_handler.handle(
        "remove from my shopping list",
        {"action": "remove", "items": None, "confidence": 1.0},
    )

    assert result is None
    fake_shopping_skill.remove_item.assert_not_called()
    assert fake_shopping_skill.state["default"] == ["milk"]


@pytest.mark.asyncio
async def test_clear_dispatches_to_store_and_reports_completion(fake_shopping_skill):
    fake_shopping_skill.state["default"] = ["milk", "eggs"]

    result = await shopping_handler.handle(
        "clear my shopping list",
        {"action": "clear", "items": None, "confidence": 0.95},
    )

    assert result == {"text": "Your shopping list has been cleared."}
    fake_shopping_skill.clear_list.assert_called_once_with("default", confidence=0.95)
    assert fake_shopping_skill.state["default"] == []


@pytest.mark.asyncio
async def test_check_present_items_is_case_insensitive(fake_shopping_skill):
    fake_shopping_skill.state["default"] = ["Milk", "eggs"]

    result = await shopping_handler.handle(
        "do I need milk and eggs",
        {"action": "check", "items": "milk, EGGS"},
    )

    assert result == {
        "text": "Yes \u2014 milk, EGGS is on your shopping list."
    }
    fake_shopping_skill.get_list.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_check_missing_items_reports_no(fake_shopping_skill):
    fake_shopping_skill.state["default"] = ["milk"]

    result = await shopping_handler.handle(
        "do I need bread",
        {"action": "check", "items": "bread"},
    )

    assert result == {
        "text": "No \u2014 bread is not on your shopping list."
    }


@pytest.mark.asyncio
async def test_check_mixed_items_reports_present_and_missing(fake_shopping_skill):
    fake_shopping_skill.state["default"] = ["milk", "eggs"]

    result = await shopping_handler.handle(
        "do I need milk and bread",
        {"action": "check", "items": "milk, bread"},
    )

    assert result == {
        "text": "Mixed: milk is on the list; bread is not."
    }


@pytest.mark.asyncio
async def test_check_without_items_escalates_without_querying_store(fake_shopping_skill):
    result = await shopping_handler.handle(
        "do I need anything",
        {"action": "check", "items": ""},
    )

    assert result is None
    fake_shopping_skill.get_list.assert_not_called()


@pytest.mark.asyncio
async def test_prompt_none_is_accepted_when_params_are_valid(fake_shopping_skill):
    fake_shopping_skill.state["default"] = ["milk"]

    result = await shopping_handler.handle(
        None,  # type: ignore[arg-type]
        {"action": "view", "items": None},
    )

    assert result == {"text": "Your shopping list has: milk."}


@pytest.mark.asyncio
async def test_empty_prompt_with_missing_params_escalates(fake_shopping_skill):
    result = await shopping_handler.handle("", None)

    assert result is None
    assert not any(mock.called for mock in _all_store_mocks(fake_shopping_skill))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"items": "milk"},
        {"action": None, "items": "milk"},
        {"action": 123, "items": "milk"},
        {"action": ["add"], "items": "milk"},
    ],
)
async def test_malformed_action_params_escalate_without_store_calls(
    fake_shopping_skill,
    params,
):
    result = await shopping_handler.handle("malformed request", params)

    assert result is None
    assert not any(mock.called for mock in _all_store_mocks(fake_shopping_skill))


@pytest.mark.asyncio
async def test_malformed_items_type_escalates_without_adding(fake_shopping_skill):
    result = await shopping_handler.handle(
        "add milk and eggs",
        {"action": "add", "items": ["milk", "eggs"]},
    )

    assert result is None
    fake_shopping_skill.add_item.assert_not_called()
    assert fake_shopping_skill.state["default"] == []


@pytest.mark.asyncio
async def test_very_long_item_round_trips_through_store_call(fake_shopping_skill):
    long_item = "x" * 10000

    result = await shopping_handler.handle(
        "add a very long item",
        {"action": "add", "items": long_item},
    )

    assert result == {
        "text": "Added " + long_item + ". Your shopping list now has 1 items."
    }
    fake_shopping_skill.add_item.assert_called_once_with(long_item, "default")
    assert fake_shopping_skill.state["default"] == [long_item]


@pytest.mark.asyncio
async def test_skill_import_failure_escalates(monkeypatch):
    monkeypatch.setitem(sys.modules, "agent_skills.shopping_list", None)

    result = await shopping_handler.handle(
        "what is on my shopping list",
        {"action": "view", "items": None},
    )

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "expected_calls"),
    [
        (
            {"action": "view", "items": None},
            {"get_list": [call("default")]},
        ),
        (
            {"action": "add", "items": "milk"},
            {"add_item": [call("milk", "default")], "get_list": [call("default")]},
        ),
        (
            {"action": "remove", "items": "milk", "confidence": 1.0},
            {"remove_item": [call("milk", "default", confidence=1.0)]},
        ),
        (
            {"action": "clear", "items": None, "confidence": 1.0},
            {"clear_list": [call("default", confidence=1.0)]},
        ),
        (
            {"action": "check", "items": "milk"},
            {"get_list": [call("default")]},
        ),
    ],
)
async def test_store_integration_uses_default_list_for_all_actions(
    fake_shopping_skill,
    params,
    expected_calls,
):
    fake_shopping_skill.state["default"] = ["milk"]

    await shopping_handler.handle("shopping request", params)

    for name, expected in expected_calls.items():
        assert getattr(fake_shopping_skill, name).call_args_list == expected


def test_executable_code_has_no_llm_or_stage3_calls(module_ast):
    forbidden = {
        "anthropic",
        "ask_opus",
        "classify",
        "generate",
        "llm",
        "local_llm",
        "ollama",
        "openai",
        "qwen",
        "stage1",
        "stage1_classify",
        "stage3",
    }
    seen = _imported_or_called_names(module_ast)

    assert not (seen & forbidden)


def test_executable_code_has_no_direct_db_or_network_dependencies(module_ast):
    forbidden = {
        "httpx",
        "mysql",
        "pymysql",
        "requests",
        "sqlalchemy",
        "sqlite3",
    }
    seen = _imported_or_called_names(module_ast)

    assert not (seen & forbidden)


def test_valid_actions_match_docstring_and_metadata_schema():
    schema_text = shopping_metadata.PARAMS_SCHEMA["action"]
    schema_actions = set(
        re.findall(r"\b(view|add|remove|clear|check)\b", schema_text)
    )

    assert shopping_handler._VALID_ACTIONS == EXPECTED_ACTIONS
    assert schema_actions == EXPECTED_ACTIONS
    assert "params-driven" in (shopping_handler.__doc__ or "")
    assert "Stage 3" in (shopping_handler.__doc__ or "")


def test_no_valid_action_is_a_fallback_or_meta_class():
    forbidden = {
        "delegate_opus",
        "fallback",
        "force_stage3",
        "others",
        "unclear",
        "unknown",
        "wrong_class",
    }

    assert not (shopping_handler._VALID_ACTIONS & forbidden)


def test_action_branch_literals_match_valid_action_set(module_ast):
    assert _action_branch_literals(module_ast) == EXPECTED_ACTIONS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "params"),
    [
        ("view", {"action": "view", "items": None}),
        ("add", {"action": "add", "items": "bread"}),
        ("remove", {"action": "remove", "items": "milk", "confidence": 1.0}),
        ("clear", {"action": "clear", "items": None, "confidence": 1.0}),
        ("check", {"action": "check", "items": "milk"}),
    ],
)
async def test_each_valid_action_is_reachable_from_params(
    fake_shopping_skill,
    action,
    params,
):
    fake_shopping_skill.state["default"] = ["milk"]

    result = await shopping_handler.handle("shopping request", params)

    _assert_text_result(result), action


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        None,
        {},
        {"action": "unknown", "items": "milk"},
        {"action": "add", "items": ""},
        {"action": "remove", "items": "", "confidence": 1.0},
        {"action": "check", "items": ""},
    ],
)
async def test_documented_escalation_paths_return_none(fake_shopping_skill, params):
    result = await shopping_handler.handle("shopping request", params)

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "params", "destructive_mock_name"),
    [
        ("remove", {"action": "remove", "items": "milk"}, "remove_item"),
        ("clear", {"action": "clear", "items": None}, "clear_list"),
        (
            "remove",
            {"action": "remove", "items": "milk", "confidence": "High"},
            "remove_item",
        ),
        (
            "clear",
            {"action": "clear", "items": None, "confidence": "High"},
            "clear_list",
        ),
    ],
)
async def test_destructive_actions_require_numeric_confidence_not_high_label(
    fake_shopping_skill,
    action,
    params,
    destructive_mock_name,
):
    fake_shopping_skill.state["default"] = ["milk"]

    result = await shopping_handler.handle(f"maybe {action} my list", params)

    assert result is None
    getattr(fake_shopping_skill, destructive_mock_name).assert_not_called()
    assert fake_shopping_skill.state["default"] == ["milk"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "destructive_mock_name"),
    [
        (
            {"action": "remove", "items": "milk", "confidence": 0.79},
            "remove_item",
        ),
        (
            {"action": "clear", "items": None, "confidence": 0.79},
            "clear_list",
        ),
    ],
)
async def test_destructive_actions_cannot_fire_on_borderline_confidence(
    fake_shopping_skill,
    params,
    destructive_mock_name,
):
    fake_shopping_skill.state["default"] = ["milk"]

    result = await shopping_handler.handle("maybe change my shopping list", params)

    assert result is None
    getattr(fake_shopping_skill, destructive_mock_name).assert_not_called()
    assert fake_shopping_skill.state["default"] == ["milk"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "destructive_mock_name"),
    [
        (
            {"action": "remove", "items": "milk", "confidence": 0.80},
            "remove_item",
        ),
        (
            {"action": "clear", "items": None, "confidence": 0.80},
            "clear_list",
        ),
    ],
)
async def test_destructive_actions_pass_threshold_confidence_to_store(
    fake_shopping_skill,
    params,
    destructive_mock_name,
):
    fake_shopping_skill.state["default"] = ["milk"]

    result = await shopping_handler.handle("change my shopping list", params)

    _assert_text_result(result)
    destructive_mock = getattr(fake_shopping_skill, destructive_mock_name)
    destructive_mock.assert_called_once()
    assert destructive_mock.call_args.kwargs.get("confidence") == 0.80


def test_destructive_store_calls_include_confidence_keyword_in_source(module_ast):
    for function_name in ("remove_item", "clear_list"):
        calls = _calls_to(module_ast, function_name)
        assert calls, f"{function_name} should be called for destructive dispatch"
        for call_node in calls:
            keyword_names = {kw.arg for kw in call_node.keywords}
            assert "confidence" in keyword_names, (
                f"{function_name} must receive an explicit numeric confidence "
                "keyword so destructive actions cannot run on weak Stage 1 output"
            )


def test_destructive_actions_are_audited_against_valid_actions():
    assert DESTRUCTIVE_ACTIONS <= shopping_handler._VALID_ACTIONS


def test_handler_signature_is_stage2_params_driven():
    import inspect

    signature = inspect.signature(shopping_handler.handle)

    assert list(signature.parameters) == ["prompt", "params"]
    assert signature.parameters["params"].default is None


def test_shopping_list_class_registry_has_handler():
    from jane_web.jane_v2 import classes as class_registry

    registry = class_registry.get_registry(refresh=True)
    metadata = registry.get("shopping list")

    assert metadata is not None
    assert metadata["handler"] is not None
    assert metadata["handler"].__module__ == shopping_handler.handle.__module__


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"action": "view", "items": None},
        {"action": "add", "items": "milk"},
        {"action": "remove", "items": "milk", "confidence": 1.0},
        {"action": "clear", "items": None, "confidence": 1.0},
        {"action": "check", "items": "milk"},
    ],
)
async def test_every_handled_action_returns_documented_dict_text_shape(
    fake_shopping_skill,
    params,
):
    fake_shopping_skill.state["default"] = ["milk"]

    result = await shopping_handler.handle("shopping request", params)

    _assert_text_result(result)


def test_metadata_file_and_handler_file_are_the_audited_targets():
    assert MODULE_PATH.exists()
    assert METADATA_PATH.exists()
    assert importlib.import_module(shopping_handler.__name__) is shopping_handler
