from pathlib import Path

from agent_skills import ra_research_cron
from agent_skills.ra_research_source_utils import (
    citation_for,
    fallback_first_sentence,
    fallback_summary_payload,
    fallback_study_type,
    source_cache_key,
)


def test_ra_research_cron_uses_source_identity_helpers():
    assert ra_research_cron.source_cache_key is source_cache_key
    assert ra_research_cron.citation_for is citation_for
    assert ra_research_cron._fallback_summary_payload is fallback_summary_payload


def test_source_cache_key_preserves_priority_order_and_fallback():
    assert source_cache_key(
        {"pmid": "", "pmcid": " PMC1 ", "doi": "10.1", "source_id": "src", "url": "url"}
    ) == "PMC1"
    assert source_cache_key({"source_id": "src", "url": "url"}) == "src"


def test_citation_for_preserves_author_limit_and_optional_fields():
    record = {
        "authors": ["A", "B", "C", "D"],
        "published": "2026-07-02",
        "title": "RA remission",
        "journal": "Journal",
        "pmid": "123",
        "doi": "10.1/example",
    }

    assert citation_for(record) == (
        "A, B, C et al. (2026-07-02) RA remission Journal PMID:123 DOI:10.1/example"
    )
    assert citation_for({"title": "Untitled"}) == "Untitled"


def test_fallback_summary_payload_helpers_preserve_text_and_type_rules():
    assert fallback_first_sentence(" First sentence.\n\nSecond sentence. " + "x" * 600) == "First sentence"
    assert fallback_study_type({"publication_types": ["A", "B", "C", "D", "E"], "kind": "fallback"}) == (
        "A, B, C, D"
    )
    assert fallback_study_type({"kind": "guideline"}) == "guideline"
    assert fallback_study_type({}) == "unknown"


def test_fallback_summary_payload_preserves_existing_defaults_and_truncation():
    record = {
        "source_id": "src1",
        "title": "Source Title",
        "url": "https://example.test",
        "publication_types": ["Type1", "Type2", "Type3", "Type4", "Ignored"],
        "authors": ["Author"],
        "published": "2026",
        "pmid": "123",
    }

    payload = fallback_summary_payload(
        record,
        "abstract_only",
        Path("/tmp/artifact"),
        ("First sentence has whitespace.\n\nSecond sentence. " + "x" * 600),
        summarized_at="2026-07-02T12:00:00Z",
    )

    assert payload["source_id"] == "src1"
    assert payload["citation"] == "Author (2026) Source Title PMID:123"
    assert payload["study_type"] == "Type1, Type2, Type3, Type4"
    assert payload["main_findings"] == ["First sentence has whitespace"]
    assert payload["artifact_dir"] == "/tmp/artifact"
    assert payload["needs_llm_review"] is True
    assert payload["summarized_at"] == "2026-07-02T12:00:00Z"
    assert payload["limitations"] == [
        "Fallback summary because local LLM was unavailable or returned invalid JSON."
    ]


def test_fallback_summary_payload_uses_kind_when_publication_types_absent():
    payload = fallback_summary_payload(
        {"source_id": "src2", "kind": "guideline"},
        "scope",
        Path("/tmp/a"),
        "",
        summarized_at="now",
    )

    assert payload["study_type"] == "guideline"
    assert payload["main_findings"] == []
