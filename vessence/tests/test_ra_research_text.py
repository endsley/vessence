from agent_skills.ra_research_text import (
    clean_text,
    compact_summary_payload,
    dedupe_summaries,
    list_values,
    parse_json_from_text,
    text_value,
)


def test_clean_text_and_text_value():
    assert clean_text(" a\n\n b\tc ") == "a b c"
    assert text_value("abcdef", max_chars=4) == "abc..."
    assert text_value(None) == ""


def test_list_values_normalizes_dedupes_and_limits_items():
    values = [" Alpha ", "alpha", "Beta", "", "Gamma"]

    assert list_values(values, max_items=2, max_chars=20) == ["Alpha", "Beta"]
    assert list_values("Single", max_items=2) == ["Single"]
    assert list_values(None) == []


def test_dedupe_summaries_uses_source_id_then_title_case_insensitive():
    summaries = [
        {"source_id": "A", "title": "First"},
        {"source_id": "a", "title": "Duplicate"},
        {"source_id": "", "title": "Title Only"},
        {"title": "title only"},
        {"source_id": "", "title": ""},
    ]

    assert dedupe_summaries(summaries) == [summaries[0], summaries[2]]


def test_parse_json_from_text_handles_direct_fenced_and_embedded_objects():
    assert parse_json_from_text('{"a": 1}') == {"a": 1}
    assert parse_json_from_text('```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json_from_text('prefix {"a": 3, "b": "x"} suffix') == {"a": 3, "b": "x"}
    assert parse_json_from_text('{"a": "{brace}", "b": 4} trailing') == {"a": "{brace}", "b": 4}


def test_parse_json_from_text_rejects_empty_malformed_and_non_object_json():
    assert parse_json_from_text("") is None
    assert parse_json_from_text("not json") is None
    assert parse_json_from_text("[1, 2]") is None


def test_compact_summary_payload_trims_and_maps_fields():
    summary = {
        "source_id": "source-1",
        "title": "T" * 300,
        "citation": "Citation",
        "url": "https://example.com",
        "evidence_scope": "guideline",
        "study_type": "Review",
        "main_findings": ["finding", "finding", "other"],
        "remission_relevance": "Relevant",
        "actionable_implications": ["act"],
        "tests_or_monitoring": ["test"],
        "food_diet_implications": ["food"],
        "lifestyle_implications": ["life"],
        "technology_implications": ["tech"],
        "safety_concerns": ["safe"],
        "limitations": ["limit"],
        "clinician_discussion_points": ["ask"],
        "artifact_dir": "/tmp/artifact",
    }

    payload = compact_summary_payload([summary], limit=1)

    assert payload[0]["source_id"] == "source-1"
    assert payload[0]["title"].endswith("...")
    assert payload[0]["findings"] == ["finding", "other"]
    assert payload[0]["clinician_questions"] == ["ask"]
