from __future__ import annotations

import ast
import builtins
import inspect
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = (
    REPO_ROOT / "jane_web" / "jane_v2" / "classes" / "read_messages" / "handler.py"
)
METADATA_PATH = MODULE_PATH.with_name("metadata.py")

from intent_classifier.v2.classes import read_messages as classifier_read_messages
from jane_web.jane_v2 import classes as class_registry
from jane_web.jane_v2 import stage2_dispatcher
from jane_web.jane_v2.classes.read_messages import handler as read_handler
from jane_web.jane_v2.classes.read_messages import metadata as read_metadata


DB_AND_LLM_IMPORT_ROOTS = {
    "anthropic",
    "google.generativeai",
    "httpx",
    "mysql",
    "openai",
    "psycopg",
    "psycopg2",
    "pymysql",
    "sqlite3",
    "sqlalchemy",
}

DESTRUCTIVE_NAMES = {
    "delete",
    "delete_email",
    "delete_message",
    "delete_messages",
    "end_conversation",
    "remove",
    "send_message",
    "sms_send",
    "sms_send_direct",
    "trash",
}

DOCUMENTED_NO_HANDLER_CLASSES = {
    "delegate opus",
    "delete email",
    "end conversation",
    "others",
    "read email",
    "send email",
    "unclear",
}

FALLBACK_CLASSES = {"delegate opus", "others", "unclear"}


@pytest.fixture
def module_source() -> str:
    return MODULE_PATH.read_text()


@pytest.fixture
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


@pytest.fixture
def metadata_source() -> str:
    return METADATA_PATH.read_text()


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            roots.add(parts[0] if len(parts) == 1 else ".".join(parts[:2]))
    return roots


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id.lower())
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr.lower())
    return names


def _module_level_dict_tables(tree: ast.Module) -> dict[str, ast.Dict]:
    tables: dict[str, ast.Dict] = {}
    markers = ("MAP", "MAPPING", "LOOKUP", "REGISTRY", "TABLE", "DISPATCH")
    for node in tree.body:
        value: ast.AST | None = None
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if not isinstance(value, ast.Dict):
            continue
        for target in targets:
            if isinstance(target, ast.Name) and any(m in target.id.upper() for m in markers):
                tables[target.id] = value
    return tables


def _parse_few_shot_label(label: str) -> tuple[str, str]:
    class_name, sep, confidence = label.partition(":")
    assert sep == ":", f"few-shot label lacks confidence delimiter: {label!r}"
    return class_name.strip(), confidence.strip()


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _FakeCursor:
        self.executed.append((sql, params))
        return _FakeCursor(self.rows)


def _install_fake_database(
    monkeypatch: pytest.MonkeyPatch,
    connection: _FakeConnection,
) -> types.ModuleType:
    database = types.ModuleType("database")
    database.get_db = lambda: connection
    monkeypatch.setitem(sys.modules, "database", database)
    return database


