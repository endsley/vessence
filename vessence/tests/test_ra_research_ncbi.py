from agent_skills import ra_research_cron
from agent_skills.ra_research_ncbi import (
    ncbi_params,
    pubmed_fetch_cache_text,
    pubmed_fetch_params,
    pubmed_ids_from_search_response,
    pubmed_search_cache_payload,
    pubmed_search_params,
)


def test_ra_research_cron_uses_ncbi_helpers():
    assert ra_research_cron._ncbi_params is ncbi_params
    assert ra_research_cron.pubmed_search_params is pubmed_search_params
    assert ra_research_cron.pubmed_search_cache_payload is pubmed_search_cache_payload
    assert ra_research_cron.pubmed_ids_from_search_response is pubmed_ids_from_search_response
    assert ra_research_cron.pubmed_fetch_params is pubmed_fetch_params
    assert ra_research_cron.pubmed_fetch_cache_text is pubmed_fetch_cache_text


def test_ncbi_params_preserves_api_key_and_extra_override_behavior():
    assert ncbi_params({"db": "pubmed"}, tool="tool", email="email", api_key=" key ") == {
        "tool": "tool",
        "email": "email",
        "api_key": "key",
        "db": "pubmed",
    }
    assert ncbi_params({"tool": "override"}, tool="tool", email="email") == {
        "tool": "override",
        "email": "email",
    }


def test_pubmed_search_params_preserve_esearch_contract():
    assert pubmed_search_params(
        "ra",
        retmax=8,
        retstart=16,
        sort="pub date",
        tool="tool",
        email="email",
        api_key="key",
    ) == {
        "tool": "tool",
        "email": "email",
        "api_key": "key",
        "db": "pubmed",
        "term": "ra",
        "retmode": "json",
        "retmax": 8,
        "retstart": 16,
        "sort": "pub date",
    }


def test_pubmed_search_cache_payload_and_id_extraction_preserve_shapes():
    data = {"esearchresult": {"idlist": [123, "456"]}}

    assert pubmed_search_cache_payload(
        fetched_at="now",
        url="https://example.test",
        query="ra",
        retmax=8,
        retstart=0,
        sort="relevance",
        response=data,
    ) == {
        "fetched_at": "now",
        "url": "https://example.test",
        "query": "ra",
        "retmax": 8,
        "retstart": 0,
        "sort": "relevance",
        "response": data,
    }
    assert pubmed_ids_from_search_response(data) == ["123", "456"]
    assert pubmed_ids_from_search_response({}) == []


def test_pubmed_fetch_params_and_cache_text_preserve_contracts():
    assert pubmed_fetch_params(["1", "2"], tool="tool", email="email") == {
        "tool": "tool",
        "email": "email",
        "db": "pubmed",
        "id": "1,2",
        "retmode": "xml",
    }
    assert pubmed_fetch_cache_text(
        fetched_at="now",
        url="https://example.test",
        pmids=["1", "2"],
        response_text="<xml />",
    ) == "Fetched at: now\nURL: https://example.test\nPMIDs: 1, 2\n\n<xml />"
