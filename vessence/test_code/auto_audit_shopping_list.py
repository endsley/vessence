import ast
import importlib.util
import inspect
import json
from pathlib import Path
from unittest.mock import Mock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "agent_skills" / "shopping_list.py"

DESTRUCTIVE_CASES = (
    pytest.param("remove_item", ("milk", "default"), id="remove_item"),
    pytest.param("clear_list", ("default",), id="clear_list"),
)
DESTRUCTIVE_SEED = {
    "default": ["milk", "eggs"],
    "costco": ["paper towels"],
}
DESTRUCTIVE_EXPECTED = {
    "remove_item": {
        "default": ["eggs"],
        "costco": ["paper towels"],
    },
    "clear_list": {
        "default": [],
        "costco": ["paper towels"],
    },
}
DB_AND_LLM_IMPORT_ROOTS = {
    "anthropic",
    "google.generativeai",
    "mysql",
    "openai",
    "psycopg",
    "psycopg2",
    "pymysql",
    "sqlite3",
    "sqlalchemy",
}


def _load_fresh_module(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path))
    module_name = f"_audit_shopping_list_{tmp_path.name}_{id(tmp_path)}"
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


def _call_destructive(module, function_name, args, **kwargs):
    return getattr(module, function_name)(*args, **kwargs)


def _module_import_roots(tree):
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            roots.add(parts[0] if len(parts) == 1 else ".".join(parts[:2]))
    return roots


def _module_level_lookup_tables(tree):
    lookup_names = {}
    markers = ("MAP", "MAPPING", "LOOKUP", "REGISTRY", "TABLE", "DISPATCH")
    for node in tree.body:
        value = None
        targets = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if not isinstance(value, ast.Dict):
            continue
        for target in targets:
            if isinstance(target, ast.Name) and any(marker in target.id.upper() for marker in markers):
                lookup_names[target.id] = value
    return lookup_names


def test_docstring_documents_json_file_storage_contract(module_source):
    module_docstring = ast.get_docstring(ast.parse(module_source))

    assert module_docstring is not None
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


@pytest.mark.parametrize("empty_item", ["", "   ", "\n\t"])
def test_add_item_does_not_store_empty_or_whitespace_items(shopping_list, empty_item):
    result = shopping_list.add_item(empty_item)

    assert result == []
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


def test_remove_item_from_missing_list_returns_empty_and_preserves_existing_lists(
    shopping_list,
):
    _write_store(shopping_list, {"default": ["milk"]})

    assert shopping_list.remove_item("milk", "missing", confidence=0.80) == []
    assert _read_store(shopping_list) == {"default": ["milk"]}


def test_clear_list_empties_named_list_and_persists_other_lists(shopping_list):
    _write_store(
        shopping_list,
        {
            "default": ["milk"],
            "costco": ["paper towels", "chicken"],
        },
    )

    assert shopping_list.clear_list("Costco", confidence=0.80) is None
    assert _read_store(shopping_list) == {
        "default": ["milk"],
        "costco": [],
    }


def test_clear_missing_list_creates_an_empty_named_list(shopping_list):
    shopping_list.clear_list("Costco", confidence=0.80)

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
        ["milk"],
        "milk",
        {"default": "milk"},
        {"default": [1]},
        {"default": ["milk"], "costco": [None]},
        {"default": ["milk"], "costco": ["valid"], "bad": [{"nested": "dict"}]},
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


def test_load_handles_read_errors_as_empty(shopping_list, monkeypatch):
    class BrokenFile:
        def exists(self):
            return True

        def read_text(self):
            raise OSError("disk unavailable")

    monkeypatch.setattr(shopping_list, "LISTS_FILE", BrokenFile())

    assert shopping_list.get_all_lists() == {}


@pytest.mark.parametrize(
    ("function_name", "args"),
    [
        ("get_list", (None,)),
        ("add_item", (None, "default")),
        ("add_item", ("milk", None)),
        ("remove_item", (None, "default")),
        ("remove_item", ("milk", None)),
        ("clear_list", (None,)),
    ],
)
def test_none_inputs_are_rejected_without_writing_files(
    shopping_list,
    function_name,
    args,
):
    kwargs = {"confidence": 0.80} if function_name in {"remove_item", "clear_list"} else {}

    with pytest.raises((AttributeError, TypeError, ValueError)):
        getattr(shopping_list, function_name)(*args, **kwargs)

    assert not shopping_list.LISTS_FILE.exists()


@pytest.mark.parametrize(
    ("function_name", "args", "kwargs"),
    [
        ("add_item", ("milk", ""), {}),
        ("add_item", ("milk", "   "), {}),
        ("remove_item", ("milk", ""), {"confidence": 0.80}),
        ("remove_item", ("milk", "   "), {"confidence": 0.80}),
        ("clear_list", ("",), {"confidence": 0.80}),
        ("clear_list", ("   ",), {"confidence": 0.80}),
    ],
)
def test_mutations_reject_blank_list_names_without_persisting_bad_keys(
    shopping_list,
    function_name,
    args,
    kwargs,
):
    with pytest.raises(ValueError):
        getattr(shopping_list, function_name)(*args, **kwargs)

    assert not shopping_list.LISTS_FILE.exists()


@pytest.mark.parametrize("function_name,args", DESTRUCTIVE_CASES)
def test_destructive_operations_reject_blank_items_without_mutating_store(
    shopping_list,
    function_name,
    args,
):
    if function_name != "remove_item":
        pytest.skip("clear_list has no item argument")
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    with pytest.raises(ValueError):
        _call_destructive(shopping_list, function_name, ("   ", args[1]), confidence=0.80)

    assert _read_store(shopping_list) == DESTRUCTIVE_SEED


