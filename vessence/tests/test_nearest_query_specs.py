from types import SimpleNamespace

from memory.v1.nearest_query_specs import build_nearest_query_specs


def plan(**overrides):
    values = {
        "use_user_memory": False,
        "use_shared": False,
        "use_jane_long_term": False,
        "use_short_term": False,
        "use_file_index": False,
        "use_essence": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def specs_for(test_plan, *, limit=2, user_memory_path="/user", essence_path="/essence"):
    return build_nearest_query_specs(
        test_plan,
        user_memory_path=user_memory_path,
        essence_chromadb_path=essence_path,
        limit=limit,
        vector_db_user_memories="/shared-user",
        collection_user_memories="user_collection",
        vector_db_long_term="/long",
        collection_long_term="long_collection",
        long_term_limit=5,
        vector_db_short_term="/short",
        collection_short_term="short_collection",
        short_term_limit=6,
        vector_db_file_index="/files",
        collection_file_index="file_collection",
        chroma_search_limit=7,
    )


def test_build_nearest_query_specs_preserves_source_order_and_limits():
    assert specs_for(
        plan(
            use_user_memory=True,
            use_jane_long_term=True,
            use_short_term=True,
            use_file_index=True,
            use_essence=True,
        ),
        limit=3,
    ) == [
        ("user_memories", "/user", "user_collection", 12),
        ("jane_long_term", "/long", "long_collection", 12),
        ("short_term", "/short", "short_collection", 12),
        ("file_index", "/files", "file_collection", 12),
        ("essence", "/essence", "essence_knowledge", 12),
    ]


def test_build_nearest_query_specs_uses_shared_path_without_user_memory():
    assert specs_for(plan(use_shared=True), limit=1) == [
        ("user_memories", "/shared-user", "user_collection", 7)
    ]


def test_build_nearest_query_specs_uses_minimum_per_source_limits():
    assert specs_for(
        plan(use_jane_long_term=True, use_short_term=True, use_file_index=True),
        limit=1,
    ) == [
        ("jane_long_term", "/long", "long_collection", 5),
        ("short_term", "/short", "short_collection", 6),
        ("file_index", "/files", "file_collection", 8),
    ]


def test_build_nearest_query_specs_uses_empty_essence_path_fallback():
    assert specs_for(plan(use_essence=True), essence_path=None) == [
        ("essence", "", "essence_knowledge", 8)
    ]
