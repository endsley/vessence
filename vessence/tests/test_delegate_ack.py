import asyncio

from jane_web.jane_v2 import pipeline
from jane_web.jane_v2.delegate_ack import (
    avoid_got_it_default,
    delegate_ack_prompt,
    estimate_duration,
    normalize_delegate_ack_response,
)


def test_estimate_duration_uses_signal_words_and_word_count():
    assert estimate_duration("what time is it") == "a few seconds"
    assert estimate_duration("explain how rsync works") == "a minute or two"
    assert estimate_duration("please refactor the pipeline") == "a while"
    assert estimate_duration("word " * 61) == "a while"


def test_avoid_got_it_default_rewrites_by_class():
    assert avoid_got_it_default("Okay, checking now", cls="others") == "Okay, checking now"
    assert avoid_got_it_default("Got it, checking your calendar", cls="read calendar") == (
        "Checking your calendar"
    )
    assert avoid_got_it_default("Got it, message draft", cls="send message") == "Okay, message draft"
    assert avoid_got_it_default("Got it", cls="others") == "On it."


def test_delegate_ack_prompt_includes_flow_duration_class_and_truncated_user_message():
    prompt = delegate_ack_prompt(
        "x" * 500,
        cls="read email",
        duration="a minute or two",
        flow_context="Jane asked which inbox.",
    )

    assert "Recent conversation flow, oldest to newest" in prompt
    assert "Jane asked which inbox." in prompt
    assert "Rough scale: a minute or two." in prompt
    assert "Routing class: read email" in prompt
    assert "User message: " + ("x" * 400) in prompt
    assert "x" * 401 not in prompt
    assert "Your one-sentence acknowledgment" in prompt


def test_normalize_delegate_ack_response_strips_labels_quotes_caps_and_rewrites_got_it():
    assert normalize_delegate_ack_response('"Acknowledgment: Got it, message draft"', cls="send message") == (
        "Okay, message draft"
    )

    long_text = "This is a complete sentence. " + ("x" * 160)
    assert normalize_delegate_ack_response(long_text, cls="others") == "This is a complete sentence."

    no_period = "x" * 160
    assert normalize_delegate_ack_response(no_period, cls="others") == "x" * 120


def test_generate_delegate_ack_uses_shared_ollama_client(monkeypatch):
    captured = {}

    async def fake_post(url, payload, *, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return "Acknowledgment: Got it, message draft"

    monkeypatch.setattr(pipeline, "_post_ollama_response", fake_post)
    monkeypatch.setattr(pipeline, "_recent_ack_context", lambda session_id: "Jane: previous")

    result = asyncio.run(pipeline._generate_delegate_ack("make it warmer", "sid", cls="send message"))

    assert result == "Okay, message draft"
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert "Jane: previous" in captured["payload"]["prompt"]
    assert captured["payload"]["options"]["num_predict"] == 40
    assert captured["timeout"]
