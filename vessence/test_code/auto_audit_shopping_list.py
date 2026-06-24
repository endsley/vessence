import ast
import importlib.util
import inspect
import json
import math
import sys
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "agent_skills" / "shopping_list.py"

DESTRUCTIVE_SEED = {
    "default": ["milk", "eggs", "Bread"],
    "costco": ["paper towels", "chicken"],
}
DESTRUCTIVE_CASES = (
    ("remove_item", ("milk", "default"), {"default": ["eggs", "Bread"], "costco": ["paper towels", "chicken"]}),
    ("clear_list", ("costco",), {"default": ["milk", "eggs", "Bread"], "costco": []}),
)


def _import_shopping_list(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path))
    module_name = f"_audit_shopping_list_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except Exception:
        sys.modules.pop(module_name, None)
        raise


@pytest.fixture
def shopping_list(tmp_path, monkeypatch):
    module = _import_shopping_list(tmp_path, monkeypatch)
    try:
        yield module
    finally:
        sys.modules.pop(module.__name__, None)


def _read_store(module):
    return json.loads(module.LISTS_FILE.read_text())


def _write_store(module, payload):
    module.LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    module.LISTS_FILE.write_text(json.dumps(payload, indent=2) + "\n")


def _source_tree():
    return ast.parse(MODULE_PATH.read_text())


def _call_destructive(module, function_name, args, confidence=0.80):
    return getattr(module, function_name)(*args, confidence=confidence)


def _public_function_names():
    return {
        node.name
        for node in _source_tree().body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }


def test_module_docstring_documents_json_storage_shape():
    module_docstring = ast.get_docstring(_source_tree())

    assert module_docstring is not None
    assert "Shopping list manager" in module_docstring
    assert "VESSENCE_DATA_HOME/shopping_lists.json" in module_docstring
    assert '"default": ["milk", "eggs", "bread"]' in module_docstring
    assert '"costco": ["paper towels", "chicken"]' in module_docstring


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
    assert shopping_list.LISTS_FILE.read_text().endswith("\n")
    assert "\n  " in shopping_list.LISTS_FILE.read_text()


