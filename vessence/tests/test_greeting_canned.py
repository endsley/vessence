from jane_web.jane_v2.classes.greeting import handler
from jane_web.jane_v2.classes.greeting.canned import (
    CANNED_PATTERNS,
    CANNED_REPLIES,
    PROMPT_TEMPLATE,
    build_greeting_prompt,
    canned_reply,
    clean_greeting_text,
    context_block,
    greeting_llm_payload,
    is_wrong_class,
)
from jane_web.jane_v2.ollama_client import post_local_llm_response


def _first(choices):
    return choices[0]


def test_handler_uses_extracted_greeting_helpers() -> None:
    assert handler._CANNED_PATTERNS is CANNED_PATTERNS
    assert handler._CANNED_REPLIES is CANNED_REPLIES
    assert handler._PROMPT_TEMPLATE is PROMPT_TEMPLATE
    assert handler._build_greeting_prompt is build_greeting_prompt
    assert handler._greeting_llm_payload is greeting_llm_payload
    assert handler._canned_reply is canned_reply
    assert handler._is_wrong_class is is_wrong_class
    assert handler._clean_greeting_text is clean_greeting_text
    assert handler._post_local_llm_response is post_local_llm_response


def test_greeting_response_preserves_text_shape() -> None:
    assert handler.greeting_response("Hey, what's up?") == {"text": "Hey, what's up?"}


def test_canned_reply_matches_common_greeting_buckets_with_injected_choice() -> None:
    assert canned_reply("how's it going?", chooser=_first) == CANNED_REPLIES["check_in"][0]
    assert canned_reply("HEY!!!", chooser=_first) == CANNED_REPLIES["hello"][0]
    assert canned_reply("good morning", chooser=_first) == CANNED_REPLIES["morning"][0]
    assert canned_reply("good afternoon", chooser=_first) == CANNED_REPLIES["afternoon"][0]
    assert canned_reply("good evening", chooser=_first) == CANNED_REPLIES["evening"][0]
    assert canned_reply("thanks", chooser=_first) == CANNED_REPLIES["thanks"][0]


def test_canned_reply_leaves_non_greetings_for_llm_path() -> None:
    assert canned_reply("hey can you set a timer", chooser=_first) is None
    assert canned_reply("", chooser=_first) is None


def test_build_greeting_prompt_and_payload_preserve_llm_path_shape() -> None:
    assert context_block(" Jane: hello ") == "Recent conversation:\nJane: hello\n\n"
    assert context_block(" ") == ""

    prompt = build_greeting_prompt(" hey there ", "Jane: previous")
    assert "Recent conversation:\nJane: previous\n\nUser: hey there\nJane:" in prompt
    assert "output ONLY: WRONG_CLASS" in prompt

    assert greeting_llm_payload("prompt", model="qwen", num_ctx=4096, keep_alive="5m") == {
        "model": "qwen",
        "prompt": "prompt",
        "stream": False,
        "think": False,
        "options": {"temperature": 0.7, "num_predict": 60, "num_ctx": 4096},
        "keep_alive": "5m",
    }


def test_wrong_class_and_cleanup_helpers() -> None:
    assert is_wrong_class("WRONG_CLASS")
    assert is_wrong_class("This is the wrong_class marker")
    assert not is_wrong_class("Hey there")
    assert clean_greeting_text("Jane: Hey there") == "Hey there"
    assert clean_greeting_text("  Hi there  ") == "Hi there"
