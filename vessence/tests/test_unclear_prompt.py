import asyncio

from jane_web.jane_v2 import unclear_prompt


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
