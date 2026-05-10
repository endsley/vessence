"""Comprehensive tests for jane_web.jane_v2.classes.greeting.handler"""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from jane_web.jane_v2.classes.greeting.handler import (
    _CANNED_PATTERNS,
    _CANNED_REPLIES,
    _canned_reply,
    _PROMPT_TEMPLATE,
    handle,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _seed_random():
    random.seed(42)


def _make_ollama_client(response_text: str, status_code: int = 200):
    """Build a fake async httpx client that returns a controlled Ollama response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"response": response_text}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp,
        )

    client = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.fixture
def mock_ollama():
    """Patch httpx.AsyncClient to return a controlled Ollama response."""
    with patch("jane_web.jane_v2.classes.greeting.handler.httpx.AsyncClient") as mock_cls:
        mock_cls._factory = _make_ollama_client
        mock_cls.side_effect = lambda **kw: _make_ollama_client("Hey! What's on your mind?")
        yield mock_cls


# ---------------------------------------------------------------------------
# 1. STRUCTURAL INVARIANTS
# ---------------------------------------------------------------------------

class TestStructuralInvariants:
    """Catch mapping/lookup inconsistencies between _CANNED_PATTERNS and _CANNED_REPLIES."""

    def test_every_pattern_bucket_exists_in_replies(self):
        """Every bucket name referenced in _CANNED_PATTERNS must exist in _CANNED_REPLIES."""
        for pattern, bucket in _CANNED_PATTERNS:
            assert bucket in _CANNED_REPLIES, (
                f"Pattern {pattern.pattern!r} references bucket {bucket!r} "
                f"which is missing from _CANNED_REPLIES"
            )

    def test_every_reply_bucket_is_reachable(self):
        """Every bucket in _CANNED_REPLIES must be referenced by at least one pattern."""
        referenced_buckets = {bucket for _, bucket in _CANNED_PATTERNS}
        for bucket in _CANNED_REPLIES:
            assert bucket in referenced_buckets, (
                f"Bucket {bucket!r} in _CANNED_REPLIES is dead — "
                f"no pattern in _CANNED_PATTERNS routes to it"
            )

    def test_no_empty_reply_lists(self):
        """Every bucket must have at least one reply."""
        for bucket, replies in _CANNED_REPLIES.items():
            assert len(replies) > 0, f"Bucket {bucket!r} has an empty reply list"

    def test_all_replies_are_nonempty_strings(self):
        """Every canned reply must be a non-empty string."""
        for bucket, replies in _CANNED_REPLIES.items():
            for i, reply in enumerate(replies):
                assert isinstance(reply, str) and reply.strip(), (
                    f"Bucket {bucket!r}[{i}] is empty or not a string: {reply!r}"
                )

    def test_all_patterns_are_compiled_regex(self):
        """Every pattern must be a compiled regex."""
        import re
        for pattern, bucket in _CANNED_PATTERNS:
            assert isinstance(pattern, re.Pattern), (
                f"Pattern for bucket {bucket!r} is not compiled: {type(pattern)}"
            )

    def test_prompt_template_has_required_placeholders(self):
        """The LLM prompt template must contain {prompt} and {context_block}."""
        assert "{prompt}" in _PROMPT_TEMPLATE
        assert "{context_block}" in _PROMPT_TEMPLATE

    def test_prompt_template_contains_wrong_class_instruction(self):
        """The template must instruct the LLM to output WRONG_CLASS for non-greetings."""
        assert "WRONG_CLASS" in _PROMPT_TEMPLATE

    @pytest.mark.asyncio
    async def test_handler_return_shape_canned(self):
        """Canned replies must return dict with 'text' key."""
        result = await handle("hey")
        assert result is not None
        assert "text" in result
        assert isinstance(result["text"], str)


# ---------------------------------------------------------------------------
# 2. BEHAVIORAL TESTS — canned reply path
# ---------------------------------------------------------------------------

class TestCannedReplies:
    """Verify that known greeting patterns return canned replies without hitting the LLM."""

    @pytest.mark.parametrize("greeting", [
        "hi", "hey", "hello", "yo", "howdy", "heya", "hiya",
        "hi!", "hey!", "hello!", "Hi", "HEY", "HELLO",
        "hiii", "heyyy",
    ])
    def test_bare_hellos(self, greeting):
        reply = _canned_reply(greeting)
        assert reply is not None
        assert reply in _CANNED_REPLIES["hello"]

    @pytest.mark.parametrize("greeting", [
        "how's it going", "how are you", "how you doing",
        "what's up", "whats up", "sup", "you good", "you there",
        "how's it going?", "how are you?",
        "How Are You", "HOW'S IT GOING",
        "how's things", "how's everything", "how you holding up",
    ])
    def test_check_in(self, greeting):
        reply = _canned_reply(greeting)
        assert reply is not None
        assert reply in _CANNED_REPLIES["check_in"]

    @pytest.mark.parametrize("greeting", [
        "good morning", "Good Morning", "good morning!",
    ])
    def test_morning(self, greeting):
        reply = _canned_reply(greeting)
        assert reply is not None
        assert reply in _CANNED_REPLIES["morning"]

    @pytest.mark.parametrize("greeting", [
        "good afternoon", "Good Afternoon",
    ])
    def test_afternoon(self, greeting):
        reply = _canned_reply(greeting)
        assert reply is not None
        assert reply in _CANNED_REPLIES["afternoon"]

    @pytest.mark.parametrize("greeting", [
        "good evening", "Good Evening",
    ])
    def test_evening(self, greeting):
        reply = _canned_reply(greeting)
        assert reply is not None
        assert reply in _CANNED_REPLIES["evening"]

    @pytest.mark.parametrize("greeting", [
        "thanks", "thank you", "thx", "ty",
        "appreciate it", "appreciate you",
        "Thanks!", "THANK YOU",
    ])
    def test_thanks(self, greeting):
        reply = _canned_reply(greeting)
        assert reply is not None
        assert reply in _CANNED_REPLIES["thanks"]


# ---------------------------------------------------------------------------
# 3. EDGE CASES
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_string(self):
        assert _canned_reply("") is None

    def test_none_input(self):
        assert _canned_reply(None) is None

    def test_whitespace_only(self):
        assert _canned_reply("   ") is None

    def test_very_long_input(self):
        long_input = "hey " * 5000
        assert _canned_reply(long_input) is None

    def test_greeting_with_followup_question(self):
        """A greeting followed by a question should NOT match canned patterns."""
        assert _canned_reply("hey can you help me with something") is None

    def test_greeting_embedded_in_sentence(self):
        assert _canned_reply("I just wanted to say hello to everyone") is None

    def test_partial_match_not_greeting(self):
        assert _canned_reply("how's it going to end") is None

    def test_good_morning_with_name(self):
        """'good morning Jane' should still match because the pattern uses \\b not $."""
        reply = _canned_reply("good morning Jane")
        assert reply is not None
        assert reply in _CANNED_REPLIES["morning"]

    def test_numeric_input(self):
        assert _canned_reply("12345") is None

    def test_special_characters(self):
        assert _canned_reply("@#$%^&*()") is None

    def test_trailing_punctuation_stripped(self):
        """Trailing punctuation should be stripped before matching."""
        reply = _canned_reply("hey!")
        assert reply is not None
        assert reply in _CANNED_REPLIES["hello"]

    @pytest.mark.asyncio
    async def test_handle_empty_string(self, mock_ollama):
        result = await handle("")
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handle_whitespace_only(self, mock_ollama):
        result = await handle("   ")
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# 4. BEHAVIORAL TESTS — LLM path
# ---------------------------------------------------------------------------

class TestLLMPath:

    @pytest.mark.asyncio
    async def test_non_canned_greeting_hits_llm(self, mock_ollama):
        """A greeting that doesn't match canned patterns should call Ollama."""
        client = mock_ollama._factory("What's good! Nice to hear from you.")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("what's crackin")
        assert result is not None
        assert "text" in result
        assert result["text"] == "What's good! Nice to hear from you."
        client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrong_class_escalates(self, mock_ollama):
        """LLM returning WRONG_CLASS should escalate (return wrong_class dict)."""
        client = mock_ollama._factory("WRONG_CLASS")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("deploy the app to production")
        assert result is not None
        assert result.get("wrong_class") is True
        assert "text" not in result

    @pytest.mark.asyncio
    async def test_wrong_class_case_insensitive(self, mock_ollama):
        """WRONG_CLASS detection should be case-insensitive."""
        client = mock_ollama._factory("wrong_class")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("what time is my meeting")
        assert result is not None
        assert result.get("wrong_class") is True

    @pytest.mark.asyncio
    async def test_wrong_class_embedded_in_text(self, mock_ollama):
        """WRONG_CLASS anywhere in the response should trigger escalation."""
        client = mock_ollama._factory("I think this is WRONG_CLASS actually.")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("schedule a meeting")
        assert result is not None
        assert result.get("wrong_class") is True

    @pytest.mark.asyncio
    async def test_llm_empty_response_returns_none(self, mock_ollama):
        """Empty LLM response should return None (escalate)."""
        client = mock_ollama._factory("")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("greetings earthling")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_whitespace_response_returns_none(self, mock_ollama):
        """Whitespace-only LLM response should return None (escalate)."""
        client = mock_ollama._factory("   \n  ")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("greetings earthling")
        assert result is None

    @pytest.mark.asyncio
    async def test_jane_prefix_stripped(self, mock_ollama):
        """LLM output starting with 'Jane:' should have the prefix stripped."""
        client = mock_ollama._factory("Jane: Hey there, good to see you!")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("long time no see")
        assert result is not None
        assert result["text"] == "Hey there, good to see you!"
        assert not result["text"].startswith("Jane:")

    @pytest.mark.asyncio
    async def test_jane_prefix_case_insensitive(self, mock_ollama):
        """'jane:' prefix stripping should be case-insensitive."""
        client = mock_ollama._factory("jane: What's going on?")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("yo yo yo")
        assert result is not None
        assert result["text"] == "What's going on?"

    @pytest.mark.asyncio
    async def test_context_included_in_prompt(self, mock_ollama):
        """When context is provided, it should appear in the LLM prompt."""
        client = mock_ollama._factory("Welcome back!")
        mock_ollama.side_effect = lambda **kw: client

        await handle("hey again", context="User: I was working on the deploy\nJane: Sure, let me check.")

        call_args = client.post.call_args
        body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        prompt_text = body["prompt"]
        assert "Recent conversation:" in prompt_text
        assert "working on the deploy" in prompt_text

    @pytest.mark.asyncio
    async def test_empty_context_not_included(self, mock_ollama):
        """Empty or whitespace context should not add a context block."""
        client = mock_ollama._factory("Hey!")
        mock_ollama.side_effect = lambda **kw: client

        await handle("hey there friend", context="   ")

        call_args = client.post.call_args
        body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        prompt_text = body["prompt"]
        assert "Recent conversation:" not in prompt_text


# ---------------------------------------------------------------------------
# 5. INTEGRATION POINTS — error handling & side effects
# ---------------------------------------------------------------------------

class TestIntegrationPoints:

    @pytest.mark.asyncio
    async def test_llm_http_error_returns_none(self, mock_ollama):
        """HTTP errors from Ollama should return None (escalate to Stage 3)."""
        client = mock_ollama._factory("", status_code=500)
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("howdy partner")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_timeout_returns_none(self, mock_ollama):
        """Timeout from Ollama should return None (escalate)."""
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("hey what's happening")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_connection_error_returns_none(self, mock_ollama):
        """Connection errors should return None (escalate)."""
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("what's the good word")
        assert result is None

    @pytest.mark.asyncio
    async def test_record_ollama_activity_called(self, mock_ollama):
        """Successful LLM calls should invoke record_ollama_activity."""
        client = mock_ollama._factory("Hey!")
        mock_ollama.side_effect = lambda **kw: client

        with patch("jane_web.jane_v2.models.record_ollama_activity") as mock_record:
            result = await handle("what's good")
            assert result is not None
            mock_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_ollama_failure_does_not_break_handler(self, mock_ollama):
        """If record_ollama_activity raises, the handler should still return normally."""
        client = mock_ollama._factory("All good!")
        mock_ollama.side_effect = lambda **kw: client

        with patch(
            "jane_web.jane_v2.models.record_ollama_activity",
            side_effect=RuntimeError("tracking broken"),
        ):
            result = await handle("what's crackin")
            assert result is not None
            assert result["text"] == "All good!"

    @pytest.mark.asyncio
    async def test_canned_reply_skips_llm_entirely(self, mock_ollama):
        """Canned replies should never hit the LLM."""
        result = await handle("hey")
        assert result is not None
        assert "text" in result
        # The mock's post should NOT have been called
        # (mock_ollama returns a factory, but handle() won't even reach httpx)
        # We verify by checking the result matches a canned reply
        assert result["text"] in _CANNED_REPLIES["hello"]

    @pytest.mark.asyncio
    async def test_ollama_request_body_shape(self, mock_ollama):
        """Verify the shape of the request body sent to Ollama."""
        client = mock_ollama._factory("Hey!")
        mock_ollama.side_effect = lambda **kw: client

        await handle("what's happening my friend")

        call_args = client.post.call_args
        body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]

        assert "model" in body
        assert "prompt" in body
        assert body["stream"] is False
        assert "options" in body
        assert "temperature" in body["options"]
        assert "num_predict" in body["options"]
        assert "num_ctx" in body["options"]
        assert body["options"]["num_predict"] == 60

    @pytest.mark.asyncio
    async def test_ollama_url_used(self, mock_ollama):
        """Verify the handler posts to the configured OLLAMA_URL."""
        from jane_web.jane_v2.models import OLLAMA_URL

        client = mock_ollama._factory("Hey!")
        mock_ollama.side_effect = lambda **kw: client

        await handle("what's happening")

        call_args = client.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url")
        assert url == OLLAMA_URL


