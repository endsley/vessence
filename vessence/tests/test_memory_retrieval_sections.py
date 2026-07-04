from types import SimpleNamespace

from memory.v1 import memory_retrieval


class FakeFuture:
    def __init__(self, value=None, error: Exception | None = None):
        self.value = value
        self.error = error

    def result(self):
        if self.error is not None:
            raise self.error
        return self.value


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def submit(self, *args):
        self.calls.append(args)
        return FakeFuture(args)


class FakeCollection:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def count(self):
        return len(self.results.get("documents", []))

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class FakeClient:
    def __init__(self, collection):
        self.collection = collection
        self.calls = []

    def get_collection(self, name):
        self.calls.append(name)
        return self.collection


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


def test_memory_sections_cache_key_normalizes_none_values():
    assert memory_retrieval._memory_sections_cache_key("q", "Jane", None, "/user", None) == (
        "q",
        "Jane",
        "",
        "/user",
        "",
    )


def test_safe_future_result_handles_missing_and_failed_futures():
    assert memory_retrieval._safe_future_result({}, "missing") == ([], [], [])
    assert memory_retrieval._safe_future_result(
        {"ok": FakeFuture((["doc"], [{"topic": "x"}], [0.1]))},
        "ok",
    ) == (["doc"], [{"topic": "x"}], [0.1])
    assert memory_retrieval._safe_future_result(
        {"bad": FakeFuture(error=RuntimeError("boom"))},
        "bad",
    ) == ([], [], [])


def test_section_query_specs_preserve_source_order_limits_and_embedding_policy(monkeypatch):
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_USER_MEMORIES", "/shared")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_USER_MEMORIES", "users")
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_LONG_TERM", "/long")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_LONG_TERM", "long")
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_SHORT_TERM", "/short")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_SHORT_TERM", "short")
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_FILE_INDEX", "/files")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_FILE_INDEX", "files")
    monkeypatch.setattr(memory_retrieval, "CHROMA_SEARCH_LIMIT", 9)
    monkeypatch.setattr(memory_retrieval, "CHROMA_LONG_TERM_LIMIT", 5)
    monkeypatch.setattr(memory_retrieval, "CHROMA_SHORT_TERM_LIMIT", 6)

    assert memory_retrieval._section_query_specs(
        plan(
            use_shared=True,
            use_jane_long_term=True,
            use_short_term=True,
            use_file_index=True,
            use_essence=True,
        ),
        user_memory_path=None,
        essence_chromadb_path="/essence",
    ) == [
        ("user_memories", "/shared", "users", 9, True),
        ("jane_long_term", "/long", "long", 5, True),
        ("short_term", "/short", "short", 6, True),
        ("file_index", "/files", "files", 8, True),
        ("essence", "/essence", "essence_knowledge", 9, False),
    ]


def test_submit_section_queries_preserves_source_order_and_limits(monkeypatch):
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_USER_MEMORIES", "/shared")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_USER_MEMORIES", "users")
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_LONG_TERM", "/long")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_LONG_TERM", "long")
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_SHORT_TERM", "/short")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_SHORT_TERM", "short")
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_FILE_INDEX", "/files")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_FILE_INDEX", "files")
    monkeypatch.setattr(memory_retrieval, "CHROMA_SEARCH_LIMIT", 9)
    monkeypatch.setattr(memory_retrieval, "CHROMA_LONG_TERM_LIMIT", 5)
    monkeypatch.setattr(memory_retrieval, "CHROMA_SHORT_TERM_LIMIT", 6)
    executor = FakeExecutor()

    futures = memory_retrieval._submit_section_queries(
        executor,
        plan(
            use_shared=True,
            use_jane_long_term=True,
            use_short_term=True,
            use_file_index=True,
            use_essence=True,
        ),
        "query",
        [1.0],
        user_memory_path=None,
        essence_chromadb_path="/essence",
    )

    assert list(futures) == [
        "user_memories",
        "jane_long_term",
        "short_term",
        "file_index",
        "essence",
    ]
    assert executor.calls == [
        (memory_retrieval._query_collection, "/shared", "users", "query", 9, [1.0]),
        (memory_retrieval._query_collection, "/long", "long", "query", 5, [1.0]),
        (memory_retrieval._query_collection, "/short", "short", "query", 6, [1.0]),
        (memory_retrieval._query_collection, "/files", "files", "query", 8, [1.0]),
        (memory_retrieval._query_collection, "/essence", "essence_knowledge", "query", 9),
    ]


