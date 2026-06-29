"""Auto-audit tests for jane_web.jane_v2.classes.greeting.handler."""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


VESSENCE_ROOT = Path(__file__).resolve().parent.parent
if str(VESSENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(VESSENCE_ROOT))

MODULE_PATH = VESSENCE_ROOT / "jane_web/jane_v2/classes/greeting/handler.py"
SPEC_PATH = VESSENCE_ROOT / "configs/v2_3stage_pipeline.md"

handler = importlib.import_module("jane_web.jane_v2.classes.greeting.handler")


BUCKET_EXAMPLES = {
    "check_in": "how's it going?",
    "hello": "hello!",
    "morning": "good morning",
    "afternoon": "good afternoon",
    "evening": "good evening",
    "thanks": "appreciate it",
}


class _FakeOllamaResponse:
    def __init__(self, payload: dict | None = None, *, status_error: Exception | None = None):
        self._payload = payload if payload is not None else {"response": "Hi."}
        self.raise_for_status = MagicMock(side_effect=status_error)

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def install_ollama(monkeypatch):
    """Patch httpx.AsyncClient and return constructed fake clients."""
    clients = []

    def _install(
        response_text: str = "Hi.",
        *,
        payload: dict | None = None,
        post_side_effect: Exception | None = None,
        status_error: Exception | None = None,
    ):
        class _FakeAsyncClient:
            def __init__(self, timeout=None, **kwargs):
                self.timeout = timeout
                self.kwargs = kwargs
                response = _FakeOllamaResponse(
                    payload if payload is not None else {"response": response_text},
                    status_error=status_error,
                )
                self.post = AsyncMock(return_value=response)
                if post_side_effect is not None:
                    self.post.side_effect = post_side_effect
                clients.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(handler.httpx, "AsyncClient", _FakeAsyncClient)
        return clients

    return _install


@pytest.fixture
def unexpected_ollama(monkeypatch):
    """Track unexpected LLM attempts without letting handler's broad except hide them."""
    calls = []

    class _UnexpectedAsyncClient:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise RuntimeError("unexpected Ollama call")

    monkeypatch.setattr(handler.httpx, "AsyncClient", _UnexpectedAsyncClient)
    return calls


def _source_tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text())


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?](?:\s|$)", text.strip()))


class TestDocumentedBehavior:
    def test_spec_documents_greeting_stage2_contract(self):
        spec = SPEC_PATH.read_text()

        assert "**Greeting**" in spec
        assert "qwen2.5:7b" in spec
        assert "Returns 1-sentence warm, casual reply" in spec
        assert "No ack shown" in spec
        assert "Escalates to Stage 3 if LLM call fails" in spec

    def test_module_docstring_documents_simple_greeting_and_escalation_contract(self):
        doc = inspect.getdoc(handler)

        assert doc is not None
        assert "Handles basic greetings" in doc
        assert 'Returns {"text": "..."}' in doc
        assert "None to escalate" in doc
        assert "follow-up question or task" in doc

    @pytest.mark.asyncio
    async def test_basic_canned_greeting_returns_text_and_skips_ollama(
        self, monkeypatch, unexpected_ollama
    ):
        monkeypatch.setattr(handler.random, "choice", lambda choices: choices[0])

        result = await handler.handle("hey")

        assert result == {"text": handler._CANNED_REPLIES["hello"][0]}
        assert unexpected_ollama == []

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
            ("thanks", "thanks"),
            ("thank you", "thanks"),
        ],
    )
    @pytest.mark.asyncio
    async def test_common_greetings_use_documented_fast_path(
        self, prompt, bucket, monkeypatch, unexpected_ollama
    ):
        seen = []

        def choose(choices):
            seen.append(tuple(choices))
            return choices[-1]

        monkeypatch.setattr(handler.random, "choice", choose)

        result = await handler.handle(prompt)

        assert result == {"text": handler._CANNED_REPLIES[bucket][-1]}
        assert seen == [tuple(handler._CANNED_REPLIES[bucket])]
        assert unexpected_ollama == []

    @pytest.mark.parametrize(
        "prompt",
        [
            "hey, set a 5 minute timer",
            "hello what's the weather",
            "hi jane, text Sarah that I am late",
            "how does the greeting handler work",
            "thanks that's all",
        ],
    )
    def test_greeting_prefix_with_real_task_does_not_use_canned_fast_path(self, prompt):
        assert handler._canned_reply(prompt) is None

    @pytest.mark.asyncio
    async def test_llm_reply_returns_documented_text_shape_and_strips_self_label(
        self, install_ollama
    ):
        install_ollama("Jane: Good to hear from you.")

        result = await handler.handle("hey Jane, you awake")

        assert result == {"text": "Good to hear from you."}

    @pytest.mark.asyncio
    async def test_llm_failure_escalates_to_stage3_as_none(self, install_ollama):
        install_ollama(post_side_effect=RuntimeError("ollama down"))

        assert await handler.handle("hey Jane, you around") is None

    @pytest.mark.asyncio
    async def test_llm_empty_response_escalates_to_stage3_as_none(self, install_ollama):
        install_ollama("")

        assert await handler.handle("hey Jane, you around") is None

    @pytest.mark.asyncio
    async def test_wrong_class_follow_up_task_uses_documented_none_escalation(
        self, install_ollama
    ):
        install_ollama("WRONG_CLASS")

        result = await handler.handle("hey, can you set a timer for 5 minutes?")

        assert result is None


