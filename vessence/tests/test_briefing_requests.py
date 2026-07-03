import pytest

from jane_web.briefing_requests import (
    briefing_submit_values,
    briefing_text_summary_values,
    briefing_url_value,
    is_http_url,
)


def test_is_http_url_preserves_existing_prefix_rule():
    assert is_http_url("https://example.com")
    assert is_http_url("http://example.com")
    assert is_http_url("https://")
    assert not is_http_url(" ftp://example.com")
    assert not is_http_url("example.com")


def test_briefing_submit_values_strips_fields_and_prefers_save_category():
    assert briefing_submit_values(
        {
            "url": "  https://example.com/a  ",
            "title": "  Title  ",
            "text": "  Body  ",
            "save_category": "  Queue  ",
            "category": "Fallback",
        }
    ) == ("https://example.com/a", "Title", "Body", "Queue")


def test_briefing_submit_values_uses_category_fallback_and_empty_defaults():
    assert briefing_submit_values({"url": "https://example.com", "category": "  Saved  "}) == (
        "https://example.com",
        "",
        "",
        "Saved",
    )


def test_briefing_url_value_preserves_existing_url_strip_contract():
    assert briefing_url_value({"url": "  https://example.com  "}) == "https://example.com"
    assert briefing_url_value({}) == ""
    with pytest.raises(AttributeError):
        briefing_url_value({"url": None})


def test_briefing_text_summary_values_strips_title_and_text():
    assert briefing_text_summary_values({"title": "  T  ", "text": "  Body  "}) == ("T", "Body")
    assert briefing_text_summary_values({"title": None, "text": None}) == ("", "")
