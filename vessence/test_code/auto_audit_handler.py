"""Auto-audit tests for jane_web.jane_v2.classes.read_messages.handler."""

from __future__ import annotations

import ast
import importlib
import inspect
import logging
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


VESSENCE_ROOT = Path(__file__).resolve().parents[1]
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

MODULE_NAME = "jane_web.jane_v2.classes.read_messages.handler"
METADATA_MODULE_NAME = "jane_web.jane_v2.classes.read_messages.metadata"
MODULE_PATH = VESSENCE_ROOT / "jane_web/jane_v2/classes/read_messages/handler.py"

handler = importlib.import_module(MODULE_NAME)


class _LowerReturnsNone:
    def lower(self):
        return None


@pytest.fixture
def read_handler():
    return importlib.import_module(MODULE_NAME)


@pytest.fixture
def read_metadata():
    return importlib.import_module(METADATA_MODULE_NAME)


@pytest.fixture
def forbidden_database_module(monkeypatch):
    fake_database = ModuleType("database")
    fake_database.get_db = Mock(
        side_effect=AssertionError("read_messages.handler must not query the DB")
    )
    monkeypatch.setitem(sys.modules, "database", fake_database)
    return fake_database


@pytest.fixture
def forbidden_llm_modules(monkeypatch):
    modules: dict[str, ModuleType] = {}

    fake_httpx = ModuleType("httpx")
    fake_httpx.AsyncClient = Mock(
        side_effect=AssertionError("read_messages.handler must not call an LLM")
    )
    modules["httpx"] = fake_httpx

    fake_openai = ModuleType("openai")
    fake_openai.OpenAI = Mock(
        side_effect=AssertionError("read_messages.handler must not call OpenAI")
    )
    fake_openai.AsyncOpenAI = Mock(
        side_effect=AssertionError("read_messages.handler must not call OpenAI")
    )
    modules["openai"] = fake_openai

    fake_ollama = ModuleType("ollama")
    fake_ollama.chat = Mock(
        side_effect=AssertionError("read_messages.handler must not call Ollama")
    )
    fake_ollama.generate = Mock(
        side_effect=AssertionError("read_messages.handler must not call Ollama")
    )
    modules["ollama"] = fake_ollama

    fake_models = ModuleType("jane_web.jane_v2.models")
    fake_models.LOCAL_LLM = "should-not-be-read"
    fake_models.call_model = Mock(
        side_effect=AssertionError("read_messages.handler must not call models")
    )
    modules["jane_web.jane_v2.models"] = fake_models

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    return modules


def _module_ast() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text())


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _assert_documented_handler_shape(result):
    if result is None:
        return
    assert isinstance(result, dict)
    if result == {"wrong_class": True}:
        return
    assert isinstance(result.get("text"), str)


def test_docstring_is_the_spec_and_documents_escalation_contract(read_handler):
    doc = inspect.getdoc(read_handler)

    assert doc is not None
    assert "always escalates to Stage 3" in doc
    assert "returns None to escalate" in doc
    assert "wrong_class" not in doc.lower() or "misclassified" in doc.lower()
    assert "_escalation_context()" in doc


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        "read my messages",
        "any new texts?",
        "what did Kathia text me?",
        "any unread messages",
        "check my inbox",
        "do I have any new messages",
        "please read the SMS inbox",
    ],
)
async def test_documented_read_message_requests_escalate_to_stage3(read_handler, prompt):
    result = await read_handler.handle(prompt)

    assert result is None


@pytest.mark.asyncio
async def test_context_and_params_do_not_change_stage3_escalation(read_handler):
    params = {"filter_sender": "Kathia", "unread_only": True, "limit": 5}
    before = dict(params)

    result = await read_handler.handle(
        "what did Kathia text me?",
        context="The previous assistant turn mentioned architecture.",
        params=params,
    )

    assert result is None
    assert params == before


