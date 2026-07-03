from memory.v1.context_compaction import compaction_split_index


def test_compaction_split_index_returns_none_below_threshold():
    assert compaction_split_index(
        [10, 10],
        current_tokens=20,
        compaction_threshold=20,
        max_tokens=100,
    ) is None


def test_compaction_split_index_removes_enough_old_messages():
    assert compaction_split_index(
        [10, 20, 30, 40],
        current_tokens=100,
        compaction_threshold=70,
        max_tokens=100,
    ) == 2


def test_compaction_split_index_keeps_at_least_one_remaining_message():
    assert compaction_split_index(
        [100, 100, 100],
        current_tokens=300,
        compaction_threshold=50,
        max_tokens=100,
    ) == 1


def test_compaction_split_index_returns_none_when_it_cannot_remove_prior_turns():
    assert compaction_split_index(
        [100],
        current_tokens=100,
        compaction_threshold=50,
        max_tokens=100,
    ) is None
