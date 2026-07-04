import datetime as dt

from memory.v1.retrieved_memory_facts import (
    collect_essence_facts,
    collect_file_index_facts,
    collect_jane_long_term_facts,
    collect_short_term_semantic_facts,
    collect_short_term_with_recency_boost,
    collect_user_memory_facts,
    include_long_term_user_memory_fact,
    is_usable_short_term_fact,
    recent_short_term_rows,
    user_memory_tier,
    within_distance,
)


def _past_iso(days: int = 1) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()


def test_within_distance_keeps_legacy_fail_open_behavior():
    assert within_distance(None, 0.5)
    assert within_distance(0.4, None)
    assert within_distance("bad", 0.5)
    assert within_distance(0.4, 0.5)
    assert not within_distance(0.6, 0.5)


def test_user_memory_tier_preserves_legacy_routing():
    assert user_memory_tier("permanent") == "permanent"
    assert user_memory_tier("forgettable") == "legacy_short_term"
    assert user_memory_tier("short_term") == "legacy_short_term"
    assert user_memory_tier("long_term") == "long_term"
    assert user_memory_tier(None) == "long_term"


def test_include_long_term_user_memory_fact_preserves_policy_filters():
    assert include_long_term_user_memory_fact(
        "Family long-term note",
        {"topic": "family"},
        0.3,
        max_distance=0.5,
        anchor_docs=set(),
    )
    assert not include_long_term_user_memory_fact(
        "Too far note",
        {"topic": "family"},
        0.8,
        max_distance=0.5,
        anchor_docs=set(),
    )
    assert not include_long_term_user_memory_fact(
        "Queued prompt",
        {"topic": "prompt_queue"},
        0.1,
        max_distance=0.5,
        anchor_docs=set(),
    )
    assert not include_long_term_user_memory_fact(
        "DS3000 lecture anchor",
        {"topic": "ds3000_lecture_notes"},
        0.1,
        max_distance=0.5,
        anchor_docs={"DS3000 lecture anchor"},
    )


def test_collect_user_memory_facts_splits_tiers_and_filters_noise():
    facts = collect_user_memory_facts(
        docs=[
            "Permanent identity",
            "Legacy short note",
            "Family long-term note",
            "Vault file: ignored.md",
            "Prompt queue should not inject",
            "DS3000 lecture anchor",
            "Logged in with Google account chieh@example.com",
            "Too distant long-term note",
        ],
        metas=[
            {"memory_type": "permanent", "topic": "identity"},
            {"memory_type": "forgettable", "topic": "scratch"},
            {"topic": "family"},
            {"topic": "vault_file"},
            {"topic": "prompt_queue"},
            {"topic": "ds3000_lecture_notes"},
            {"topic": "auth"},
            {"topic": "project"},
        ],
        distances=[0.8, 0.2, 0.3, 0.1, 0.1, 0.1, 0.1, 0.9],
        exact_anchor_docs=["DS3000 lecture anchor"],
        permanent_max_distance=1.0,
        short_term_max_distance=0.5,
        user_max_distance=0.5,
    )

    assert facts.permanent == ["[unknown age] (identity) (Dist: 0.8000): Permanent identity"]
    assert facts.legacy_short_term == ["[unknown age] (scratch) (Dist: 0.2000): Legacy short note"]
    assert facts.long_term == ["[unknown age] (family) (Dist: 0.3000): Family long-term note"]


def test_collect_short_term_semantic_facts_filters_expired_stale_none_noise_and_far_entries():
    facts = collect_short_term_semantic_facts(
        docs=[
            "Recent useful note",
            "Expired note",
            "Old note",
            "None",
            "**Class Protocol:** read_calendar",
            "Too far note",
        ],
        metas=[
            {"topic": "recent"},
            {"expires_at": _past_iso()},
            {"timestamp": _past_iso(days=10)},
            {},
            {"memory_type": "short_term"},
            {},
        ],
        distances=[0.2, 0.2, 0.2, 0.2, 0.2, 0.9],
        max_distance=0.5,
    )

    assert facts == ["[unknown age] (recent) (Dist: 0.2000): Recent useful note"]


def test_is_usable_short_term_fact_reuses_noise_filters():
    assert is_usable_short_term_fact("Useful note", {"topic": "recent"})
    assert not is_usable_short_term_fact("Expired note", {"expires_at": _past_iso()})
    assert not is_usable_short_term_fact("Old note", {"timestamp": _past_iso(days=10)})
    assert not is_usable_short_term_fact("None", {})
    assert not is_usable_short_term_fact("**Class Protocol:** timer", {"memory_type": "short_term"})


def test_recent_short_term_rows_sorts_by_timestamp_and_limits_rows():
    assert recent_short_term_rows(
        ["old", "missing", "new"],
        [
            {"timestamp": "2026-07-03T09:00:00Z"},
            None,
            {"timestamp": "2026-07-04T09:00:00Z"},
        ],
        limit=2,
    ) == [
        ("new", {"timestamp": "2026-07-04T09:00:00Z"}),
        ("old", {"timestamp": "2026-07-03T09:00:00Z"}),
    ]


def test_collect_short_term_with_recency_boost_sorts_filters_and_preserves_legacy_dedupe_key():
    semantic = collect_short_term_semantic_facts(
        ["Already present"],
        [{"topic": "recent"}],
        [0.2],
        max_distance=0.5,
    )

    boosted = collect_short_term_with_recency_boost(
        semantic,
        docs=[
            "Old stale note",
            "Newest useful note",
            "Already present",
            "None",
            "**Class Protocol:** timer",
        ],
        metas=[
            {"timestamp": _past_iso(days=10), "topic": "old"},
            {"timestamp": _past_iso(days=0), "topic": "new"},
            {"timestamp": _past_iso(days=0), "topic": "recent"},
            {"timestamp": _past_iso(days=0), "topic": "none"},
            {"timestamp": _past_iso(days=0), "memory_type": "short_term"},
        ],
        limit=5,
    )

    assert boosted[0] == "[unknown age] (recent) (Dist: 0.2000): Already present"
    assert len(boosted) == 3
    assert boosted[1].endswith(": Already present")
    assert boosted[2].endswith(": Newest useful note")
    assert all("Old stale note" not in fact for fact in boosted)
    assert all("**Class Protocol:**" not in fact for fact in boosted)


def test_collect_expiring_distance_fact_lists_preserve_formatting_policy():
    docs = ["Good", "Expired", "Far"]
    metas = [{"topic": "ok"}, {"expires_at": _past_iso()}, {"topic": "far"}]
    distances = [0.2, 0.2, 0.9]

    expected = ["[unknown age] (ok) (Dist: 0.2000): Good"]
    assert collect_jane_long_term_facts(docs, metas, distances, max_distance=0.5) == expected
    assert collect_file_index_facts(docs, metas, distances, max_distance=0.5) == expected
    assert collect_essence_facts(docs, metas, distances, max_distance=0.5) == expected
