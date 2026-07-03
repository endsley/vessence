from jane_web.jane_v2.classes.tell_joke import handler
from jane_web.jane_v2.classes.tell_joke.helpers import (
    PROMPT_TEMPLATE,
    build_joke_prompt,
    context_block,
    joke_llm_payload,
    parse_joke_response,
)
from jane_web.jane_v2.ollama_client import post_local_llm_response


def test_tell_joke_handler_uses_extracted_helpers() -> None:
    assert handler._PROMPT_TEMPLATE is PROMPT_TEMPLATE
    assert handler._build_joke_prompt is build_joke_prompt
    assert handler._joke_llm_payload is joke_llm_payload
    assert handler._parse_joke_response is parse_joke_response
    assert handler._post_local_llm_response is post_local_llm_response


def test_build_joke_prompt_includes_context_when_present() -> None:
    assert context_block(" Jane told one. ") == "Recent conversation:\nJane told one.\n\n"
    assert context_block(" ") == ""

    prompt = build_joke_prompt(" another one ", "Jane: old joke")

    assert "Recent conversation:\nJane: old joke\n\nUser: \"another one\"" in prompt
    assert "Tell ONE short clean joke." in prompt
    assert prompt.endswith("REPLY: <the joke itself, plain spoken English for TTS, no markdown, no emoji>")


def test_joke_llm_payload_preserves_generation_options() -> None:
    assert joke_llm_payload(
        "prompt",
        model="qwen",
        num_ctx=4096,
        keep_alive="5m",
    ) == {
        "model": "qwen",
        "prompt": "prompt",
        "stream": False,
        "think": False,
        "options": {"temperature": 0.9, "num_predict": 100, "num_ctx": 4096},
        "keep_alive": "5m",
    }


def test_parse_joke_response_prefers_reply_and_strips_quote_wrapping() -> None:
    assert parse_joke_response('THOUGHT: pun\nREPLY: "Why did it cross? To get there."') == (
        "pun",
        "Why did it cross? To get there.",
    )
    assert parse_joke_response("Just a joke.") == ("", "Just a joke.")


def test_parse_joke_response_omits_thought_only_prefix_from_spoken_reply() -> None:
    assert parse_joke_response("THOUGHT: animal pun\nA setup.\nA punchline.") == (
        "animal pun",
        "A setup.\nA punchline.",
    )
    assert parse_joke_response("THOUGHT: animal pun") == ("animal pun", "animal pun")
