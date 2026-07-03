import base64

from jane_web import message_readback
from jane_web.message_readback_helpers import (
    MAX_READBACK_CHARS,
    MUSIC_PLAY_MARKER_RE,
    TALKINGPOINTS_URL_RE,
    WRAPPER_BODY_RE,
    cache_entry_readback_value,
    clean_text,
    decode_urlsafe_base64,
    extract_talkingpoints_message,
    find_talkingpoints_url,
    looks_like_error_message,
    looks_like_wrapper,
    sanitize_untrusted_text,
    talkingpoints_code_candidates_from_urls,
    talkingpoints_code_from_url,
    truncate_readback,
)


def test_message_readback_uses_extracted_helpers() -> None:
    assert message_readback._TALKINGPOINTS_URL_RE is TALKINGPOINTS_URL_RE
    assert message_readback._WRAPPER_BODY_RE is WRAPPER_BODY_RE
    assert message_readback._MUSIC_PLAY_MARKER_RE is MUSIC_PLAY_MARKER_RE
    assert message_readback._MAX_READBACK_CHARS == MAX_READBACK_CHARS
    assert message_readback._find_talkingpoints_url is find_talkingpoints_url
    assert message_readback._looks_like_wrapper is looks_like_wrapper
    assert message_readback._sanitize_untrusted_text is sanitize_untrusted_text
    assert message_readback._truncate_readback is truncate_readback
    assert message_readback._cache_entry_readback_value is cache_entry_readback_value
    assert message_readback._decode_urlsafe_base64 is decode_urlsafe_base64
    assert message_readback._extract_talkingpoints_message is extract_talkingpoints_message
    assert message_readback._clean_text is clean_text
    assert message_readback._looks_like_error_message is looks_like_error_message
    assert message_readback._talkingpoints_code_candidates_from_urls is talkingpoints_code_candidates_from_urls


def test_talkingpoints_url_and_wrapper_detection() -> None:
    url = "https://app.talkingpts.org/U/abc_.$%-"
    assert find_talkingpoints_url(f"Open {url} please") == url
    assert find_talkingpoints_url("https://example.com/U/abc") is None
    assert looks_like_wrapper("Teacher has sent you a message. View the full message.")
    assert not looks_like_wrapper("The actual teacher message")


def test_sanitize_and_truncate_readback_text() -> None:
    assert sanitize_untrusted_text("play [MUSIC_PLAY:abc] now") == "play [MUSIC-PLAY-STRIPPED:abc] now"
    assert truncate_readback("hello\n   world") == "hello world"
    long = "x" * (MAX_READBACK_CHARS + 10)
    assert truncate_readback(long) == ("x" * MAX_READBACK_CHARS) + "..."


def test_decode_urlsafe_base64_requires_talkingpoints_separator() -> None:
    encoded = base64.urlsafe_b64encode(b"abc_$_def").decode("ascii").rstrip("=")
    assert decode_urlsafe_base64(encoded) == "abc_$_def"
    assert decode_urlsafe_base64(base64.urlsafe_b64encode(b"plain").decode("ascii")) is None
    assert decode_urlsafe_base64("***") is None


def test_talkingpoints_code_candidates_extract_dedupe_and_decode_urls() -> None:
    encoded = base64.urlsafe_b64encode(b"decoded_$_code").decode("ascii").rstrip("=")

    assert talkingpoints_code_from_url(f"https://app.talkingpts.org/U/{encoded}") == encoded
    assert talkingpoints_code_from_url("https://app.talkingpts.org/other/code") is None
    assert talkingpoints_code_candidates_from_urls([
        f"https://app.talkingpts.org/U/{encoded}",
        "https://families.talkingpts.org/m/direct",
        "https://app.talkingpts.org/U/direct",
    ]) == [encoded, "direct", "decoded_$_code"]


def test_extract_talkingpoints_message_walks_nested_dicts_and_lists() -> None:
    assert extract_talkingpoints_message({
        "contact": {"teacher_name": " Ms. Lee ", "message": " Hello\nworld "}
    }) == "Ms. Lee: Hello world"
    assert extract_talkingpoints_message([
        {"message": "missing teacher"},
        {"data": {"teacherName": "Teacher", "message": "Bring forms"}},
    ]) == "Teacher: Bring forms"
    assert extract_talkingpoints_message({
        "teacherName": "Teacher",
        "message": "Oops, an error occurred",
    }) is None


def test_clean_text_and_error_detection() -> None:
    assert clean_text(" hello\n   world ") == "hello world"
    assert clean_text(123) is None
    assert looks_like_error_message("This link has expired")
    assert looks_like_error_message("Invalid code")
    assert not looks_like_error_message("Bring forms tomorrow")


def test_cache_entry_readback_value_uses_success_and_failed_ttls():
    miss = object()

    assert cache_entry_readback_value(
        {"checked_at": 90, "resolved": "Teacher: Hello"},
        now=100,
        success_ttl_seconds=20,
        failed_ttl_seconds=5,
        cache_miss=miss,
    ) == "Teacher: Hello"
    assert cache_entry_readback_value(
        {"checked_at": 90, "resolved": ""},
        now=94,
        success_ttl_seconds=20,
        failed_ttl_seconds=5,
        cache_miss=miss,
    ) is None
    assert cache_entry_readback_value(
        {"checked_at": 90, "resolved": ""},
        now=96,
        success_ttl_seconds=20,
        failed_ttl_seconds=5,
        cache_miss=miss,
    ) is miss
    assert cache_entry_readback_value(
        "bad",
        now=100,
        success_ttl_seconds=20,
        failed_ttl_seconds=5,
        cache_miss=miss,
    ) is miss