class TestDocumentedBehavior:
    def test_module_docstring_documents_stage3_escalation_contract(
        self, module_source: str
    ) -> None:
        doc = ast.get_docstring(ast.parse(module_source))

        assert doc is not None
        assert "always escalates to Stage 3" in doc
        assert "thin guard" in doc
        assert "meta / architecture phrases" in doc
        assert "returns None to escalate" in doc
        assert "_escalation_context()" in doc

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "prompt",
        [
            "read my messages",
            "any new texts?",
            "what did Kathia text me?",
            "do I have any unread messages",
            "check my SMS inbox",
        ],
    )
    async def test_inbox_read_requests_return_none_to_escalate(self, prompt: str) -> None:
        result = await read_handler.handle(prompt)

        assert result is None

    @pytest.mark.asyncio
    async def test_context_and_params_are_accepted_but_do_not_answer_locally(self) -> None:
        result = await read_handler.handle(
            "read the last three text messages",
            context="Earlier topic was calendar.",
            params={"filter_sender": None, "unread_only": False, "limit": 3},
        )

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("word", read_handler._ARCH_WORDS)
    async def test_architecture_words_are_blocked_as_wrong_class(self, word: str) -> None:
        result = await read_handler.handle(f"explain the {word} for read messages")

        assert result == {"wrong_class": True}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("phrase", read_handler._META_PHRASES)
    async def test_meta_self_reference_phrases_are_blocked_as_wrong_class(
        self, phrase: str
    ) -> None:
        result = await read_handler.handle(f"{phrase}?")

        assert result == {"wrong_class": True}

    @pytest.mark.asyncio
    async def test_guards_are_case_insensitive(self) -> None:
        assert await read_handler.handle("WHY DID YOU take so long?") == {
            "wrong_class": True
        }
        assert await read_handler.handle("How does the CLASSIFIER work?") == {
            "wrong_class": True
        }

    @pytest.mark.asyncio
    async def test_meta_guard_logs_wrong_class_reason(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("INFO", logger=read_handler.logger.name)

        result = await read_handler.handle("your last reply took so long")

        assert result == {"wrong_class": True}
        assert "meta/self-reference phrase" in caplog.text
        assert "wrong_class" in caplog.text

    @pytest.mark.asyncio
    async def test_normal_escalation_logs_stage3_design_reason(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("INFO", logger=read_handler.logger.name)

        result = await read_handler.handle("read my messages")

        assert result is None
        assert "escalating to Stage 3 by design" in caplog.text


class TestEdgeCases:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
    async def test_empty_and_whitespace_prompts_escalate(self, prompt: str) -> None:
        assert await read_handler.handle(prompt) is None

    @pytest.mark.asyncio
    async def test_very_long_prompt_is_linear_guard_only_and_escalates(self) -> None:
        prompt = "read my messages " + "please " * 50000

        result = await read_handler.handle(prompt)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("prompt", "expected_exception"),
        [
            (None, AttributeError),
            (123, AttributeError),
            (["read", "messages"], AttributeError),
            ({"prompt": "read messages"}, AttributeError),
            (b"read my messages", TypeError),
        ],
    )
    async def test_non_string_prompts_are_rejected_by_lowercase_guard(
        self, prompt: Any, expected_exception: type[Exception]
    ) -> None:
        with pytest.raises(expected_exception):
            await read_handler.handle(prompt)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("context", [None, 1, [], {"recent": "turn"}])
    async def test_malformed_context_is_ignored_because_handler_only_reads_prompt(
        self, context: Any
    ) -> None:
        result = await read_handler.handle("read my texts", context=context)  # type: ignore[arg-type]

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("params", [None, [], "bad", {"limit": "not an int"}])
    async def test_malformed_params_are_ignored_because_handler_only_reads_prompt(
        self, params: Any
    ) -> None:
        result = await read_handler.handle("read my texts", params=params)  # type: ignore[arg-type]

        assert result is None


class TestIntegrationPoints:
    def test_handler_module_has_no_direct_database_or_llm_imports(
        self, module_ast: ast.Module
    ) -> None:
        assert _import_roots(module_ast).isdisjoint(DB_AND_LLM_IMPORT_ROOTS)

    def test_handler_module_has_no_direct_database_or_llm_calls(
        self, module_ast: ast.Module
    ) -> None:
        banned_calls = {
            "asyncclient",
            "chat",
            "completion",
            "connect",
            "cursor",
            "execute",
            "get_db",
            "openai",
            "post",
            "query",
        }

        assert _called_names(module_ast).isdisjoint(banned_calls)

    def test_metadata_escalation_context_queries_recent_synced_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [
            {
                "sender": "Kathia",
                "body": "Can you call when you are free?",
                "timestamp_ms": 1710000000000,
                "is_contact": 1,
                "msg_type": "sms",
            },
            {
                "sender": f"Me {chr(0x2192)} Lee",
                "body": "On my way",
                "timestamp_ms": 1710000060000,
                "is_contact": 1,
                "msg_type": "sms",
            },
        ]
        conn = _FakeConnection(rows)
        _install_fake_database(monkeypatch, conn)

        context = read_metadata._escalation_context()

        assert len(conn.executed) == 1
        sql, params = conn.executed[0]
        assert params == ()
        assert "FROM synced_messages" in sql
        assert "ORDER BY timestamp_ms DESC LIMIT 20" in sql
        assert "Recent synced messages" in context
        assert "RECEIVED from Kathia" in context
        assert "SENT by user to Lee" in context
        assert "Classify each as important" in context
        assert "Quote contact messages verbatim" in context

    def test_metadata_escalation_context_reports_empty_database(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        conn = _FakeConnection([])
        _install_fake_database(monkeypatch, conn)

        assert read_metadata._escalation_context() == "No synced messages in the database yet."

    def test_metadata_escalation_context_reports_database_query_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class BrokenConnection:
            def __enter__(self) -> "BrokenConnection":
                return self

            def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                return False

            def execute(self, *_args: Any, **_kwargs: Any) -> Any:
                raise RuntimeError("boom")

        database = types.ModuleType("database")
        database.get_db = lambda: BrokenConnection()
        monkeypatch.setitem(sys.modules, "database", database)

        assert read_metadata._escalation_context() == "Message query failed: boom"

    def test_metadata_escalation_context_reports_database_import_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delitem(sys.modules, "database", raising=False)
        original_import = builtins.__import__

        def blocked_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "database":
                raise ImportError("database unavailable in test")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked_import)

        result = read_metadata._escalation_context()

        assert result == "Message database unavailable: database unavailable in test"

    @pytest.mark.asyncio
    async def test_stage2_dispatcher_uses_mocked_llm_gate_then_escalates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gate = AsyncMock(return_value=True)
        monkeypatch.setattr(stage2_dispatcher, "_gate_check", gate)

        result = await stage2_dispatcher.dispatch(
            "read messages",
            "read my messages",
            context="recent turn context",
            min_dist=1.0,
        )

        assert result is None
        gate.assert_awaited_once_with(
            "read messages", "read my messages", "recent turn context"
        )

    @pytest.mark.asyncio
    async def test_stage2_dispatcher_wrong_class_signal_stays_non_terminal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gate = AsyncMock(return_value=True)
        monkeypatch.setattr(stage2_dispatcher, "_gate_check", gate)
        started_threads: list[Any] = []

        class FakeThread:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.args = args
                self.kwargs = kwargs

            def start(self) -> None:
                started_threads.append(self)

        monkeypatch.setattr(stage2_dispatcher.threading, "Thread", FakeThread)

        result = await stage2_dispatcher.dispatch(
            "read messages",
            "how does the read messages handler work?",
            min_dist=1.0,
        )

        assert result is None
        gate.assert_awaited_once_with(
            "read messages", "how does the read messages handler work?", ""
        )
        assert len(started_threads) == 1
        thread = started_threads[0]
        assert thread.kwargs["target"] is stage2_dispatcher._self_correct_classification
        assert thread.kwargs["args"] == (
            "how does the read messages handler work?",
            "read messages",
        )
        assert thread.kwargs["daemon"] is True


class TestStructuralInvariants:
    def test_guard_tables_are_tuples_with_unique_lowercase_nonempty_entries(self) -> None:
        for table in (read_handler._ARCH_WORDS, read_handler._META_PHRASES):
            assert isinstance(table, tuple)
            assert table
            assert len(table) == len(set(table))
            for entry in table:
                assert isinstance(entry, str)
                assert entry.strip() == entry
                assert entry
                assert entry == entry.lower()

    def test_architecture_guard_does_not_include_core_sms_request_terms(self) -> None:
        core_sms_terms = {
            "check",
            "inbox",
            "message",
            "messages",
            "read",
            "sms",
            "text",
            "texts",
            "unread",
        }

        assert core_sms_terms.isdisjoint(set(read_handler._ARCH_WORDS))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("word", read_handler._ARCH_WORDS)
    async def test_every_architecture_guard_entry_is_reachable(self, word: str) -> None:
        result = await read_handler.handle(f"why does the {word} work this way")

        assert result == {"wrong_class": True}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("phrase", read_handler._META_PHRASES)
    async def test_every_meta_guard_entry_is_reachable(self, phrase: str) -> None:
        result = await read_handler.handle(f"{phrase} in our conversation")

        assert result == {"wrong_class": True}

    def test_module_has_no_mapping_lookup_or_dispatch_table(self, module_ast: ast.Module) -> None:
        assert _module_level_dict_tables(module_ast) == {}

    def test_metadata_few_shot_targets_exist_in_runtime_registry(self) -> None:
        registry = class_registry.get_registry(refresh=True)

        for _prompt, label in read_metadata.METADATA["few_shot"]:
            class_name, confidence = _parse_few_shot_label(label)
            assert class_name in registry
            assert confidence in {"High", "Low"}

    def test_metadata_few_shots_do_not_mark_fallback_classes_high_confidence(self) -> None:
        for _prompt, label in read_metadata.METADATA["few_shot"]:
            class_name, confidence = _parse_few_shot_label(label)
            assert not (class_name in FALLBACK_CLASSES and confidence == "High")

    def test_classifier_class_name_matches_runtime_registry_key(self) -> None:
        registry_name = classifier_read_messages.CLASS_NAME.lower().replace("_", " ")

        assert registry_name == read_metadata.METADATA["name"]
        assert registry_name in class_registry.get_registry(refresh=True)

    def test_read_messages_registry_entry_has_documented_escalating_handler(self) -> None:
        registry = class_registry.get_registry(refresh=True)
        meta = registry["read messages"]

        assert meta["pkg_name"] == "read_messages"
        assert meta["handler"] is read_handler.handle
        assert meta["escalation_context"] is read_metadata._escalation_context
        assert "escalate" in (read_handler.__doc__ or "").lower()

    def test_classes_without_handlers_are_explicitly_known_stage3_or_special_cases(self) -> None:
        registry = class_registry.get_registry(refresh=True)
        classes_without_handlers = {
            name for name, meta in registry.items() if meta.get("handler") is None
        }

        assert classes_without_handlers <= DOCUMENTED_NO_HANDLER_CLASSES

    @pytest.mark.asyncio
    async def test_read_messages_handler_return_shapes_match_dispatcher_contract(self) -> None:
        normal = await read_handler.handle("read my messages")
        wrong_class = await read_handler.handle("how does the handler work?")

        assert normal is None
        assert wrong_class == {"wrong_class": True}
        assert set(wrong_class) == {"wrong_class"}

    def test_handle_signature_exposes_only_non_destructive_inputs(self) -> None:
        signature = inspect.signature(read_handler.handle)

        assert list(signature.parameters) == ["prompt", "context", "params"]
        assert signature.parameters["context"].default == ""
        assert signature.parameters["params"].default is None
        assert "confidence" not in signature.parameters

    def test_module_contains_no_destructive_tool_markers_or_calls(
        self, module_source: str, module_ast: ast.Module
    ) -> None:
        lowered_source = module_source.lower()

        assert "[[client_tool:" not in lowered_source
        assert _called_names(module_ast).isdisjoint(DESTRUCTIVE_NAMES)

    def test_module_has_no_destructive_operations_requiring_confidence_threshold(
        self, module_ast: ast.Module
    ) -> None:
        function_names = {
            node.name.lower()
            for node in ast.walk(module_ast)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        destructive_functions = function_names & DESTRUCTIVE_NAMES

        assert destructive_functions == set()
        assert not any(
            parameter.arg == "confidence"
            for node in ast.walk(module_ast)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for parameter in list(node.args.args) + list(node.args.kwonlyargs)
        )

    def test_module_has_no_class_registry_or_handler_dispatch(self, module_ast: ast.Module) -> None:
        class_defs = [node.name for node in module_ast.body if isinstance(node, ast.ClassDef)]
        dispatch_functions = [
            node.name
            for node in module_ast.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name not in {"handle"}
            and any(token in node.name.lower() for token in ("dispatch", "route", "registry"))
        ]

        assert class_defs == []
        assert dispatch_functions == []
