from agent_skills.ra_research_candidates import (
    collect_seed_candidates,
    pubmed_search_finding,
    select_pubmed_candidates,
)


def test_collect_seed_candidates_records_findings_and_stops_at_limit():
    sources = [
        {"id": "guideline", "url": "https://example.test/guideline"},
        {"id": "review", "url": "https://example.test/review"},
        {"id": "diet", "url": "https://example.test/diet"},
    ]
    processed = {"web_guideline": {"title": "already cached"}}

    candidates, findings, limit_reached = collect_seed_candidates(sources, processed, max_new=1)

    assert candidates == [{"kind": "web", "source": sources[1], "source_id": "web_review"}]
    assert findings == [
        {"kind": "seed_web_source", "source_id": "web_guideline", "source": sources[0]},
        {"kind": "seed_web_source", "source_id": "web_review", "source": sources[1]},
    ]
    assert limit_reached is True


def test_collect_seed_candidates_reports_all_findings_when_under_limit():
    sources = [
        {"id": "guideline"},
        {"id": "review"},
    ]

    candidates, findings, limit_reached = collect_seed_candidates(sources, {"web_review": {}}, max_new=5)

    assert candidates == [{"kind": "web", "source": sources[0], "source_id": "web_guideline"}]
    assert [finding["source_id"] for finding in findings] == ["web_guideline", "web_review"]
    assert limit_reached is False


def test_pubmed_search_finding_preserves_cache_shape():
    finding = pubmed_search_finding(
        {"name": "latest", "query": "RA remission"},
        retstart=10,
        retmax=8,
        sort="pub date",
        pmids=["1", "2"],
    )

    assert finding == {
        "kind": "pubmed_search_result",
        "profile": "latest",
        "query": "RA remission",
        "retstart": 10,
        "retmax": 8,
        "sort": "pub date",
        "pmids": ["1", "2"],
    }


def test_select_pubmed_candidates_consumes_processed_pmids_before_limit():
    candidates, consumed = select_pubmed_candidates(
        ["10", "11", "12", "13"],
        {"pubmed_10": {}, "pubmed_12": {}},
        profile_name="backlog",
        max_candidates=2,
    )

    assert candidates == [
        {"kind": "pubmed", "pmid": "11", "source_id": "pubmed_11", "profile": "backlog"},
        {"kind": "pubmed", "pmid": "13", "source_id": "pubmed_13", "profile": "backlog"},
    ]
    assert consumed == 4


def test_select_pubmed_candidates_stops_after_first_new_candidate_when_limit_is_one():
    candidates, consumed = select_pubmed_candidates(
        ["20", "21", "22"],
        {"pubmed_20": {}},
        profile_name="latest",
        max_candidates=1,
    )

    assert candidates == [{"kind": "pubmed", "pmid": "21", "source_id": "pubmed_21", "profile": "latest"}]
    assert consumed == 2
