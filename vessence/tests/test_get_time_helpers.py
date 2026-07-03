from datetime import datetime, timedelta, timezone

from jane_web.jane_v2.classes.get_time import handler
from jane_web.jane_v2.classes.get_time.time_helpers import (
    FAST_DATE_RE,
    FAST_TIME_RE,
    build_prompt,
    fast_time_reply,
    format_time_info,
    parse_llm_response,
    time_llm_payload,
)
from jane_web.jane_v2.ollama_client import post_local_llm_response


def _fixed_now() -> datetime:
    return datetime(2026, 7, 2, 13, 5, tzinfo=timezone(timedelta(hours=-4), "EDT"))


def test_handler_uses_extracted_get_time_helpers() -> None:
    assert handler._FAST_DATE_RE is FAST_DATE_RE
    assert handler._FAST_TIME_RE is FAST_TIME_RE
    assert handler._fast_time_reply is fast_time_reply
    assert handler._format_time_info is format_time_info
    assert handler._build_prompt is build_prompt
    assert handler._parse_llm_response is parse_llm_response
    assert handler._time_llm_payload is time_llm_payload
    assert handler._post_local_llm_response is post_local_llm_response


def test_fast_time_reply_handles_plain_time_and_date_queries() -> None:
    now = _fixed_now()

    assert fast_time_reply("what time is it", now=now) == "It's 1:05 PM."
    assert fast_time_reply("hey Jane, please tell me the time", now=now) == "It's 1:05 PM."
    assert fast_time_reply("what's today's date", now=now) == "It's Thursday, July 2."
    assert fast_time_reply("what day of the week is it", now=now) == "It's Thursday, July 2."
    assert fast_time_reply("is it late?", now=now) is None
    assert fast_time_reply("", now=now) is None


def test_format_time_info_uses_injected_clock() -> None:
    assert format_time_info(_fixed_now()) == (
        "Current local time: 1:05 PM on Thursday, July 2, 2026 (timezone: EDT)."
    )


def test_build_prompt_includes_recent_context_or_empty_marker() -> None:
    time_info = "Current local time: 1:05 PM on Thursday."

    with_context = build_prompt(" is it late? ", "User: hello\nJane: hi", time_info)
    assert time_info in with_context
    assert "Recent conversation (oldest first):\nUser: hello\nJane: hi\n" in with_context
    assert 'User: "is it late?"' in with_context
    assert "THOUGHT:" in with_context
    assert "REPLY:" in with_context

    without_context = build_prompt("what time is it", "", time_info)
    assert "Recent conversation: (empty)" in without_context


def test_time_llm_payload_preserves_generation_options() -> None:
    assert time_llm_payload(
        "prompt",
        model="qwen",
        num_ctx=4096,
        keep_alive="5m",
    ) == {
        "model": "qwen",
        "prompt": "prompt",
        "stream": False,
        "think": False,
        "options": {"temperature": 0.3, "num_predict": 80, "num_ctx": 4096},
        "keep_alive": "5m",
    }


def test_parse_llm_response_prefers_reply_field_and_falls_back_cleanly() -> None:
    assert parse_llm_response(
        'THOUGHT: user wants the time\nREPLY: "It is just after one."',
        fallback="fallback",
    ) == ("user wants the time", "It is just after one.")
    assert parse_llm_response("Just after one.", fallback="fallback") == ("", "Just after one.")
    assert parse_llm_response("THOUGHT: blank\nREPLY:", fallback="fallback") == ("blank", "fallback")