def test_very_long_item_and_list_name_round_trip(shopping_list):
    long_item = "x" * 10000
    long_list_name = "A" * 512

    assert shopping_list.add_item(long_item, long_list_name) == [long_item]
    assert shopping_list.get_list(long_list_name) == [long_item]
    assert _read_store(shopping_list) == {long_list_name.lower(): [long_item]}
    assert long_item in shopping_list.format_for_context()


def test_save_creates_parent_directories_and_writes_json_file(shopping_list, tmp_path, monkeypatch):
    nested_file = tmp_path / "missing" / "nested" / "shopping_lists.json"
    monkeypatch.setattr(shopping_list, "LISTS_FILE", nested_file)

    shopping_list._save({"default": ["milk"]})

    assert nested_file.exists()
    assert nested_file.read_text() == '{\n  "default": [\n    "milk"\n  ]\n}\n'


def test_format_for_context_integration_uses_load_result_for_llm_context(
    shopping_list,
    monkeypatch,
):
    mocked_load = Mock(return_value={"default": ["milk"], "costco": []})
    monkeypatch.setattr(shopping_list, "_load", mocked_load)

    assert (
        shopping_list.format_for_context()
        == "**Default list:**\n  - milk\n\n**Costco list:** (empty)"
    )
    mocked_load.assert_called_once_with()


def test_module_has_no_direct_database_or_llm_integrations(module_ast):
    import_roots = _module_import_roots(module_ast)

    assert import_roots.isdisjoint(DB_AND_LLM_IMPORT_ROOTS)


def test_public_api_does_not_call_database_or_llm_symbols(module_ast):
    banned_names = {
        "anthropic",
        "chat",
        "completion",
        "connect",
        "cursor",
        "execute",
        "generativeai",
        "openai",
        "query",
        "sqlite3",
    }
    calls = set()
    for node in ast.walk(module_ast):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id.lower())
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr.lower())

    assert calls.isdisjoint(banned_names)


def test_structural_invariant_no_lookup_or_dispatch_table_is_present(module_ast):
    assert _module_level_lookup_tables(module_ast) == {}


def test_structural_invariant_no_class_registry_or_handler_dispatch_is_present(module_ast):
    class_names = [
        node.name for node in module_ast.body if isinstance(node, ast.ClassDef)
    ]
    handler_functions = [
        node.name
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("handle_")
    ]

    assert class_names == []
    assert handler_functions == []


def test_confidence_threshold_constant_is_numeric_and_strict(shopping_list):
    assert isinstance(shopping_list._CONFIDENCE_THRESHOLD, float)
    assert shopping_list._CONFIDENCE_THRESHOLD == 0.80


@pytest.mark.parametrize("function_name,args", DESTRUCTIVE_CASES)
def test_destructive_operations_expose_required_keyword_only_confidence(
    shopping_list,
    function_name,
    args,
):
    signature = inspect.signature(getattr(shopping_list, function_name))
    confidence = signature.parameters["confidence"]

    assert confidence.kind is inspect.Parameter.KEYWORD_ONLY
    assert confidence.default is inspect.Parameter.empty


@pytest.mark.parametrize("function_name,args", DESTRUCTIVE_CASES)
def test_destructive_implementation_has_no_missing_confidence_bypass(
    shopping_list,
    function_name,
    args,
):
    function = getattr(shopping_list, function_name)
    kwdefaults = function.__kwdefaults__ or {}

    assert "confidence" not in kwdefaults


@pytest.mark.parametrize("function_name,args", DESTRUCTIVE_CASES)
def test_destructive_operations_reject_missing_confidence_without_mutating_store(
    shopping_list,
    function_name,
    args,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    with pytest.raises((PermissionError, TypeError)):
        _call_destructive(shopping_list, function_name, args)

    assert _read_store(shopping_list) == DESTRUCTIVE_SEED


@pytest.mark.parametrize("function_name,args", DESTRUCTIVE_CASES)
@pytest.mark.parametrize("confidence", [-1.0, 0.0, 0.50, 0.79, 0.799999])
def test_destructive_operations_reject_below_threshold_confidence_without_mutating_store(
    shopping_list,
    function_name,
    args,
    confidence,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    with pytest.raises(PermissionError):
        _call_destructive(shopping_list, function_name, args, confidence=confidence)

    assert _read_store(shopping_list) == DESTRUCTIVE_SEED


@pytest.mark.parametrize("function_name,args", DESTRUCTIVE_CASES)
@pytest.mark.parametrize("confidence", [None, "High", "0.95", True, False, object()])
def test_destructive_operations_reject_ambiguous_confidence_without_mutating_store(
    shopping_list,
    function_name,
    args,
    confidence,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    with pytest.raises((PermissionError, TypeError)):
        _call_destructive(shopping_list, function_name, args, confidence=confidence)

    assert _read_store(shopping_list) == DESTRUCTIVE_SEED


@pytest.mark.parametrize("function_name,args", DESTRUCTIVE_CASES)
@pytest.mark.parametrize("confidence", [0.80, 0.95, 1.0])
def test_destructive_operations_allow_exact_threshold_or_higher_numeric_confidence(
    shopping_list,
    function_name,
    args,
    confidence,
):
    _write_store(shopping_list, DESTRUCTIVE_SEED)

    result = _call_destructive(shopping_list, function_name, args, confidence=confidence)

    assert _read_store(shopping_list) == DESTRUCTIVE_EXPECTED[function_name]
    if function_name == "remove_item":
        assert result == ["eggs"]
    else:
        assert result is None


@pytest.mark.parametrize("function_name,args", DESTRUCTIVE_CASES)
def test_destructive_refusal_does_not_call_save(shopping_list, monkeypatch, function_name, args):
    _write_store(shopping_list, DESTRUCTIVE_SEED)
    save = Mock()
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
