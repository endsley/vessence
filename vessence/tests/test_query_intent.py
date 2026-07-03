from memory.v1 import query_intent


def test_is_file_index_record_detects_metadata_and_text_shapes():
    assert query_intent.is_file_index_record("anything", {"topic": "vault_file"})
    assert query_intent.is_file_index_record("anything", {"subtopic": "vault_file"})
    assert query_intent.is_file_index_record("anything", {"memory_type": "file_index"})
    assert query_intent.is_file_index_record("anything", {"source": "vault"})
    assert query_intent.is_file_index_record("Vault file: notes.md", {})
    assert query_intent.is_file_index_record("Saved file 'report.pdf'", {})
    assert query_intent.is_file_index_record("The user has and stores a file stored at /home/chieh/ambient/vault/a.md", {})
    assert query_intent.is_file_index_record("Metadata location: Documents/plan.docx", {})
    assert not query_intent.is_file_index_record("ordinary memory", {"topic": "preference"})


def test_is_file_query_uses_static_and_dynamic_markers(monkeypatch):
    monkeypatch.setattr(query_intent, "get_file_markers", lambda: ("custom marker",))

    assert query_intent.is_file_query("Where did I save that PDF?")
    assert query_intent.is_file_query("Please find custom marker")
    assert not query_intent.is_file_query("What did we decide about dinner?")


def test_classify_query_intent_priority_and_fallbacks(monkeypatch):
    monkeypatch.setattr(query_intent, "get_file_markers", lambda: ())
    monkeypatch.setattr(query_intent, "get_project_markers", lambda: ("refactor",))
    monkeypatch.setattr(query_intent, "get_personal_markers", lambda: ("favorite",))

    assert query_intent.classify_query_intent("refactor this file") == "file_lookup"
    assert query_intent.classify_query_intent("continue refactor work") == "project_work"
    assert query_intent.classify_query_intent("favorite restaurant") == "personal_lookup"
    assert query_intent.classify_query_intent("who is amy?") == "personal_lookup"
    assert query_intent.classify_query_intent("explain distributed locks in general") == "general"


def test_ds3000_lecture_subtopics_parses_numbers_suffixes_and_series_markers():
    assert query_intent.ds3000_lecture_subtopics(
        "DS3000 lecture 03a, lecture 4, appendix, and series index"
    ) == ["lecture_3a", "lecture_4", "appendix", "series_index"]
    assert query_intent.ds3000_lecture_subtopics("lecture 2 lecture 2") == ["lecture_2"]
    assert query_intent.ds3000_lecture_subtopics("DS3000 lecture 00 and lecture 100") == []
    assert query_intent.ds3000_lecture_subtopics("appendix only") == []