class TestEdgeCases:
    @pytest.mark.parametrize("bad_prompt", [None, 123, 4.5, [], {}, object()])
    @pytest.mark.asyncio
    async def test_non_string_input_returns_none_without_llm(self, bad_prompt, unexpected_ollama):
        assert await handler.handle(bad_prompt) is None
        assert unexpected_ollama == []

    @pytest.mark.asyncio
    async def test_empty_input_escalates_without_fabricating_a_greeting(self, install_ollama):
        install_ollama("")

        assert await handler.handle("") is None

    @pytest.mark.asyncio
    async def test_malformed_string_input_is_safely_sent_through_llm_confirmation(
        self, install_ollama
    ):
        clients = install_ollama("Jane: Hey.")

        result = await handler.handle("\x00\x00   ???")

        assert result == {"text": "Hey."}
        assert len(clients) == 1

    @pytest.mark.asyncio
    async def test_very_long_follow_up_task_escalates_when_llm_rejects_class(
        self, install_ollama
    ):
        long_prompt = "hello " + "please write a detailed deployment plan " * 100
        install_ollama("WRONG_CLASS")

        result = await handler.handle(long_prompt)

        assert result is None

    @pytest.mark.asyncio
    async def test_very_long_non_canned_input_still_uses_bounded_generation_options(
        self, install_ollama
    ):
        long_prompt = "hello " + "checking whether you are available " * 120
        clients = install_ollama("I am here.")

        result = await handler.handle(long_prompt)

        assert result == {"text": "I am here."}
        args, kwargs = clients[0].post.await_args
        assert args == (handler.OLLAMA_URL,)
        body = kwargs["json"]
        assert body["options"]["num_predict"] == 60
        assert body["options"]["num_ctx"] == handler.LOCAL_LLM_NUM_CTX


class TestIntegrationPoints:
    @pytest.mark.asyncio
    async def test_llm_call_uses_shared_model_config_context_and_activity_recorder(
        self, monkeypatch, install_ollama
    ):
        from jane_web.jane_v2 import models

        record_activity = MagicMock()
        monkeypatch.setattr(models, "record_ollama_activity", record_activity)
        clients = install_ollama("Jane: Nice to hear from you.")

        result = await handler.handle(
            "hey Jane, are you there",
            context="user: did the deployment finish?\njane: yes",
        )

        assert result == {"text": "Nice to hear from you."}
        assert len(clients) == 1
        assert clients[0].timeout == handler.LOCAL_LLM_TIMEOUT
        clients[0].post.assert_awaited_once()
        args, kwargs = clients[0].post.await_args
        assert args == (handler.OLLAMA_URL,)

        body = kwargs["json"]
        assert body["model"] == handler.MODEL
        assert body["stream"] is False
        assert body["think"] is False
        assert body["keep_alive"] == -1
        assert body["options"] == {
            "temperature": 0.7,
            "num_predict": 60,
            "num_ctx": handler.LOCAL_LLM_NUM_CTX,
        }
        assert "WRONG_CLASS" in body["prompt"]
        assert "Recent conversation:" in body["prompt"]
        assert "did the deployment finish?" in body["prompt"]
        assert "User: hey Jane, are you there" in body["prompt"]
        record_activity.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_llm_json_payload_missing_response_escalates(self, install_ollama):
        install_ollama(payload={"not_response": "ignored"})

        assert await handler.handle("hey Jane, testing") is None

    def test_handler_has_no_database_query_integration_point(self):
        tree = _source_tree()
        forbidden_modules = {
            "chromadb",
            "sqlite3",
            "psycopg",
            "psycopg2",
            "sqlalchemy",
            "pymysql",
            "mysql",
        }
        forbidden_calls = {
            "get_chroma_client",
            "PersistentClient",
            "connect",
            "execute",
            "executemany",
            "query",
            "commit",
            "rollback",
        }
        imports = []
        calls = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_modules:
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in forbidden_modules:
                    imports.append(node.module or "")
            elif isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in forbidden_calls:
                    calls.append(name)

        assert imports == []
        assert calls == []

    @pytest.mark.asyncio
    async def test_greeting_registry_dispatches_to_handler_with_documented_shape(
        self, monkeypatch, unexpected_ollama
    ):
        from jane_web.jane_v2 import classes as class_registry
        from jane_web.jane_v2 import stage2_dispatcher

        monkeypatch.setattr(handler.random, "choice", lambda choices: choices[0])
        registry = class_registry.get_registry(refresh=True)

        assert "greeting" in registry
        assert registry["greeting"]["handler"] is handler.handle
        assert registry["greeting"].get("ack") is None

        result = await stage2_dispatcher.dispatch("greeting", "hello", min_dist=0.0)

        assert result == {"text": handler._CANNED_REPLIES["hello"][0]}
        assert isinstance(result["text"], str)
        assert result["text"].strip()
        assert unexpected_ollama == []


