import ast
import importlib.util
import inspect
import json
from pathlib import Path
from unittest.mock import Mock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "agent_skills" / "shopping_list.py"

PUBLIC_API = {
    "get_all_lists",
    "get_list",
    "add_item",
    "remove_item",
    "clear_list",
    "format_for_context",
}

DESTRUCTIVE_FUNCTIONS = {
    "remove_item": {
        "args": ("milk", "default"),
        "seed": {"default": ["milk"], "costco": ["eggs"]},
        "mutated": {"default": [], "costco": ["eggs"]},
    },
    "clear_list": {
        "args": ("default",),
        "seed": {"default": ["milk"], "costco": ["eggs"]},
        "mutated": {"default": [], "costco": ["eggs"]},
    },
}


def _load_fresh_module(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path))
    module_name = f"_audit_shopping_list_{id(tmp_path)}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def shopping_list(tmp_path, monkeypatch):
    return _load_fresh_module(tmp_path, monkeypatch)


@pytest.fixture
def module_source():
    return MODULE_PATH.read_text()


@pytest.fixture
def module_ast(module_source):
    return ast.parse(module_source)


def _write_store(module, data):
    module.LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    module.LISTS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def _read_store(module):
    return json.loads(module.LISTS_FILE.read_text())


def _call_allowing_refusal(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except (PermissionError, RuntimeError, ValueError):
        return None


def _module_level_dict_assignments(tree):
    mappings = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    mappings[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if isinstance(node.value, ast.Dict):
                mappings[node.target.id] = node.value
    return mappings


def test_lists_file_resolves_under_vessence_data_home(shopping_list, tmp_path):
    assert shopping_list.VESSENCE_DATA_HOME == str(tmp_path)
    assert shopping_list.LISTS_FILE == tmp_path / "shopping_lists.json"


def test_missing_file_reads_as_empty_store(shopping_list):
    assert not shopping_list.LISTS_FILE.exists()
    assert shopping_list.get_all_lists() == {}
    assert shopping_list.get_list() == []
    assert shopping_list.get_list("costco") == []
    assert (
        shopping_list.format_for_context()
        == "No shopping lists exist yet. The user can ask you to create one."
    )


def test_get_all_lists_and_get_list_read_documented_json_mapping(shopping_list):
    data = {
        "default": ["milk", "eggs", "bread"],
        "costco": ["paper towels", "chicken"],
    }
    _write_store(shopping_list, data)

    assert shopping_list.get_all_lists() == data
    assert shopping_list.get_list("default") == ["milk", "eggs", "bread"]
    assert shopping_list.get_list("Costco") == ["paper towels", "chicken"]
    assert shopping_list.get_list("missing") == []


def test_add_item_creates_default_list_and_persists_json(shopping_list):
    result = shopping_list.add_item("milk")

    assert result == ["milk"]
    assert _read_store(shopping_list) == {"default": ["milk"]}
    text = shopping_list.LISTS_FILE.read_text()
    assert text.endswith("\n")
    assert '{\n  "default": [' in text


def test_add_item_trims_items_lowercases_list_names_and_deduplicates_case_insensitively(
    shopping_list,
):
    assert shopping_list.add_item("  Milk  ") == ["Milk"]
    assert shopping_list.add_item("milk") == ["Milk"]
    assert shopping_list.add_item("EGGS", "Costco") == ["EGGS"]
    assert shopping_list.add_item("eggs", "COSTCO") == ["EGGS"]

    assert _read_store(shopping_list) == {
        "default": ["Milk"],
        "costco": ["EGGS"],
    }


def test_remove_item_is_case_insensitive_and_scoped_to_named_list(shopping_list):
    _write_store(
        shopping_list,
        {
            "default": ["Milk", "eggs", "bread"],
            "costco": ["milk", "paper towels"],
        },
    )

    result = shopping_list.remove_item(" milk ", "DEFAULT")

    assert result == ["eggs", "bread"]
    assert _read_store(shopping_list) == {
        "default": ["eggs", "bread"],
        "costco": ["milk", "paper towels"],
    }


def test_remove_item_from_missing_list_returns_empty_without_creating_file(shopping_list):
    assert shopping_list.remove_item("milk", "missing") == []
    assert not shopping_list.LISTS_FILE.exists()


def test_clear_list_empties_named_list_and_persists_other_lists(shopping_list):
    _write_store(
        shopping_list,
        {
            "default": ["milk"],
            "costco": ["paper towels", "chicken"],
        },
    )

    assert shopping_list.clear_list("Costco") is None
    assert _read_store(shopping_list) == {
        "default": ["milk"],
        "costco": [],
    }


def test_clear_missing_list_creates_an_empty_named_list(shopping_list):
    shopping_list.clear_list("Costco")

    assert _read_store(shopping_list) == {"costco": []}


def test_format_for_context_renders_populated_and_empty_lists(shopping_list):
    _write_store(
        shopping_list,
        {
            "default": ["milk", "eggs"],
            "costco": [],
        },
    )

    assert (
        shopping_list.format_for_context()
        == "**Default list:**\n"
        "  - milk\n"
        "  - eggs\n\n"
        "**Costco list:** (empty)"
    )


def test_invalid_json_file_is_treated_as_empty_and_can_be_recovered(shopping_list):
    shopping_list.LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    shopping_list.LISTS_FILE.write_text("{not valid json")

    assert shopping_list.get_all_lists() == {}
    assert shopping_list.add_item("milk") == ["milk"]
    assert _read_store(shopping_list) == {"default": ["milk"]}


@pytest.mark.parametrize(
    "bad_store",
    [
        [],
        {"default": "milk"},
        {"default": [1, 2, 3]},
        {"default": ["milk"], "costco": "paper towels"},
    ],
)
def test_schema_malformed_json_store_is_rejected_as_empty(shopping_list, bad_store):
    shopping_list.LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    shopping_list.LISTS_FILE.write_text(json.dumps(bad_store))

    assert shopping_list.get_all_lists() == {}
    assert shopping_list.get_list("default") == []


def test_empty_item_is_not_added_to_list(shopping_list):
    assert shopping_list.add_item("   ") == []
    assert _read_store(shopping_list) == {"default": []}


@pytest.mark.parametrize(
    ("func_name", "args"),
    [
        ("get_list", (None,)),
        ("add_item", (None, "default")),
        ("add_item", ("milk", None)),
        ("remove_item", (None, "default")),
        ("remove_item", ("milk", None)),
        ("clear_list", (None,)),
    ],
)
def test_none_inputs_are_rejected_without_mutating_existing_store(
    shopping_list, func_name, args
):
    _write_store(shopping_list, {"default": ["milk"]})
    before = shopping_list.LISTS_FILE.read_text()

    with pytest.raises((AttributeError, TypeError)):
        getattr(shopping_list, func_name)(*args)

    assert shopping_list.LISTS_FILE.read_text() == before


def test_very_long_item_round_trips_without_truncation(shopping_list):
    long_item = "x" * 10_000

    assert shopping_list.add_item(long_item) == [long_item]
    assert shopping_list.get_list("default") == [long_item]
    assert _read_store(shopping_list) == {"default": [long_item]}


def test_public_api_used_by_runtime_integration_points_exists_with_expected_signatures(
    shopping_list,
):
    for name in PUBLIC_API:
        assert callable(getattr(shopping_list, name))

    assert inspect.signature(shopping_list.get_list).parameters["name"].default == "default"
    assert (
        inspect.signature(shopping_list.add_item).parameters["list_name"].default
        == "default"
    )
    assert (
        inspect.signature(shopping_list.remove_item).parameters["list_name"].default
        == "default"
    )
    assert (
        inspect.signature(shopping_list.clear_list).parameters["list_name"].default
        == "default"
    )


def test_storage_integration_uses_single_json_file_under_data_home(shopping_list, tmp_path):
    shopping_list.add_item("milk")
    shopping_list.add_item("paper towels", "costco")

    assert sorted(path.name for path in tmp_path.iterdir()) == ["shopping_lists.json"]
    assert _read_store(shopping_list) == {
        "default": ["milk"],
        "costco": ["paper towels"],
    }


def test_context_formatter_reads_storage_without_writing_or_calling_model(
    shopping_list, monkeypatch
):
    load = Mock(return_value={"default": ["milk"]})
    save = Mock()
    monkeypatch.setattr(shopping_list, "_load", load)
    monkeypatch.setattr(shopping_list, "_save", save)

    assert shopping_list.format_for_context() == "**Default list:**\n  - milk"
    load.assert_called_once_with()
    save.assert_not_called()


def test_module_has_no_database_or_llm_import_dependencies(module_ast):
    imported_roots = set()
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    disallowed = {
        "anthropic",
        "chromadb",
        "google",
        "langchain",
        "llama_index",
        "openai",
        "psycopg2",
        "pymongo",
        "requests",
        "sqlite3",
    }
    assert imported_roots.isdisjoint(disallowed)


def test_module_contains_no_database_query_or_llm_call_sites(module_ast, module_source):
    disallowed_call_attrs = {
        "chat",
        "complete",
        "create",
        "embeddings",
        "execute",
        "executemany",
        "generate_content",
        "query",
    }
    called_attrs = {
        node.func.attr
        for node in ast.walk(module_ast)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert called_attrs.isdisjoint(disallowed_call_attrs)
    assert "select " not in module_source.lower()
    assert "insert " not in module_source.lower()
    assert "delete " not in module_source.lower()


def test_structural_no_mapping_or_lookup_table_is_present_without_audit_invariants(
    module_ast,
):
    assert _module_level_dict_assignments(module_ast) == {}


@pytest.mark.parametrize("func_name", sorted(DESTRUCTIVE_FUNCTIONS))
def test_structural_destructive_operations_require_explicit_confidence_threshold(
    shopping_list, func_name
):
    signature = inspect.signature(getattr(shopping_list, func_name))
    confidence_param = signature.parameters.get("confidence")

    assert confidence_param is not None, (
        f"{func_name} mutates persisted list state and must require an explicit "
        "numeric confidence parameter."
    )
    assert confidence_param.default is inspect.Signature.empty, (
        f"{func_name} must not be callable without an explicit confidence score."
    )


@pytest.mark.parametrize("func_name", sorted(DESTRUCTIVE_FUNCTIONS))
def test_structural_destructive_operations_block_borderline_confidence(
    shopping_list, func_name
):
    case = DESTRUCTIVE_FUNCTIONS[func_name]
    _write_store(shopping_list, case["seed"])
    before = _read_store(shopping_list)

    _call_allowing_refusal(
        getattr(shopping_list, func_name),
        *case["args"],
        confidence=0.79,
    )

    assert _read_store(shopping_list) == before


@pytest.mark.parametrize("func_name", sorted(DESTRUCTIVE_FUNCTIONS))
def test_structural_destructive_operations_allow_exact_threshold(
    shopping_list, func_name
):
    case = DESTRUCTIVE_FUNCTIONS[func_name]
    _write_store(shopping_list, case["seed"])

    getattr(shopping_list, func_name)(*case["args"], confidence=0.80)

    assert _read_store(shopping_list) == case["mutated"]


@pytest.mark.parametrize(
    ("func_name", "args"),
    [
        ("remove_item", ("   ", "default")),
        ("clear_list", ("   ",)),
    ],
)
def test_structural_destructive_operations_block_ambiguous_inputs_even_when_confident(
    shopping_list, func_name, args
):
    _write_store(shopping_list, {"default": ["milk"]})
    before = _read_store(shopping_list)

    _call_allowing_refusal(getattr(shopping_list, func_name), *args, confidence=1.0)

    assert _read_store(shopping_list) == before


def test_structural_storage_module_has_no_class_registry_or_handler_dispatch(module_ast):
    class_names = [node.name for node in ast.walk(module_ast) if isinstance(node, ast.ClassDef)]
    function_names = [
        node.name for node in ast.walk(module_ast) if isinstance(node, ast.FunctionDef)
    ]
    registry_names = {
        name
        for name in _module_level_dict_assignments(module_ast)
        if "registry" in name.lower() or "handler" in name.lower()
    }

    assert class_names == []
    assert registry_names == set()
    assert "handle" not in function_names
    assert "dispatch" not in function_names