def test_add_item_trims_item_lowercases_list_name_and_deduplicates_case_insensitively(
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


@pytest.mark.parametrize("empty_item", ["", "   ", "\n\t"])
def test_add_item_does_not_store_empty_or_whitespace_items(shopping_list, empty_item):
    result = shopping_list.add_item(empty_item)

    assert result == []
    assert _read_store(shopping_list) == {"default": []}
    assert all(
        item.strip()
        for items in _read_store(shopping_list).values()
        for item in items
    )


def test_remove_item_is_case_insensitive_and_scoped_to_named_list(shopping_list):
    _write_store(
        shopping_list,
        {
            "default": ["Milk", "eggs", "bread"],
            "costco": ["milk", "paper towels"],
        },
    )

    result = shopping_list.remove_item(" milk ", "DEFAULT", confidence=0.80)

    assert result == ["eggs", "bread"]
    assert _read_store(shopping_list) == {
        "default": ["eggs", "bread"],
        "costco": ["milk", "paper towels"],
    }


def test_remove_item_from_missing_list_returns_empty_and_does_not_create_list(
    shopping_list,
):
    _write_store(shopping_list, {"default": ["milk"]})

    assert shopping_list.remove_item("milk", "missing", confidence=0.80) == []
    assert _read_store(shopping_list) == {"default": ["milk"]}


def test_remove_absent_item_from_existing_list_preserves_items(shopping_list):
    _write_store(shopping_list, {"default": ["milk", "eggs"]})

    assert shopping_list.remove_item("bread", confidence=0.80) == ["milk", "eggs"]
    assert _read_store(shopping_list) == {"default": ["milk", "eggs"]}


def test_clear_list_empties_named_list_and_persists_other_lists(shopping_list):
    _write_store(
        shopping_list,
        {
            "default": ["milk", "eggs"],
            "costco": ["paper towels", "chicken"],
        },
    )

    assert shopping_list.clear_list("Costco", confidence=0.80) is None
    assert _read_store(shopping_list) == {
        "default": ["milk", "eggs"],
        "costco": [],
    }


def test_clear_missing_list_creates_an_empty_named_list(shopping_list):
    shopping_list.clear_list("Costco", confidence=0.80)

    assert _read_store(shopping_list) == {"costco": []}
    assert shopping_list.get_list("costco") == []


def test_format_for_context_renders_populated_and_empty_lists(shopping_list):
    _write_store(
        shopping_list,
        {
            "default": ["milk", "eggs"],
            "costco": [],
            "hardware": ["bolts"],
        },
    )

    assert (
        shopping_list.format_for_context()
        == "**Default list:**\n"
        "  - milk\n"
        "  - eggs\n\n"
        "**Costco list:** (empty)\n\n"
        "**Hardware list:**\n"
        "  - bolts"
    )


def test_invalid_json_file_is_treated_as_empty_and_can_be_recovered(shopping_list):
    shopping_list.LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    shopping_list.LISTS_FILE.write_text("{not valid json")

    assert shopping_list.get_all_lists() == {}
    assert shopping_list.format_for_context() == (
        "No shopping lists exist yet. The user can ask you to create one."
    )

    assert shopping_list.add_item("milk") == ["milk"]
    assert _read_store(shopping_list) == {"default": ["milk"]}


@pytest.mark.parametrize(
    "bad_store",
    [
        [],
        ["default", ["milk"]],
        "not a dict",
        123,
        None,
        {"default": "milk"},
        {"default": [1, "milk"]},
        {"default": [{"name": "milk"}]},
        {"default": ["milk"], "bad": [None]},
    ],
)
def test_malformed_json_shapes_are_treated_as_empty(shopping_list, bad_store):
    _write_store(shopping_list, bad_store)

    assert shopping_list.get_all_lists() == {}
    assert shopping_list.get_list("default") == []
    assert (
        shopping_list.format_for_context()
        == "No shopping lists exist yet. The user can ask you to create one."
    )


def test_load_rejects_non_string_json_keys_returned_by_parser(shopping_list, monkeypatch):
    shopping_list.LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    shopping_list.LISTS_FILE.write_text("{}")
    monkeypatch.setattr(shopping_list.json, "loads", Mock(return_value={1: ["milk"]}))

    assert shopping_list.get_all_lists() == {}


def test_load_rejects_non_list_values_returned_by_parser(shopping_list, monkeypatch):
    shopping_list.LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    shopping_list.LISTS_FILE.write_text("{}")
    monkeypatch.setattr(
        shopping_list.json,
        "loads",
        Mock(return_value={"default": ("milk",)}),
    )

    assert shopping_list.get_all_lists() == {}


def test_load_handles_read_errors_as_empty(shopping_list, monkeypatch):
    class BrokenFile:
        def exists(self):
            return True

        def read_text(self):
            raise OSError("read failed")

    monkeypatch.setattr(shopping_list, "LISTS_FILE", BrokenFile())

    assert shopping_list.get_all_lists() == {}


@pytest.mark.parametrize(
    ("function_name", "args", "expected_exception"),
    [
        ("get_list", (None,), AttributeError),
        ("add_item", (None,), AttributeError),
        ("add_item", ("milk", None), AttributeError),
        ("remove_item", (None, "default"), AttributeError),
        ("remove_item", ("milk", None), AttributeError),
        ("clear_list", (None,), AttributeError),
    ],
)
def test_none_inputs_raise_without_creating_storage_file(
    shopping_list,
    function_name,
    args,
    expected_exception,
):
    kwargs = {"confidence": 0.80} if function_name in {"remove_item", "clear_list"} else {}

    with pytest.raises(expected_exception):
        getattr(shopping_list, function_name)(*args, **kwargs)

    assert not shopping_list.LISTS_FILE.exists()


@pytest.mark.parametrize(
    ("function_name", "args"),
    [
        ("add_item", ("milk", "")),
        ("add_item", ("milk", "   ")),
        ("remove_item", ("milk", "")),
        ("remove_item", ("milk", "   ")),
        ("clear_list", ("",)),
        ("clear_list", ("   ",)),
    ],
)
def test_empty_list_name_is_rejected_without_storage_mutation(
    shopping_list,
    function_name,
    args,
):
    _write_store(shopping_list, {"default": ["milk"]})
    kwargs = {"confidence": 0.80} if function_name in {"remove_item", "clear_list"} else {}

    with pytest.raises(ValueError, match="list_name is required"):
        getattr(shopping_list, function_name)(*args, **kwargs)

    assert _read_store(shopping_list) == {"default": ["milk"]}


@pytest.mark.parametrize("empty_item", ["", " ", "\n\t"])
def test_empty_remove_item_is_rejected_without_storage_mutation(shopping_list, empty_item):
    _write_store(shopping_list, {"default": ["milk"]})

    with pytest.raises(ValueError, match="item is required"):
        shopping_list.remove_item(empty_item, confidence=0.80)

    assert _read_store(shopping_list) == {"default": ["milk"]}


def test_very_long_item_and_list_name_round_trip(shopping_list):
    long_item = "x" * 10_000
    long_list_name = "weekly-" + ("a" * 1_000)

    assert shopping_list.add_item(long_item, long_list_name) == [long_item]
    assert shopping_list.get_list(long_list_name) == [long_item]
    assert _read_store(shopping_list) == {long_list_name.lower(): [long_item]}
    assert long_item in shopping_list.format_for_context()


def test_save_creates_parent_directories_and_writes_json_file(shopping_list, tmp_path, monkeypatch):
    nested_file = tmp_path / "missing" / "nested" / "shopping_lists.json"
    monkeypatch.setattr(shopping_list, "LISTS_FILE", nested_file)

    shopping_list._save({"default": ["milk"]})

    assert nested_file.exists()
    assert json.loads(nested_file.read_text()) == {"default": ["milk"]}


def test_load_uses_json_loads_for_file_storage_integration(shopping_list, monkeypatch):
    shopping_list.LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    shopping_list.LISTS_FILE.write_text('{"default": ["milk"]}')
    mocked_loads = Mock(return_value={"default": ["from mock"]})
    monkeypatch.setattr(shopping_list.json, "loads", mocked_loads)

    assert shopping_list.get_all_lists() == {"default": ["from mock"]}
    mocked_loads.assert_called_once_with('{"default": ["milk"]}')


def test_format_for_context_uses_storage_snapshot_without_llm_call(
    shopping_list,
    monkeypatch,
):
    mocked_load = Mock(return_value={"default": ["milk"]})
    monkeypatch.setattr(shopping_list, "_load", mocked_load)

    assert shopping_list.format_for_context() == "**Default list:**\n  - milk"
    mocked_load.assert_called_once_with()


def test_module_imports_no_database_or_llm_client_integrations():
    tree = _source_tree()
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    forbidden_imports = {
        "openai",
        "anthropic",
        "google",
        "requests",
        "httpx",
        "sqlite3",
        "sqlalchemy",
        "psycopg2",
        "pymysql",
        "mysql",
    }
    assert imported_roots.isdisjoint(forbidden_imports)


def test_module_makes_no_database_query_or_llm_generation_calls():
    forbidden_call_names = {
        "execute",
        "executemany",
        "query",
        "raw",
        "chat",
        "completions",
        "responses",
        "generate_content",
        "create",
    }
    call_names = set()
    for node in ast.walk(_source_tree()):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    assert call_names.isdisjoint(forbidden_call_names)


def test_persisted_mapping_uses_lowercase_keys_and_list_of_string_values(shopping_list):
    shopping_list.add_item("Milk", "Default")
    shopping_list.add_item("eggs", "DEFAULT")
    shopping_list.add_item("Paper Towels", "Costco")

    data = _read_store(shopping_list)
    assert data == {"default": ["Milk", "eggs"], "costco": ["Paper Towels"]}
    assert all(name == name.lower() and name.strip() for name in data)
    assert all(isinstance(items, list) for items in data.values())
    assert all(isinstance(item, str) and item for items in data.values() for item in items)


def test_every_persisted_mapping_value_is_reachable_by_public_get_list(shopping_list):
    shopping_list.add_item("milk", "Default")
    shopping_list.add_item("paper towels", "Costco")
    data = _read_store(shopping_list)

    for list_name, items in data.items():
        assert shopping_list.get_list(list_name) == items
        assert shopping_list.get_list(list_name.upper()) == items


def test_no_module_level_lookup_table_or_registry_requires_key_value_invariants():
    tree = _source_tree()
    module_level_dict_assignments = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            module_level_dict_assignments.extend(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict):
            if isinstance(node.target, ast.Name):
                module_level_dict_assignments.append(node.target.id)

    assert module_level_dict_assignments == []


def test_no_class_registry_or_handler_dispatch_exists_in_this_module():
    tree = _source_tree()
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    handler_functions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (node.name.startswith("handle_") or node.name.endswith("_handler"))
    ]

    assert class_names == []
    assert handler_functions == []


