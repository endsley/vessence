import datetime as dt

from memory.v1 import memory_retrieval
from memory.v1.nearest_memory import (
    _blocks_short_term_candidate,
    _blocks_user_memory_candidate,
    _candidate_distance,
    _promotes_recent_short_term,
    lexical_overlap,
    nearest_candidates_from_rows,
    nearest_memory_candidate,
    nearest_query_terms,
    select_nearest_memory_lines,
)


def _recent_iso(days_ago: int = 1) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).isoformat()


def test_nearest_query_terms_filters_short_words_and_stopwords():
    assert nearest_query_terms("what about ds3000 homework /vault/file-name") == {
        "ds3000",
        "homework",
        "/vault/file-name",
    }


def test_lexical_overlap_counts_query_terms_in_document():
    terms = {"ds3000", "homework", "grading"}

    assert lexical_overlap("DS3000 homework plan", terms) == 2 / 3
    assert lexical_overlap("nothing relevant", terms) == 0
    assert lexical_overlap("anything", set()) == 0


def test_candidate_distance_coerces_numeric_values_and_rejects_bad_values():
    assert _candidate_distance("0.25") == 0.25
    assert _candidate_distance(0.5) == 0.5
    assert _candidate_distance(None) is None
    assert _candidate_distance("bad") is None


def test_recent_short_term_promotion_preserves_age_and_overlap_boundaries():
    assert _promotes_recent_short_term("short_term", 14, 0.35)
    assert not _promotes_recent_short_term("short_term", 14.1, 0.35)
    assert not _promotes_recent_short_term("short_term", 14, 0.34)
    assert not _promotes_recent_short_term("user_memories", 1, 1.0)
    assert not _promotes_recent_short_term("short_term", None, 1.0)


def test_nearest_user_memory_blocking_helper_preserves_source_policy():
    assert _blocks_user_memory_candidate(
        "Vault file: tax/return.pdf",
        {},
        "long_term",
    )
    assert _blocks_user_memory_candidate(
        "prompt list verbatim from a UI prompt",
        {},
        "long_term",
    )
    assert _blocks_user_memory_candidate(
        "Class protocol: stale handler instructions",
        {"memory_type": "short_term"},
        "short_term",
    )
    assert _blocks_user_memory_candidate(
        "Queued prompt",
        {"topic": "prompt_queue"},
        "long_term",
    )
    assert not _blocks_user_memory_candidate(
        "DS3000 homework grading rubric",
        {"topic": "teaching"},
        "long_term",
    )


def test_nearest_short_term_blocking_helper_preserves_staleness_and_noise_policy():
    assert _blocks_short_term_candidate(
        "DS3000 homework grading",
        {"timestamp": _recent_iso(days_ago=20)},
        promoted_recent_short_term=False,
    )
    assert not _blocks_short_term_candidate(
        "DS3000 homework grading",
        {"timestamp": _recent_iso(days_ago=20)},
        promoted_recent_short_term=True,
    )
    assert _blocks_short_term_candidate(
        "Class protocol: stale handler instructions",
        {"timestamp": _recent_iso(days_ago=1)},
        promoted_recent_short_term=True,
    )


