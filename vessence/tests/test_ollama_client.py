import pytest

from jane_web.jane_v2 import models
from jane_web.jane_v2.ollama_client import post_local_llm_response, post_ollama_response


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raise_called = False

    def raise_for_status(self):
        self.raise_called = True

    def json(self):
        return self.payload


class FakeClient:
    instances = []

    def __init__(self, *, timeout):
        self.timeout = timeout
        self.posts = []
        self.response = FakeResponse({"response": "  hello  "})
        FakeClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        self.posts.append((url, json))
        return self.response


@pytest.mark.asyncio
async def test_post_ollama_response_posts_payload_strips_response_and_records_activity():
    calls = []

    result = await post_ollama_response(
        "http://ollama.test",
        {"prompt": "hello"},
        timeout=12,
        client_factory=FakeClient,
        activity_recorder=lambda: calls.append("recorded"),
    )

    client = FakeClient.instances[-1]
    assert result == "hello"
    assert client.timeout == 12
    assert client.posts == [("http://ollama.test", {"prompt": "hello"})]
    assert client.response.raise_called is True
    assert calls == ["recorded"]


@pytest.mark.asyncio
async def test_post_local_llm_response_uses_local_model_settings(monkeypatch):
    monkeypatch.setattr(models, "LOCAL_LLM", "qwen-test")
    monkeypatch.setattr(models, "LOCAL_LLM_NUM_CTX", 4096)
    monkeypatch.setattr(models, "LOCAL_LLM_TIMEOUT", 17)
    monkeypatch.setattr(models, "OLLAMA_KEEP_ALIVE", "9m")
    monkeypatch.setattr(models, "OLLAMA_URL", "http://ollama.local/api/generate")
    captured = {}

    def payload_builder(prompt_text, *, model, num_ctx, keep_alive, num_predict):
        captured["builder"] = (prompt_text, model, num_ctx, keep_alive, num_predict)
        return {
            "prompt": prompt_text,
            "model": model,
            "num_ctx": num_ctx,
            "keep_alive": keep_alive,
            "num_predict": num_predict,
        }

    async def response_poster(url, payload, *, timeout):
        captured["post"] = (url, payload, timeout)
        return "reply"

    result = await post_local_llm_response(
        "hello",
        payload_builder,
        payload_kwargs={"num_predict": 99},
        response_poster=response_poster,
    )

    assert result == "reply"
    assert captured["builder"] == ("hello", "qwen-test", 4096, "9m", 99)
    assert captured["post"] == (
        "http://ollama.local/api/generate",
        {
            "prompt": "hello",
            "model": "qwen-test",
            "num_ctx": 4096,
            "keep_alive": "9m",
            "num_predict": 99,
        },
        17,
    )