def test_public_api_surface_matches_documented_shopping_list_manager():
    assert _public_function_names() == {
        "get_all_lists",
        "get_list",
        "add_item",
        "remove_item",
        "clear_list",
        "format_for_context",
    }


def test_confidence_threshold_constant_is_numeric_and_strict(shopping_list):
    assert isinstance(shopping_list._CONFIDENCE_THRESHOLD, float)
    assert shopping_list._CONFIDENCE_THRESHOLD == 0.80


@pytest.mark.parametrize("function_name", ["remove_item", "clear_list"])
def test_destructive_operations_require_keyword_only_confidence_without_default(
    shopping_list,
    function_name,
):
    signature = inspect.signature(getattr(shopping_list, function_name))
    confidence = signature.parameters["confidence"]

    assert confidence.kind is inspect.Parameter.KEYWORD_ONLY
    assert confidence.default is inspect.Parameter.empty


@pytest.mark.parametrize("function_name", ["remove_item", "clear_list"])
def test_destructive_operations_raise_when_confidence_is_omitted(
    shopping_list,
    function_name,
):
    function = getattr(shopping_list, function_name)

    with pytest.raises(TypeError):
        function("milk")


@pytest.mark.parametrize(
    ("function_name", "args", "_expected"),
    DESTRUCTIVE_CASES,
)
def test_destructive_operations_check_confidence_before_touching_storage(
    shopping_list,
    monkeypatch,
    function_name,
    args,
    _expected,
):
    monkeypatch.setattr(
        shopping_list,
        "_load",
        Mock(side_effect=AssertionError("storage should not be read")),
    )
    monkeypatch.setattr(
        shopping_list,
        "_save",
        Mock(side_effect=AssertionError("storage should not be written")),
    )

    with pytest.raises(PermissionError):
        _call_destructive(shopping_list, function_name, args, confidence=0.79)


