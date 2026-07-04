import asyncio

from jane_web.jane_v2 import unclear_prompt


def test_unclear_prompt_payload_preserves_qwen_request_shape():
    payload = unclear_prompt._unclear_prompt_payload(
        "  apple meeting blue  ",
        model="qwen",
        num_ctx=2048,
        keep_alive="5m",
    )

    assert payload["model"] == "qwen"
    assert "User prompt: apple meeting blue" in payload["prompt"]
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"] == {
        "temperature": 0.0,
        "num_predict": 5,
        "num_ctx": 2048,
    }
    assert payload["keep_alive"] == "5m"


def test_is_unclear_response_preserves_prefix_policy():
    assert unclear_prompt._is_unclear_response(" unclear ")
    assert unclear_prompt._is_unclear_response("UNCLEAR because it trails")
    assert not unclear_prompt._is_unclear_response(" clear ")


def test_unclear_prompt_uses_shared_ollama_client(monkeypatch):
    captured = {}

    async def fake_post(url, payload, *, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return " unclear "

    monkeypatch.setattr(unclear_prompt, "_post_ollama_response", fake_post)

    assert asyncio.run(unclear_prompt.is_unclear("apple meeting blue", timeout_s=3)) is True
    assert captured["url"]
    assert "apple meeting blue" in captured["payload"]["prompt"]
    assert captured["payload"]["options"]["num_predict"] == 5
    assert captured["timeout"] == 3


def test_unclear_prompt_fails_open_on_ollama_error(monkeypatch):
    async def fake_post(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(unclear_prompt, "_post_ollama_response", fake_post)

    assert asyncio.run(unclear_prompt.is_unclear("cut off prompt", timeout_s=3)) is False
