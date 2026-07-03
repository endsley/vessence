from pathlib import Path

from agent_skills.ra_research_summary_cache import (
    build_processed_source_entry,
    finalize_summary_for_cache,
    load_cached_summary,
    readable_text_from_artifact,
    read_json_dict,
    summary_to_markdown,
)


def test_read_json_dict_and_load_cached_summary(tmp_path: Path):
    missing = tmp_path / "missing.json"
    assert read_json_dict(missing) is None
    assert load_cached_summary(missing) == (None, False)

    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert read_json_dict(bad) is None

    needs_review = tmp_path / "needs_review.json"
    needs_review.write_text('{"source_id": "s1", "needs_llm_review": true}', encoding="utf-8")
    assert load_cached_summary(needs_review) == ({"source_id": "s1", "needs_llm_review": True}, False)

    complete = tmp_path / "complete.json"
    complete.write_text('{"source_id": "s2", "needs_llm_review": false}', encoding="utf-8")
    assert load_cached_summary(complete) == ({"source_id": "s2", "needs_llm_review": False}, True)


def test_finalize_summary_for_cache_preserves_existing_fields_and_sets_cache_metadata(tmp_path: Path):
    summary = {"title": "LLM title", "main_findings": ["Finding"]}
    record = {
        "source_id": "pmid-1",
        "title": "Record title",
        "url": "https://example.test/source",
    }

    finalized = finalize_summary_for_cache(
        summary,
        record,
        artifact_dir=tmp_path / "artifact",
        evidence_scope="abstract_only",
        cache_key="12345",
        summarized_at="2026-07-02T12:00:00+00:00",
        citation="Citation text",
    )

    assert finalized is summary
    assert finalized["title"] == "LLM title"
    assert finalized["source_id"] == "pmid-1"
    assert finalized["citation"] == "Citation text"
    assert finalized["url"] == "https://example.test/source"
    assert finalized["evidence_scope"] == "abstract_only"
    assert finalized["artifact_dir"] == str(tmp_path / "artifact")
    assert finalized["cache_key"] == "12345"
    assert finalized["summarized_at"] == "2026-07-02T12:00:00+00:00"


def test_build_processed_source_entry_matches_state_shape(tmp_path: Path):
    entry = build_processed_source_entry(
        {"title": "Title", "url": "https://example.test"},
        source_id="web_seed",
        artifact_dir=tmp_path / "papers" / "web_seed",
        summary_dir=tmp_path / "summaries",
        evidence_scope="guideline_or_review_page",
        cache_key="web_seed",
        processed_at="2026-07-02T12:34:56+00:00",
    )

    assert entry == {
        "title": "Title",
        "url": "https://example.test",
        "processed_at": "2026-07-02T12:34:56+00:00",
        "artifact_dir": str(tmp_path / "papers" / "web_seed"),
        "summary_path": str(tmp_path / "summaries" / "web_seed.json"),
        "evidence_scope": "guideline_or_review_page",
        "cache_key": "web_seed",
    }


def test_readable_text_from_artifact_prefers_full_text_then_readable_then_abstract(tmp_path: Path):
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "abstract.txt").write_text("abstract", encoding="utf-8")
    (artifact / "readable_text.txt").write_text("readable", encoding="utf-8")
    assert readable_text_from_artifact(artifact) == "readable"

    (artifact / "full_text.txt").write_text("full", encoding="utf-8")
    assert readable_text_from_artifact(artifact) == "full"
    assert readable_text_from_artifact(tmp_path / "missing") == ""


def test_summary_to_markdown_keeps_source_trace_sections():
    markdown = summary_to_markdown(
        {
            "title": "RA remission source",
            "source_id": "pmid-1",
            "citation": "Citation",
            "url": "https://example.test",
            "evidence_scope": "open_access_full_text",
            "study_type": "guideline",
            "artifact_dir": "/vault/papers/pmid-1",
            "population": "Adults with RA.",
            "intervention_or_exposure": "Treat to target.",
            "main_findings": [" CDAI\nremission ", ""],
            "remission_relevance": "Useful for clinician discussion.",
            "actionable_implications": ["Ask about CDAI."],
            "tests_or_monitoring": ["ESR/CRP"],
            "clinician_discussion_points": ["Which score?"],
        }
    )

    assert markdown.startswith("# RA remission source\n")
    assert "- Source ID: `pmid-1`" in markdown
    assert "- Saved artifact directory: `/vault/papers/pmid-1`" in markdown
    assert "## Main Findings\n- CDAI remission" in markdown
    assert "## Safety Concerns\n- None captured." in markdown
    assert markdown.endswith("\n")