# ---------------------------------------------------------------------------
# 6. PATTERN COVERAGE — ensure every bucket is reachable via at least one input
# ---------------------------------------------------------------------------

class TestPatternCoverage:
    """Verify that every _CANNED_REPLIES bucket can be reached by real user input."""

    _BUCKET_EXAMPLES = {
        "check_in": "how's it going",
        "hello": "hey",
        "morning": "good morning",
        "afternoon": "good afternoon",
        "evening": "good evening",
        "thanks": "thanks",
    }

    @pytest.mark.parametrize("bucket,example", list(_BUCKET_EXAMPLES.items()))
    def test_bucket_reachable(self, bucket, example):
        reply = _canned_reply(example)
        assert reply is not None, f"Bucket {bucket!r} not reachable via {example!r}"
        assert reply in _CANNED_REPLIES[bucket]


# ---------------------------------------------------------------------------
# 7. RETURN SHAPE CONSISTENCY
# ---------------------------------------------------------------------------

class TestReturnShapes:
    """Every code path must return either None, {"text": str}, or {"wrong_class": True}."""

    @pytest.mark.asyncio
    async def test_canned_return_shape(self):
        result = await handle("hey")
        assert isinstance(result, dict)
        assert "text" in result
        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_llm_success_return_shape(self, mock_ollama):
        client = mock_ollama._factory("Yo! What's up?")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("greetings friend")
        assert isinstance(result, dict)
        assert "text" in result
        assert isinstance(result["text"], str)

    @pytest.mark.asyncio
    async def test_wrong_class_return_shape(self, mock_ollama):
        client = mock_ollama._factory("WRONG_CLASS")
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("run the deploy script")
        assert isinstance(result, dict)
        assert result == {"wrong_class": True}

    @pytest.mark.asyncio
    async def test_failure_return_shape(self, mock_ollama):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=Exception("boom"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_ollama.side_effect = lambda **kw: client

        result = await handle("ahoy there")
        assert result is None