@pytest.mark.parametrize(
    ("function_name", "args", "_expected"),
    DESTRUCTIVE_CASES,
)
@pytest.mark.parametrize("confidence", [None, True, False, "High", "0.95", object()])
def test_destructive_operations_reject_non_numeric_confidence_without_mutating(
    shopping_list,
    function_name,
    args,
    _expected,
    confidence,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    with pytest.raises(TypeError, match="confidence must be numeric"):
        _call_destructive(shopping_list, function_name, args, confidence=confidence)

    assert _read_store(shopping_list) == DESTRUCTIVE_SEED


@pytest.mark.parametrize(
    ("function_name", "args", "_expected"),
    DESTRUCTIVE_CASES,
)
@pytest.mark.parametrize(
    "confidence",
    [
        -1,
        0,
        0.5,
        0.79,
        0.799999,
        math.nextafter(0.80, 0),
        float("nan"),
    ],
)
def test_destructive_operations_reject_borderline_or_ambiguous_confidence_without_mutating(
    shopping_list,
    function_name,
    args,
    _expected,
    confidence,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    with pytest.raises(PermissionError, match="confidence is below the required threshold"):
        _call_destructive(shopping_list, function_name, args, confidence=confidence)

    assert _read_store(shopping_list) == DESTRUCTIVE_SEED


@pytest.mark.parametrize(
    ("function_name", "args", "expected"),
    DESTRUCTIVE_CASES,
)
@pytest.mark.parametrize("confidence", [0.80, 0.8000001, 1, 1.0, float("inf")])
def test_destructive_operations_allow_exact_threshold_and_above(
    shopping_list,
    function_name,
    args,
    expected,
    confidence,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    result = _call_destructive(shopping_list, function_name, args, confidence=confidence)

    assert _read_store(shopping_list) == expected
    if function_name == "remove_item":
        assert result == expected["default"]
    else:
        assert result is None


@pytest.mark.parametrize(
    ("function_name", "args"),
    [
        ("remove_item", ("   ", "default")),
        ("remove_item", ("milk", "   ")),
        ("clear_list", ("   ",)),
    ],
)
def test_destructive_operations_cannot_fire_on_ambiguous_empty_input(
    shopping_list,
    function_name,
    args,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    with pytest.raises(ValueError):
        _call_destructive(shopping_list, function_name, args, confidence=0.80)

    assert _read_store(shopping_list) == DESTRUCTIVE_SEED


@pytest.mark.parametrize(
    ("function_name", "args", "_expected"),
    DESTRUCTIVE_CASES,
)
def test_destructive_refusal_does_not_call_save(
    shopping_list,
    monkeypatch,
    function_name,
    args,
    _expected,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)
    save = Mock(wraps=shopping_list._save)
    monkeypatch.setattr(shopping_list, "_save", save)

    with pytest.raises(PermissionError):
        _call_destructive(shopping_list, function_name, args, confidence=0.79)

    save.assert_not_called()
    assert _read_store(shopping_list) == DESTRUCTIVE_SEED


def test_remove_item_signature_matches_public_tool_contract(shopping_list):
    signature = inspect.signature(shopping_list.remove_item)

    assert list(signature.parameters) == ["item", "list_name", "confidence"]
    assert signature.parameters["item"].default is inspect.Parameter.empty
    assert signature.parameters["list_name"].default == "default"
    assert signature.parameters["confidence"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["confidence"].default is inspect.Parameter.empty


def test_clear_list_signature_matches_public_tool_contract(shopping_list):
    signature = inspect.signature(shopping_list.clear_list)

    assert list(signature.parameters) == ["list_name", "confidence"]
    assert signature.parameters["list_name"].default == "default"
    assert signature.parameters["confidence"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["confidence"].default is inspect.Parameter.empty
