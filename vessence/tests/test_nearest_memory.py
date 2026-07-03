import datetime as dt

from memory.v1 import memory_retrieval
from memory.v1.nearest_memory import (
    lexical_overlap,
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


def test_memory_retrieval_uses_nearest_memory_selector():
    assert memory_retrieval._select_nearest_memory_lines is select_nearest_memory_lines


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