def test_collect_legacy_forgettable_facts_filters_noise(monkeypatch):
    collection = FakeCollection({
        "ids": ["1", "2", "3", "4"],
        "documents": ["keep", "expired", "none", "low"],
        "metadatas": [{}, {"expired": True}, {}, {"low": True}],
    })
    client = FakeClient(collection)
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_USER_MEMORIES", "/shared")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_USER_MEMORIES", "users")
    monkeypatch.setattr(memory_retrieval, "get_chroma_client", lambda path: client)
    monkeypatch.setattr(memory_retrieval, "_is_expired", lambda meta: meta.get("expired", False))
    monkeypatch.setattr(memory_retrieval, "_is_none_content", lambda doc: doc == "none")
    monkeypatch.setattr(
        memory_retrieval,
        "_is_low_signal_short_term_memory",
        lambda _doc, meta: meta.get("low", False),
    )
    monkeypatch.setattr(memory_retrieval, "_fmt_memory", lambda doc, _meta: f"formatted:{doc}")

    assert memory_retrieval._collect_legacy_forgettable_facts() == ["formatted:keep"]
    assert client.calls == ["users"]
    assert collection.calls == [
        {"where": {"memory_type": "forgettable"}, "include": ["documents", "metadatas"]}
    ]


def test_collect_legacy_forgettable_facts_is_best_effort(monkeypatch):
    def fail_client(path):
        raise RuntimeError(path)

    monkeypatch.setattr(memory_retrieval, "get_chroma_client", fail_client)

    assert memory_retrieval._collect_legacy_forgettable_facts() == []


def test_apply_short_term_recency_boost_reads_recent_short_term(monkeypatch):
    collection = FakeCollection({
        "documents": ["recent 1", "recent 2"],
        "metadatas": [{"source": "a"}, {"source": "b"}],
    })
    client = FakeClient(collection)
    calls = []

    def fake_boost(existing, docs, metas, limit):
        calls.append((existing, docs, metas, limit))
        return existing + ["boosted"]

    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_SHORT_TERM", "/short")
    monkeypatch.setattr(memory_retrieval, "CHROMA_COLLECTION_SHORT_TERM", "short")
    monkeypatch.setattr(memory_retrieval.os.path, "exists", lambda path: path == "/short")
    monkeypatch.setattr(memory_retrieval, "get_chroma_client", lambda path: client)
    monkeypatch.setattr(memory_retrieval, "_collect_short_term_with_recency_boost", fake_boost)

    assert memory_retrieval._apply_short_term_recency_boost(["semantic"]) == [
        "semantic",
        "boosted",
    ]
    assert calls == [
        (
            ["semantic"],
            ["recent 1", "recent 2"],
            [{"source": "a"}, {"source": "b"}],
            3,
        )
    ]
    assert collection.calls == [{"include": ["documents", "metadatas"], "limit": 2}]


def test_apply_short_term_recency_boost_returns_existing_on_failure(monkeypatch):
    monkeypatch.setattr(memory_retrieval, "VECTOR_DB_SHORT_TERM", "/short")
    monkeypatch.setattr(memory_retrieval.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        memory_retrieval,
        "get_chroma_client",
        lambda path: (_ for _ in ()).throw(RuntimeError(path)),
    )

    assert memory_retrieval._apply_short_term_recency_boost(["semantic"]) == ["semantic"]


