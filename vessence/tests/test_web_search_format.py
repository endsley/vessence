from agent_skills import web_search_utils
from agent_skills.web_search_format import (
    format_ddg_results,
    format_search_results,
    format_tavily_results,
    is_tavily_quota_status,
    tavily_request_payload,
)


def test_web_search_utils_uses_extracted_format_helpers():
    assert web_search_utils._tavily_request_payload is tavily_request_payload
    assert web_search_utils._is_tavily_quota_status is is_tavily_quota_status
    assert web_search_utils._format_tavily_results is format_tavily_results
    assert web_search_utils._format_ddg_results is format_ddg_results


def test_tavily_request_payload_preserves_search_shape():
    assert tavily_request_payload("key", "latest models", 3) == {
        "api_key": "key",
        "query": "latest models",
        "max_results": 3,
        "search_depth": "basic",
    }


def test_is_tavily_quota_status_matches_quota_and_payment_errors():
    assert is_tavily_quota_status(402)
    assert is_tavily_quota_status(429)
    assert not is_tavily_quota_status(500)


def test_format_tavily_results_preserves_markdown_shape_and_defaults():
    assert format_search_results(
        [{"title": "One", "href": "https://one", "body": "First"}],
        url_key="href",
        body_key="body",
    ) == "[One](https://one)\nFirst"
    assert format_tavily_results([]) == ""
    assert format_tavily_results(
        [
            {"title": "One", "url": "https://one", "content": "First"},
            {"title": "Two"},
        ]
    ) == "[One](https://one)\nFirst\n\n[Two]()\n"


def test_format_ddg_results_preserves_markdown_shape_and_defaults():
    assert format_ddg_results([]) == ""
    assert format_ddg_results(
        [
            {"title": "One", "href": "https://one", "body": "First"},
            {"title": "Two"},
        ]
    ) == "[One](https://one)\nFirst\n\n[Two]()\n"