class TestStructuralInvariants:
    def test_canned_pattern_buckets_all_exist(self):
        reply_buckets = set(handler._CANNED_REPLIES)
        pattern_buckets = {bucket for _pattern, bucket in handler._CANNED_PATTERNS}

        assert pattern_buckets <= reply_buckets

    def test_every_canned_reply_bucket_is_reachable_from_a_pattern(self):
        reply_buckets = set(handler._CANNED_REPLIES)
        pattern_buckets = {bucket for _pattern, bucket in handler._CANNED_PATTERNS}

        assert reply_buckets <= pattern_buckets

    @pytest.mark.parametrize("bucket", sorted(BUCKET_EXAMPLES))
    def test_bucket_examples_match_exactly_one_canned_pattern(self, bucket):
        prompt = BUCKET_EXAMPLES[bucket].strip().lower().rstrip(".!?,")
        matches = [
            pattern_bucket
            for pattern, pattern_bucket in handler._CANNED_PATTERNS
            if pattern.match(prompt)
        ]

        assert matches == [bucket]

    @pytest.mark.asyncio
    async def test_every_canned_reply_value_is_reachable_from_an_input(
        self, monkeypatch, unexpected_ollama
    ):
        for bucket, prompt in BUCKET_EXAMPLES.items():
            for target_reply in handler._CANNED_REPLIES[bucket]:

                def choose(choices, expected=target_reply):
                    assert expected in choices
                    return expected

                monkeypatch.setattr(handler.random, "choice", choose)
                assert await handler.handle(prompt) == {"text": target_reply}

        assert unexpected_ollama == []

    def test_canned_replies_do_not_contradict_greeting_handler_contract(self):
        forbidden_route_terms = {
            "WRONG_CLASS",
            "DELEGATE_OPUS",
            "Stage 3",
            "Opus",
            "weather",
            "timer",
            "text ",
            "SMS",
            "email",
            "calendar",
        }
        failures = []

        for bucket, replies in handler._CANNED_REPLIES.items():
            assert isinstance(replies, list)
            assert replies
            for reply in replies:
                if not isinstance(reply, str) or not reply.strip():
                    failures.append((bucket, reply, "reply must be non-empty text"))
                    continue
                if "\n" in reply:
                    failures.append((bucket, reply, "reply must be one line"))
                if _sentence_count(reply) > 1:
                    failures.append((bucket, reply, "reply must be one sentence"))
                if reply.lstrip().startswith(("-", "*", "1.")):
                    failures.append((bucket, reply, "reply must not be markdown/list text"))
                if any(term.lower() in reply.lower() for term in forbidden_route_terms):
                    failures.append((bucket, reply, "reply contains task/routing vocabulary"))
                if bucket == "thanks" and reply.rstrip().endswith("?"):
                    failures.append((bucket, reply, "thanks reply must not ask a follow-up"))
                if bucket == "morning" and "morning" not in reply.lower():
                    failures.append((bucket, reply, "morning bucket should stay morning-specific"))
                if bucket == "afternoon" and "afternoon" not in reply.lower():
                    failures.append((bucket, reply, "afternoon bucket should stay afternoon-specific"))
                if bucket == "evening" and "evening" not in reply.lower():
                    failures.append((bucket, reply, "evening bucket should stay evening-specific"))

        assert failures == []

    def test_stage1_greeting_mapping_references_registered_greeting_class(self):
        from jane_web.jane_v2 import classes as class_registry
        from jane_web.jane_v2 import stage1_classifier

        registry = class_registry.get_registry(refresh=True)

        assert stage1_classifier._CLASS_MAP["GREETING"] == "greeting"
        assert stage1_classifier._CLASS_MAP["GREETING"] in registry
        assert callable(registry["greeting"]["handler"])

    def test_no_destructive_operation_is_reachable_from_greeting_handler(self):
        tree = _source_tree()
        destructive_calls = {
            "delete",
            "unlink",
            "rmdir",
            "rmtree",
            "remove",
            "replace",
            "rename",
            "send_message",
            "sms_send_direct",
            "end_conversation",
            "truncate",
            "drop",
        }
        found = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in destructive_calls:
                    found.append(name)

        assert found == []

    def test_no_canned_pattern_shadows_more_specific_task_phrases(self):
        task_like_prompts = [
            "hi set a timer",
            "hello add milk to my shopping list",
            "hey text Sarah hello",
            "good morning what is the weather",
            "thanks now read my email",
            "how are you can you check my calendar",
        ]

        assert [p for p in task_like_prompts if handler._canned_reply(p) is not None] == []