@pytest.mark.asyncio
@pytest.mark.parametrize("arch_word", sorted(handler._ARCH_WORDS))
async def test_architecture_lookup_words_return_wrong_class(read_handler, arch_word):
    result = await read_handler.handle(f"Can you explain the {arch_word} for this?")

    assert result == {"wrong_class": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("meta_phrase", sorted(handler._META_PHRASES))
async def test_meta_lookup_phrases_return_wrong_class(read_handler, meta_phrase):
    result = await read_handler.handle(f"{meta_phrase}?")

    assert result == {"wrong_class": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        "WHY WAS YOUR LAST REPLY SO SLOW?",
        "Can you explain the HANDLER pipeline?",
        "Your Previous Message took a while.",
    ],
)
async def test_wrong_class_guards_are_case_insensitive(read_handler, prompt):
    result = await read_handler.handle(prompt)

    assert result == {"wrong_class": True}


@pytest.mark.asyncio
async def test_non_meta_message_word_still_escalates(read_handler):
    result = await read_handler.handle("read the message from Mom")

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", ["", " ", "\n\t", "???"])
async def test_empty_or_content_free_input_escalates_to_stage3(read_handler, prompt):
    result = await read_handler.handle(prompt)

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bad_prompt", "expected_exception"),
    [
        (None, AttributeError),
        (123, AttributeError),
        (object(), AttributeError),
        (b"read my messages", TypeError),
        (_LowerReturnsNone(), TypeError),
    ],
)
async def test_malformed_prompt_types_fail_loudly(read_handler, bad_prompt, expected_exception):
    with pytest.raises(expected_exception):
        await read_handler.handle(bad_prompt)


@pytest.mark.asyncio
async def test_none_context_and_malformed_params_are_ignored_for_valid_prompt(read_handler):
    result = await read_handler.handle(
        "any new texts?",
        context=None,
        params="not-a-dict",
    )

    assert result is None


@pytest.mark.asyncio
async def test_very_long_read_prompt_escalates_without_side_effects(read_handler):
    long_prompt = "please read my texts. " * 10_000

    result = await read_handler.handle(long_prompt)

    assert result is None


@pytest.mark.asyncio
async def test_very_long_meta_prompt_still_trips_wrong_class_guard(read_handler):
    long_prompt = ("please " * 10_000) + "why was your last reply so slow?"

    result = await read_handler.handle(long_prompt)

    assert result == {"wrong_class": True}


@pytest.mark.asyncio
async def test_escalation_path_logs_stage3_decision(read_handler, caplog):
    caplog.set_level(logging.INFO, logger=read_handler.logger.name)

    result = await read_handler.handle("read my messages")

    assert result is None
    assert "escalating to Stage 3" in caplog.text


@pytest.mark.asyncio
async def test_meta_guard_logs_wrong_class_decision(read_handler, caplog):
    caplog.set_level(logging.INFO, logger=read_handler.logger.name)

    result = await read_handler.handle("your last reply took too long")

    assert result == {"wrong_class": True}
    assert "wrong_class" in caplog.text


@pytest.mark.asyncio
async def test_handler_does_not_query_db_or_call_llm_for_read_requests(
    read_handler,
    forbidden_database_module,
    forbidden_llm_modules,
):
    result = await read_handler.handle(
        "read my unread texts from Kathia",
        context="existing context",
        params={"filter_sender": "Kathia", "unread_only": True, "limit": 3},
    )

    assert result is None
    forbidden_database_module.get_db.assert_not_called()
    forbidden_llm_modules["httpx"].AsyncClient.assert_not_called()
    forbidden_llm_modules["openai"].OpenAI.assert_not_called()
    forbidden_llm_modules["openai"].AsyncOpenAI.assert_not_called()
    forbidden_llm_modules["ollama"].chat.assert_not_called()
    forbidden_llm_modules["ollama"].generate.assert_not_called()
    forbidden_llm_modules["jane_web.jane_v2.models"].call_model.assert_not_called()


