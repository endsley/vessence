from __future__ import annotations

import ast
import inspect
import re
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = (
    REPO_ROOT / "jane_web" / "jane_v2" / "classes" / "greeting" / "handler.py"
)
SPEC_PATH = REPO_ROOT / "configs" / "v2_3stage_pipeline.md"

from jane_web.jane_v2 import classes as class_registry
from jane_web.jane_v2 import stage1_classifier, stage2_dispatcher
from jane_web.jane_v2.classes.greeting import handler as greeting_handler
from jane_web.jane_v2.classes.greeting import metadata as greeting_metadata


CANNED_SAMPLE_BY_BUCKET = {
    "check_in": "how's it going",
    "hello": "hey",
    "morning": "good morning",
    "afternoon": "good afternoon",
    "evening": "good evening",
    "thanks": "thanks",
}

DESTRUCTIVE_TOKENS = {
    "delete",
    "delete_email",
    "delete_message",
    "delete_messages",
    "drop_table",
    "end_conversation",
    "remove",
    "send_message",
    "sms_send_direct",
    "trash",
}

DB_IMPORT_PREFIXES = (
    "chromadb",
    "jane.config",
    "mysql",
    "psycopg",
    "psycopg2",
    "pymysql",
    "sqlalchemy",
    "sqlite3",
)


@pytest.fixture
def module_source() -> str:
    return MODULE_PATH.read_text()


@pytest.fixture
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


@pytest.fixture
def spec_source() -> str:
    return SPEC_PATH.read_text()


@pytest.fixture
def record_activity_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from jane_web.jane_v2 import models

    calls: list[str] = []
    monkeypatch.setattr(
        models,
        "record_ollama_activity",
        lambda: calls.append("recorded"),
        raising=False,
    )
    return calls


@pytest.fixture
def fake_ollama(monkeypatch: pytest.MonkeyPatch):
    def install(
        *,
        response: str | None = "Hey Chieh.",
        payload: dict | None = None,
        post_exc: Exception | None = None,
        status_exc: Exception | None = None,
    ) -> list[dict]:
        calls: list[dict] = []

        class FakeResponse:
            def raise_for_status(self) -> None:
                if status_exc is not None:
                    raise status_exc

            def json(self) -> dict:
                if payload is not None:
                    return payload
                return {"response": response}

        class FakeAsyncClient:
            def __init__(self, *, timeout):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url: str, json: dict):
                calls.append({"url": url, "json": json, "timeout": self.timeout})
                if post_exc is not None:
                    raise post_exc
                return FakeResponse()

        monkeypatch.setattr(greeting_handler.httpx, "AsyncClient", FakeAsyncClient)
        return calls

    return install


def _block_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    class BombAsyncClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("canned greeting path must not call Ollama")

    monkeypatch.setattr(greeting_handler.httpx, "AsyncClient", BombAsyncClient)


def _force_choice(monkeypatch: pytest.MonkeyPatch, expected: str | None = None) -> None:
    def choose(options):
        if expected is not None:
            assert expected in options
            return expected
        return options[0]

    monkeypatch.setattr(greeting_handler.random, "choice", choose)


def _assert_text_result(result: dict | None) -> None:
    assert isinstance(result, dict)
    assert set(result) == {"text"}
    assert isinstance(result["text"], str)
    assert result["text"].strip()
    assert "[[CLIENT_TOOL:" not in result["text"]
    assert "WRONG_CLASS" not in result["text"].upper()


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _imported_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _call_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _qualified_name(node.func)
            if name:
                names.add(name)
    return names


def _handle_return_nodes(tree: ast.Module) -> list[ast.Return]:
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle":
            return [child for child in ast.walk(node) if isinstance(child, ast.Return)]
    raise AssertionError("handle() not found")


