from memory.v1.query_plan import MemoryQueryPlan, build_memory_query_plan


def _exists(paths):
    return lambda path: path in paths


def test_build_memory_query_plan_uses_private_user_memory_when_available():
    assert build_memory_query_plan(
        intent="general",
        assistant_name="Jane",
        user_memory_path="/private",
        essence_chromadb_path="/essence",
        path_exists=_exists({"/private", "/essence"}),
    ) == MemoryQueryPlan(
        use_user_memory=True,
        use_shared=False,
        use_jane_long_term=False,
        use_short_term=False,
        use_file_index=False,
        use_essence=True,
    )


def test_build_memory_query_plan_shared_jane_general_includes_long_and_short_term():
    assert build_memory_query_plan(
        intent="general",
        assistant_name="Jane",
        path_exists=_exists(set()),
    ) == MemoryQueryPlan(
        use_user_memory=False,
        use_shared=True,
        use_jane_long_term=True,
        use_short_term=True,
        use_file_index=False,
        use_essence=False,
    )


def test_build_memory_query_plan_amber_suppresses_jane_long_term():
    plan = build_memory_query_plan(
        intent="project_work",
        assistant_name=" Amber ",
        path_exists=_exists(set()),
    )

    assert plan.use_shared
    assert not plan.use_jane_long_term
    assert plan.use_short_term


def test_build_memory_query_plan_file_lookup_uses_file_index_only_for_shared_memory():
    shared = build_memory_query_plan(intent="file_lookup", assistant_name="Jane", path_exists=_exists(set()))
    managed = build_memory_query_plan(
        intent="file_lookup",
        assistant_name="Jane",
        user_memory_path="/private",
        path_exists=_exists({"/private"}),
    )

    assert shared.use_file_index
    assert shared.use_shared
    assert not managed.use_file_index
    assert managed.use_user_memory