@pytest.mark.asyncio
async def test_handler_does_not_pull_metadata_escalation_context(
    read_handler,
    read_metadata,
    monkeypatch,
):
    context_builder = Mock(
        side_effect=AssertionError("metadata escalation context is Stage 3 prefetch only")
    )
    monkeypatch.setattr(read_metadata, "_escalation_context", context_builder)
    monkeypatch.setitem(read_metadata.METADATA, "escalation_context", context_builder)

    result = await read_handler.handle("check my inbox")

    assert result is None
    context_builder.assert_not_called()


def test_handler_imports_only_logging_as_runtime_dependency():
    imported_modules = set()
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            imported_modules.add((node.module or "").split(".", 1)[0])

    assert imported_modules == {"logging"}


def test_handler_ast_has_no_db_llm_network_or_tool_calls():
    dangerous_fragments = {
        "get_db",
        "execute",
        "fetchall",
        "fetchone",
        "commit",
        "AsyncClient",
        "OpenAI",
        "AsyncOpenAI",
        "chat",
        "generate",
        "complete",
        "sms_send",
        "send_direct",
    }
    calls = [_call_name(node.func) for node in ast.walk(_module_ast()) if isinstance(node, ast.Call)]
    offending = {
        call
        for call in calls
        for fragment in dangerous_fragments
        if fragment in call
    }

    assert offending == set()


def test_lookup_tables_are_literal_nonempty_lowercase_tuples(read_handler):
    for name in ("_ARCH_WORDS", "_META_PHRASES"):
        table = getattr(read_handler, name)
        assert isinstance(table, tuple)
        assert table
        assert len(table) == len(set(table))
        for item in table:
            assert isinstance(item, str)
            assert item.strip() == item
            assert item
            assert item == item.lower()


def test_lookup_tables_do_not_have_known_contradictory_entries(read_handler):
    arch_words = set(read_handler._ARCH_WORDS)
    meta_phrases = set(read_handler._META_PHRASES)
    positive_read_starters = (
        "read my",
        "any new",
        "what did",
        "check my inbox",
        "do i have",
    )

    assert arch_words.isdisjoint(meta_phrases)
    for entry in arch_words | meta_phrases:
        assert not entry.startswith(positive_read_starters)


@pytest.mark.asyncio
async def test_every_architecture_lookup_value_is_reachable(read_handler):
    for arch_word in read_handler._ARCH_WORDS:
        result = await read_handler.handle(f"debug the {arch_word} please")
        assert result == {"wrong_class": True}, arch_word


@pytest.mark.asyncio
async def test_every_meta_lookup_value_is_reachable(read_handler):
    for meta_phrase in read_handler._META_PHRASES:
        result = await read_handler.handle(meta_phrase)
        assert result == {"wrong_class": True}, meta_phrase


def test_handler_module_has_no_mapping_dict_or_dispatch_registry(read_handler):
    module_level_dicts = {
        name: value
        for name, value in vars(read_handler).items()
        if not name.startswith("__") and isinstance(value, dict)
    }

    assert module_level_dicts == {}


def test_handler_source_has_no_destructive_operations_or_client_tool_markers():
    source = MODULE_PATH.read_text()
    destructive_markers = {
        "contacts.sms_send_direct",
        "sms_send_direct",
        "send_message(",
        "email.send",
        "email.delete",
        "messages.delete",
        "timer.delete",
        "end_conversation",
        "DELETE FROM",
        "UPDATE ",
        "INSERT INTO",
    }
    offending = {marker for marker in destructive_markers if marker in source}

    assert offending == set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ambiguous_prompt",
    [
        "tell Bob I can read his message later",
        "I might need to check messages eventually",
        "do not send anything, just wondering about texts",
    ],
)
async def test_ambiguous_input_never_emits_destructive_or_direct_tool_result(
    read_handler,
    ambiguous_prompt,
):
    result = await read_handler.handle(ambiguous_prompt)

    assert result is None or result == {"wrong_class": True}
    if isinstance(result, dict):
        assert "text" not in result
        assert "CLIENT_TOOL" not in repr(result)