class TestDocumentedBehavior:
    def test_spec_documents_greeting_stage2_contract(self, spec_source: str) -> None:
        assert "Greeting" in spec_source
        assert "qwen2.5:7b" in spec_source
        assert "1-sentence contextual reply" in spec_source
        assert "FIFO" in spec_source
        assert "WRONG_CLASS" in spec_source
        assert "Returning `None` means" in spec_source
        assert "No -> Stage 3" in spec_source or "No \u2192 Stage 3" in spec_source

    def test_module_docstring_documents_greeting_and_escalation_contract(self) -> None:
        doc = inspect.getdoc(greeting_handler)
        assert doc is not None
        assert "Handles basic greetings" in doc
        assert "No Opus needed" in doc
        assert 'Returns {"text": "..."}' in doc
        assert "None to escalate" in doc
        assert "follow-up question or task" in doc

    @pytest.mark.asyncio
    async def test_basic_canned_greeting_returns_text_and_skips_ollama(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _block_ollama(monkeypatch)
        _force_choice(monkeypatch)

        result = await greeting_handler.handle("hey")

        assert result == {"text": greeting_handler._CANNED_REPLIES["hello"][0]}
        _assert_text_result(result)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("prompt", "bucket"),
        [
            ("how's it going?", "check_in"),
            ("How are you", "check_in"),
            ("what's up", "check_in"),
            ("HELLO!!!", "hello"),
            ("yo", "hello"),
            ("good morning", "morning"),
            ("good afternoon", "afternoon"),
            ("good evening", "evening"),
            ("thanks!", "thanks"),
            ("appreciate you", "thanks"),
        ],
    )
    async def test_common_greetings_use_documented_fast_path(
        self,
        prompt: str,
        bucket: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _block_ollama(monkeypatch)
        expected = greeting_handler._CANNED_REPLIES[bucket][-1]
        _force_choice(monkeypatch, expected)

        result = await greeting_handler.handle(prompt)

        assert result == {"text": expected}
        _assert_text_result(result)

    @pytest.mark.asyncio
    async def test_less_templated_greeting_uses_llm_with_context(
        self,
        fake_ollama,
        record_activity_spy: list[str],
    ) -> None:
        calls = fake_ollama(response="Jane: Hey Chieh, good to hear from you.")
        context = "User: Morning.\nJane: Morning."

        result = await greeting_handler.handle("hello there", context=context)

        assert result == {"text": "Hey Chieh, good to hear from you."}
        assert record_activity_spy == ["recorded"]
        assert len(calls) == 1
        body = calls[0]["json"]
        assert calls[0]["url"] == greeting_handler.OLLAMA_URL
        assert calls[0]["timeout"] == greeting_handler.LOCAL_LLM_TIMEOUT
        assert body["model"] == greeting_handler.MODEL
        assert body["stream"] is False
        assert body["think"] is False
        assert body["keep_alive"] == -1
        assert body["options"] == {
            "temperature": 0.7,
            "num_predict": 60,
            "num_ctx": greeting_handler.LOCAL_LLM_NUM_CTX,
        }
        assert "First, confirm" in body["prompt"]
        assert "WRONG_CLASS" in body["prompt"]
        assert f"Recent conversation:\n{context}\n\n" in body["prompt"]
        assert "User: hello there" in body["prompt"]
        assert body["prompt"].rstrip().endswith("Jane:")

    @pytest.mark.asyncio
    async def test_blank_context_is_omitted_from_llm_prompt(self, fake_ollama) -> None:
        calls = fake_ollama(response="Hey Chieh.")

        result = await greeting_handler.handle("hello there", context=" \n\t ")

        assert result == {"text": "Hey Chieh."}
        assert "Recent conversation:" not in calls[0]["json"]["prompt"]

    @pytest.mark.asyncio
    async def test_llm_wrong_class_response_returns_explicit_escalation_signal(
        self, fake_ollama
    ) -> None:
        calls = fake_ollama(response="WRONG_CLASS")

        result = await greeting_handler.handle("how does the greeting handler work?")

        assert result == {"wrong_class": True}
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_llm_empty_response_escalates_to_stage3(self, fake_ollama) -> None:
        calls = fake_ollama(response=" \n\t ")

        result = await greeting_handler.handle("hello there")

        assert result is None
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_llm_http_error_escalates_to_stage3(
        self,
        fake_ollama,
        record_activity_spy: list[str],
    ) -> None:
        calls = fake_ollama(status_exc=RuntimeError("503 from Ollama"))

        result = await greeting_handler.handle("hello there")

        assert result is None
        assert len(calls) == 1
        assert record_activity_spy == []

    @pytest.mark.asyncio
    async def test_llm_transport_error_escalates_to_stage3(
        self,
        fake_ollama,
        record_activity_spy: list[str],
    ) -> None:
        calls = fake_ollama(post_exc=RuntimeError("connection refused"))

        result = await greeting_handler.handle("hello there")

        assert result is None
        assert len(calls) == 1
        assert record_activity_spy == []

    @pytest.mark.asyncio
    async def test_greeting_with_followup_task_escalates_instead_of_answering(
        self, fake_ollama
    ) -> None:
        calls = fake_ollama(response="WRONG_CLASS")

        result = await greeting_handler.handle("hi Jane, set a 5 minute timer")

        assert result == {"wrong_class": True}
        assert len(calls) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "prompt",
        [
            "good morning, set a 5 minute timer",
            "good afternoon, text Sarah that I am late",
            "good evening, what's the weather tomorrow?",
        ],
    )
    async def test_time_of_day_greeting_with_attached_task_does_not_use_canned_reply(
        self,
        prompt: str,
        fake_ollama,
    ) -> None:
        calls = fake_ollama(response="WRONG_CLASS")

        result = await greeting_handler.handle(prompt)

        assert result == {"wrong_class": True}
        assert len(calls) == 1


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_prompt_escalates_without_crashing(self, fake_ollama) -> None:
        calls = fake_ollama(response="")

        result = await greeting_handler.handle("")

        assert result is None
        assert len(calls) == 1
        assert "User: " in calls[0]["json"]["prompt"]

    @pytest.mark.asyncio
    async def test_whitespace_prompt_escalates_without_crashing(self, fake_ollama) -> None:
        calls = fake_ollama(response="")

        result = await greeting_handler.handle(" \n\t ")

        assert result is None
        assert len(calls) == 1
        assert "User: " in calls[0]["json"]["prompt"]

    @pytest.mark.asyncio
    async def test_none_prompt_escalates_without_crashing(self, fake_ollama) -> None:
        fake_ollama(response="")

        result = await greeting_handler.handle(None)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("malformed_prompt", [b"hey", object()])
    async def test_malformed_prompt_escalates_without_crashing(
        self,
        malformed_prompt,
        fake_ollama,
    ) -> None:
        fake_ollama(response="")

        result = await greeting_handler.handle(malformed_prompt)

        assert result is None

    @pytest.mark.asyncio
    async def test_very_long_prompt_uses_llm_confirmation_before_handling(
        self, fake_ollama
    ) -> None:
        long_prompt = "hello there " + " ".join(f"word{i}" for i in range(5000))
        calls = fake_ollama(response="WRONG_CLASS")

        result = await greeting_handler.handle(long_prompt)

        assert result == {"wrong_class": True}
        assert len(calls) == 1
        assert calls[0]["json"]["options"]["num_ctx"] == greeting_handler.LOCAL_LLM_NUM_CTX
        assert long_prompt[:100] in calls[0]["json"]["prompt"]

    @pytest.mark.asyncio
    async def test_very_long_time_of_day_prompt_with_task_does_not_short_circuit(
        self, fake_ollama
    ) -> None:
        long_prompt = (
            "good morning, set a timer for "
            + " ".join(f"minute{i}" for i in range(1000))
        )
        calls = fake_ollama(response="WRONG_CLASS")

        result = await greeting_handler.handle(long_prompt)

        assert result == {"wrong_class": True}
        assert len(calls) == 1