def test_nearest_memory_candidate_accepts_valid_memory_and_formats_distance():
    candidate = nearest_memory_candidate(
        "user_memories",
        "DS3000 homework grading rubric",
        {"topic": "teaching", "timestamp": _recent_iso()},
        0.25,
        query_terms={"ds3000", "homework"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    )

    assert candidate is not None
    priority, distance, source, content_key, line = candidate
    assert priority == 1
    assert distance == 0.25
    assert source == "user_memories"
    assert content_key == "ds3000 homework grading rubric"
    assert "(Dist: 0.2500): DS3000 homework grading rubric" in line


def test_nearest_memory_candidate_rejects_bad_distance_low_overlap_and_prompt_queue():
    assert nearest_memory_candidate(
        "user_memories",
        "DS3000 homework",
        {},
        None,
        query_terms={"ds3000"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    ) is None
    assert nearest_memory_candidate(
        "user_memories",
        "unrelated text",
        {},
        0.25,
        query_terms={"ds3000"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    ) is None
    assert nearest_memory_candidate(
        "user_memories",
        "DS3000 homework",
        {"topic": "prompt_queue"},
        0.25,
        query_terms={"ds3000"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    ) is None


def test_nearest_memory_candidate_promotes_recent_short_term_despite_distance():
    candidate = nearest_memory_candidate(
        "short_term",
        "DS3000 homework grading",
        {"memory_type": "short_term", "timestamp": _recent_iso(days_ago=2)},
        0.90,
        query_terms={"ds3000", "homework"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    )

    assert candidate is not None
    assert candidate[0] == 0
    assert candidate[1] == 0.90


def test_nearest_memory_candidate_rejects_stale_short_term_and_file_index_records():
    assert nearest_memory_candidate(
        "short_term",
        "DS3000 homework grading",
        {"memory_type": "short_term", "timestamp": _recent_iso(days_ago=20)},
        0.25,
        query_terms={"ds3000", "homework"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    ) is None
    assert nearest_memory_candidate(
        "user_memories",
        "DS3000 homework file",
        {"topic": "vault_file"},
        0.25,
        query_terms={"ds3000", "homework"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    ) is None


def test_nearest_candidates_from_rows_filters_and_collects_valid_rows():
    candidates = nearest_candidates_from_rows(
        "user_memories",
        ["DS3000 homework grading", "unrelated text", "DS3000 file"],
        [{"topic": "teaching"}, {"topic": "other"}, {"topic": "vault_file"}],
        [0.25, 0.25, 0.25],
        query_terms={"ds3000", "homework"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    )

    assert len(candidates) == 1
    assert candidates[0][2] == "user_memories"
    assert "(Dist: 0.2500): DS3000 homework grading" in candidates[0][4]


def test_memory_retrieval_uses_nearest_memory_selector():
    assert memory_retrieval._nearest_candidates_from_rows is nearest_candidates_from_rows
    assert memory_retrieval._select_nearest_memory_lines is select_nearest_memory_lines


def test_ds3000_anchor_candidates_format_exact_anchor(monkeypatch):
    monkeypatch.setattr(memory_retrieval, "_ds3000_lecture_subtopics", lambda query: ["week1"])
    monkeypatch.setattr(
        memory_retrieval,
        "_get_ds3000_lecture_anchors",
        lambda subtopics: [("Anchor doc", {"topic": "ds3000", "subtopic": subtopics[0]})],
    )
    monkeypatch.setattr(memory_retrieval, "_extract_content_key", lambda doc: f"key:{doc}")
    monkeypatch.setattr(memory_retrieval, "_fmt_memory", lambda doc, meta: f"{meta['subtopic']}:{doc}")

    assert memory_retrieval._ds3000_anchor_candidates("ds3000 week1") == [
        (0, 0.0, "user_memories", "key:Anchor doc", "week1:Anchor doc")
    ]


def test_nearest_candidates_from_query_specs_skips_failed_specs(monkeypatch):
    calls = []

    def fake_query_collection(path, collection, query, limit, query_emb):
        calls.append((path, collection, query, limit, query_emb))
        if collection == "bad":
            raise RuntimeError("boom")
        return (
            ["DS3000 homework", "unrelated"],
            [{"topic": "teaching"}, {"topic": "other"}],
            [0.25, 0.25],
        )

    monkeypatch.setattr(memory_retrieval, "_query_collection", fake_query_collection)

    candidates = memory_retrieval._nearest_candidates_from_query_specs(
        [
            ("user_memories", "/ok", "ok", 2),
            ("short_term", "/bad", "bad", 2),
        ],
        "ds3000 homework",
        [1.0],
        {"ds3000", "homework"},
        max_distance=0.5,
        min_lexical_overlap=0.34,
    )

    assert calls == [
        ("/ok", "ok", "ds3000 homework", 2, [1.0]),
        ("/bad", "bad", "ds3000 homework", 2, [1.0]),
    ]
    assert len(candidates) == 1
    assert candidates[0][2] == "user_memories"
    assert "(Dist: 0.2500): DS3000 homework" in candidates[0][4]


def test_select_nearest_memory_lines_sorts_dedupes_and_limits_candidates():
    candidates = [
        (1, 0.1, "long_term", "same", "Long duplicate"),
        (0, 0.9, "short_term", "recent", "Recent promoted"),
        (1, 0.2, "user_memories", "same", "User duplicate"),
        (1, 0.05, "essence", "essence", "Essence"),
    ]

    assert select_nearest_memory_lines(candidates, limit=3) == [
        "short_term: Recent promoted",
        "essence: Essence",
        "long_term: Long duplicate",
    ]