def test_stage1_read_messages_mapping_is_registered_and_not_fallback():
    from jane_web.jane_v2 import classes, stage1_classifier

    registry = classes.get_registry(refresh=True)
    mapped = stage1_classifier._CLASS_MAP["READ_MESSAGES"]

    assert mapped == "read messages"
    assert mapped in registry
    assert mapped != "others"
    assert "READ_MESSAGES" in stage1_classifier.STRICT_CLASSES
    assert stage1_classifier._gate_for("READ_MESSAGES")["conf"] >= 0.80


def test_stage1_fallback_mappings_do_not_contradict_strict_or_proven_sets():
    from jane_web.jane_v2 import stage1_classifier

    fallback_keys = {
        raw_class
        for raw_class, registry_name in stage1_classifier._CLASS_MAP.items()
        if registry_name == "others"
    }
    contradictory = (
        fallback_keys
        & (
            set(stage1_classifier.PROVEN_CLASSES)
            | set(stage1_classifier.STRICT_CLASSES)
            | set(stage1_classifier._STRICT_KEYWORDS)
        )
    )

    assert contradictory == set()


def test_every_stage1_mapping_value_exists_in_registry_or_is_explicit_fallback():
    from jane_web.jane_v2 import classes, stage1_classifier

    registry = classes.get_registry(refresh=True)
    missing = {
        raw_class: registry_name
        for raw_class, registry_name in stage1_classifier._CLASS_MAP.items()
        if registry_name != "others" and registry_name not in registry
    }

    assert missing == {}


def test_read_messages_registry_entry_points_to_this_handler_and_documents_escalation(
    read_handler,
):
    from jane_web.jane_v2 import classes

    registry = classes.get_registry(refresh=True)
    metadata = registry["read messages"]
    description = str(metadata.get("description") or "").lower()

    assert metadata["pkg_name"] == "read_messages"
    assert metadata["handler"] is read_handler.handle
    assert "stage 3" in (inspect.getdoc(read_handler) or "").lower()
    assert "not this class" in description


def test_read_messages_strict_keywords_are_present_for_classifier_guard():
    from jane_web.jane_v2 import stage1_classifier

    keywords = stage1_classifier._STRICT_KEYWORDS["READ_MESSAGES"]

    assert "READ_MESSAGES" in stage1_classifier.STRICT_CLASSES
    for expected in ("text", "message", "msg", "sms", "inbox"):
        assert expected in keywords


@pytest.mark.asyncio
async def test_positive_read_messages_few_shots_reach_documented_escalation(
    read_handler,
    read_metadata,
):
    positive_prompts = [
        prompt
        for prompt, label in read_metadata.METADATA["few_shot"]
        if str(label).startswith("read messages:")
    ]

    assert positive_prompts
    for prompt in positive_prompts:
        result = await read_handler.handle(prompt)
        assert result is None, prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        "read my messages",
        "your previous reply was slow",
        "explain the classifier",
    ],
)
async def test_handler_return_values_match_documented_dispatch_shapes(read_handler, prompt):
    result = await read_handler.handle(prompt)

    _assert_documented_handler_shape(result)


def test_read_messages_params_schema_keys_are_stable_and_stage3_owned(read_metadata):
    schema = read_metadata.PARAMS_SCHEMA

    assert set(schema) == {"filter_sender", "unread_only", "limit"}
    assert read_metadata.METADATA["params_schema"] is schema
    assert callable(read_metadata.METADATA["escalation_context"])


def test_read_messages_references_in_v2_code_have_registered_mapping():
    from jane_web.jane_v2 import stage1_classifier

    references = []
    for path in (VESSENCE_ROOT / "jane_web" / "jane_v2").rglob("*.py"):
        text = path.read_text()
        if "READ_MESSAGES" in text:
            references.append(path.relative_to(VESSENCE_ROOT).as_posix())

    assert references
    assert "READ_MESSAGES" in stage1_classifier._CLASS_MAP
    assert stage1_classifier._CLASS_MAP["READ_MESSAGES"] == "read messages"