class TestIntegrationPoints:
    def test_module_uses_ollama_httpx_client_and_no_cloud_llm_clients(
        self, module_ast: ast.Module
    ) -> None:
        imports = _imported_modules(module_ast)

        assert "httpx" in imports
        assert "openai" not in imports
        assert "anthropic" not in imports
        assert "google.generativeai" not in imports

    def test_module_has_no_db_query_integration_points(self, module_ast: ast.Module) -> None:
        imports = _imported_modules(module_ast)
        calls = _call_names(module_ast)

        assert not {
            module
            for module in imports
            if module == DB_IMPORT_PREFIXES
            or any(module == prefix or module.startswith(f"{prefix}.") for prefix in DB_IMPORT_PREFIXES)
        }
        assert not any(name.endswith(".execute") for name in calls)
        assert not any(name.endswith(".executemany") for name in calls)
        assert not any(name.endswith(".query") for name in calls)
        assert "get_chroma_client" not in calls
        assert "chromadb.PersistentClient" not in calls

    @pytest.mark.asyncio
    async def test_successful_llm_call_records_ollama_activity_once(
        self,
        fake_ollama,
        record_activity_spy: list[str],
    ) -> None:
        fake_ollama(response="Hey Chieh.")

        result = await greeting_handler.handle("hello there")

        assert result == {"text": "Hey Chieh."}
        assert record_activity_spy == ["recorded"]

    @pytest.mark.asyncio
    async def test_json_payload_missing_response_escalates(self, fake_ollama) -> None:
        calls = fake_ollama(payload={"not_response": "ignored"})

        result = await greeting_handler.handle("hello there")

        assert result is None
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_stage2_dispatcher_invokes_registered_greeting_handler_shape(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _force_choice(monkeypatch)
        _block_ollama(monkeypatch)

        result = await stage2_dispatcher.dispatch("greeting", "hey", min_dist=0.0)

        assert result == {"text": greeting_handler._CANNED_REPLIES["hello"][0]}
        _assert_text_result(result)

    @pytest.mark.asyncio
    async def test_stage2_dispatcher_passes_fifo_context_to_greeting_handler(
        self,
        fake_ollama,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def gate_ok(class_name: str, prompt: str, context: str) -> bool:
            assert class_name == "greeting"
            assert prompt == "hello there"
            assert context == "User: earlier\nJane: earlier reply"
            return True

        monkeypatch.setattr(stage2_dispatcher, "_gate_check", gate_ok)
        calls = fake_ollama(response="Hey Chieh.")

        result = await stage2_dispatcher.dispatch(
            "greeting",
            "hello there",
            context="User: earlier\nJane: earlier reply",
        )

        assert result == {"text": "Hey Chieh."}
        assert "Recent conversation:" in calls[0]["json"]["prompt"]


class TestStructuralInvariants:
    def test_canned_reply_table_has_valid_shape(self) -> None:
        replies = greeting_handler._CANNED_REPLIES

        assert isinstance(replies, dict)
        assert replies
        assert set(replies) == set(CANNED_SAMPLE_BY_BUCKET)
        for bucket, options in replies.items():
            assert isinstance(bucket, str)
            assert bucket.strip() == bucket
            assert isinstance(options, list)
            assert options
            assert len(options) == len(set(options))
            for text in options:
                assert isinstance(text, str)
                assert text.strip() == text
                assert text
                assert "\n" not in text
                assert not text.startswith(("-", "*", "#"))
                assert "[[CLIENT_TOOL:" not in text
                assert "WRONG_CLASS" not in text.upper()

    def test_canned_pattern_buckets_all_exist_and_no_reply_bucket_is_dead(self) -> None:
        replies = greeting_handler._CANNED_REPLIES
        referenced = {bucket for _pattern, bucket in greeting_handler._CANNED_PATTERNS}

        assert referenced == set(replies)

    def test_every_canned_reply_value_is_reachable_from_at_least_one_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for bucket, sample in CANNED_SAMPLE_BY_BUCKET.items():
            for expected in greeting_handler._CANNED_REPLIES[bucket]:
                _force_choice(monkeypatch, expected)

                assert greeting_handler._canned_reply(sample) == expected

    def test_canned_patterns_do_not_reference_missing_reply_keys(self) -> None:
        missing = [
            bucket
            for _pattern, bucket in greeting_handler._CANNED_PATTERNS
            if bucket not in greeting_handler._CANNED_REPLIES
        ]

        assert missing == []

    def test_no_canned_reply_maps_to_destructive_or_escalation_action(self) -> None:
        forbidden = re.compile(
            r"WRONG_CLASS|\[\[CLIENT_TOOL:|sms_send_direct|send_message|"
            r"delete|trash|end conversation|stage 3|opus",
            re.IGNORECASE,
        )

        contradictions = {
            bucket: [text for text in replies if forbidden.search(text)]
            for bucket, replies in greeting_handler._CANNED_REPLIES.items()
        }

        assert {bucket: values for bucket, values in contradictions.items() if values} == {}

    def test_prompt_template_contains_required_wrong_class_confirmation(self) -> None:
        template = greeting_handler._PROMPT_TEMPLATE

        assert "The classifier thinks the user is greeting" in template
        assert "First, confirm" in template
        assert "output ONLY: WRONG_CLASS" in template
        assert "No markdown" in template
        assert "No lists" in template
        assert "{context_block}User: {prompt}" in template
        assert template.rstrip().endswith("Jane:")

    def test_handle_return_literals_are_only_documented_shapes(
        self, module_ast: ast.Module
    ) -> None:
        bad_returns: list[ast.Return] = []
        saw_text_shape = False
        saw_wrong_class_shape = False
        saw_none_shape = False

        for node in _handle_return_nodes(module_ast):
            value = node.value
            if value is None or (isinstance(value, ast.Constant) and value.value is None):
                saw_none_shape = True
                continue
            if isinstance(value, ast.Dict):
                keys = {
                    key.value
                    for key in value.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                }
                if keys == {"text"}:
                    saw_text_shape = True
                    continue
                if keys == {"wrong_class"}:
                    saw_wrong_class_shape = True
                    continue
            bad_returns.append(node)

        assert bad_returns == []
        assert saw_text_shape
        assert saw_wrong_class_shape
        assert saw_none_shape

    def test_greeting_class_name_is_wired_across_stage1_dispatcher_and_registry(self) -> None:
        registry = class_registry.get_registry(refresh=True)

        assert stage1_classifier._CLASS_MAP["GREETING"] == "greeting"
        assert stage2_dispatcher._CLASS_DESCRIPTIONS["greeting"]
        assert greeting_metadata.METADATA["name"] == "greeting"
        assert "greeting" in registry
        assert registry["greeting"]["pkg_name"] == "greeting"
        assert registry["greeting"]["handler"] is greeting_handler.handle

    def test_greeting_metadata_documents_adversarial_non_greeting_inputs(self) -> None:
        description = greeting_metadata.METADATA["description"]

        assert "Adversarial phrasings" in description
        assert "set a 5 minute timer" in description
        assert "what's the weather" in description
        assert "send message" in description
        assert "how does the greeting handler work" in description

    def test_registered_greeting_has_handler_or_explicit_stage3_documentation(
        self, spec_source: str
    ) -> None:
        registry = class_registry.get_registry(refresh=True)
        greeting = registry["greeting"]

        assert greeting["handler"] is not None
        assert "GREETING | greeting" in spec_source
        assert "Yes" in spec_source.split("GREETING | greeting", 1)[1].splitlines()[0]

    def test_module_has_no_destructive_operation_surface(self, module_ast: ast.Module) -> None:
        calls = _call_names(module_ast)
        lowered_calls = {name.lower().replace(".", "_") for name in calls}

        assert lowered_calls.isdisjoint(DESTRUCTIVE_TOKENS)
        assert not any(token in MODULE_PATH.read_text().lower() for token in (
            "[[client_tool:",
            "sms_send_direct",
            "delete(",
            "end_conversation(",
        ))

    def test_if_destructive_surface_is_added_it_must_have_numeric_threshold_guard(
        self, module_source: str
    ) -> None:
        destructive_present = bool(
            re.search(
                r"\b(delete|delete_email|delete_message|delete_messages|"
                r"end_conversation|send_message|sms_send_direct|trash)\s*\(",
                module_source,
                re.IGNORECASE,
            )
        ) or "[[CLIENT_TOOL:contacts.sms_send_direct" in module_source
        threshold_guard_present = bool(
            re.search(r"confidence\s*[>=]=\s*0\.8|0\.80\s*[<]=\s*confidence", module_source)
        )

        assert not destructive_present or threshold_guard_present