def test_collect_user_and_shared_facts_combines_anchors_user_and_legacy(monkeypatch):
    captured = {}

    def fake_collect_user(docs, metas, distances, **kwargs):
        captured["docs"] = docs
        captured["metas"] = metas
        captured["distances"] = distances
        captured["anchors"] = list(kwargs["exact_anchor_docs"])
        return SimpleNamespace(
            permanent=["permanent"],
            long_term=["long-term"],
            legacy_short_term=["legacy-user"],
        )

    monkeypatch.setattr(memory_retrieval, "_ds3000_lecture_subtopics", lambda query: ["week1"])
    monkeypatch.setattr(
        memory_retrieval,
        "_get_ds3000_lecture_anchors",
        lambda subtopics: [("anchor-doc", {"subtopic": subtopics[0]})],
    )
    monkeypatch.setattr(memory_retrieval, "_fmt_memory", lambda doc, meta: f"anchor:{meta['subtopic']}:{doc}")
    monkeypatch.setattr(memory_retrieval, "_collect_user_memory_facts", fake_collect_user)
    monkeypatch.setattr(memory_retrieval, "_collect_legacy_forgettable_facts", lambda: ["legacy-extra"])

    permanent, long_term, legacy = memory_retrieval._collect_user_and_shared_facts(
        plan(use_shared=True, use_short_term=True),
        "ds3000 week1",
        {"user_memories": FakeFuture((["doc"], [{"topic": "x"}], [0.1]))},
    )

    assert permanent == ["permanent"]
    assert long_term == ["anchor:week1:anchor-doc", "long-term"]
    assert legacy == ["legacy-user", "legacy-extra"]
    assert captured == {
        "docs": ["doc"],
        "metas": [{"topic": "x"}],
        "distances": [0.1],
        "anchors": ["anchor-doc"],
    }


def test_collect_user_and_shared_facts_returns_empty_for_unused_plan():
    assert memory_retrieval._collect_user_and_shared_facts(
        plan(),
        "query",
        {},
    ) == ([], [], [])


def test_collect_section_facts_forwards_future_result_to_collector():
    calls = []

    def collector(docs, metas, distances, *, max_distance):
        calls.append((docs, metas, distances, max_distance))
        return ["collected"]

    assert memory_retrieval._collect_section_facts(
        {"section": FakeFuture((["doc"], [{"topic": "x"}], [0.2]))},
        "section",
        collector,
        max_distance=0.4,
    ) == ["collected"]
    assert calls == [(["doc"], [{"topic": "x"}], [0.2], 0.4)]


def test_collect_non_user_section_facts_uses_source_collectors(monkeypatch):
    calls = []

    def fake_collect(label):
        def _collector(docs, metas, distances, **kwargs):
            calls.append((label, docs, metas, distances, kwargs))
            return [label]
        return _collector

    monkeypatch.setattr(memory_retrieval, "_collect_jane_long_term_facts", fake_collect("jane"))
    monkeypatch.setattr(memory_retrieval, "_collect_short_term_semantic_facts", fake_collect("short"))
    monkeypatch.setattr(memory_retrieval, "_apply_short_term_recency_boost", lambda facts: facts + ["recent"])
    monkeypatch.setattr(memory_retrieval, "_collect_file_index_facts", fake_collect("file"))
    monkeypatch.setattr(memory_retrieval, "_collect_essence_facts", fake_collect("essence"))

    facts = memory_retrieval._collect_non_user_section_facts(
        plan(
            use_jane_long_term=True,
            use_short_term=True,
            use_file_index=True,
            use_essence=True,
        ),
        {
            "jane_long_term": FakeFuture((["jdoc"], [{"topic": "j"}], [0.1])),
            "short_term": FakeFuture((["sdoc"], [{"topic": "s"}], [0.2])),
            "file_index": FakeFuture((["fdoc"], [{"topic": "f"}], [0.3])),
            "essence": FakeFuture((["edoc"], [{"topic": "e"}], [0.4])),
        },
    )

    assert facts == (["jane"], ["short", "recent"], ["file"], ["essence"])
    assert [call[0] for call in calls] == ["jane", "short", "file", "essence"]


def test_collect_non_user_section_facts_returns_empty_for_unused_plan():
    assert memory_retrieval._collect_non_user_section_facts(plan(), {}) == (
        [],
        [],
        [],
        [],
    )
