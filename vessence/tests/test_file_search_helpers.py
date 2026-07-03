from jane_web.file_search_helpers import (
    description_excerpt,
    file_matches_type,
    file_search_result,
    filename_search_results,
    merge_index_search_results,
    normalize_index_path,
    row_scope_allowed,
)


def test_file_matches_type_uses_extension_set_case_insensitively():
    assert file_matches_type("Report.PDF", {".pdf"})
    assert not file_matches_type("photo.png", {".pdf"})
    assert file_matches_type("anything.bin", None)


def test_normalize_index_path_handles_empty_absolute_and_escape_paths():
    assert normalize_index_path("", "/vault") is None
    assert normalize_index_path("/vault/docs/a.md", "/vault") == "docs/a.md"
    assert normalize_index_path("../outside.md", "/vault") is None
    assert normalize_index_path("..outside.md", "/vault") is None
    assert normalize_index_path("docs/a.md", "/vault") == "docs/a.md"


def test_row_scope_allowed_preserves_managed_user_scope_rules():
    assert row_scope_allowed({}, None)
    assert row_scope_allowed({}, "child")
    assert row_scope_allowed({"user_id": "child"}, "child")
    assert not row_scope_allowed({"user_id": "other"}, "child")


def test_description_excerpt_and_file_search_result_shape():
    assert description_excerpt("x" * 250) == "x" * 200

    assert file_search_result(
        name="notes.md",
        path="docs/notes.md",
        description="meeting notes",
        detect_file_type=lambda name: "document",
    ) == {
        "name": "notes.md",
        "path": "docs/notes.md",
        "type": "document",
        "description": "meeting notes",
        "serve_url": "/api/files/serve/docs/notes.md",
    }


def test_filename_search_results_walks_vault_and_filters_hidden_type_and_query(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "Notes.md").write_text("notes", encoding="utf-8")
    (docs / ".hidden.md").write_text("hidden", encoding="utf-8")
    (docs / "Notes.png").write_text("image", encoding="utf-8")
    (docs / "other.txt").write_text("other", encoding="utf-8")

    results = filename_search_results(
        vault_root=str(tmp_path),
        query="notes",
        type_exts={".md"},
        detect_file_type=lambda name: "document",
    )

    assert results == {
        "docs/Notes.md": {
            "name": "Notes.md",
            "path": "docs/Notes.md",
            "type": "document",
            "description": "",
            "serve_url": "/api/files/serve/docs/Notes.md",
        }
    }


def test_merge_index_search_results_adds_existing_files_and_enriches_filename_hits(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "notes.md").write_text("notes", encoding="utf-8")
    (docs_dir / "other.md").write_text("other", encoding="utf-8")
    results = {
        "docs/notes.md": {
            "name": "notes.md",
            "path": "docs/notes.md",
            "type": "document",
            "description": "",
            "serve_url": "/api/files/serve/docs/notes.md",
        }
    }

    merge_index_search_results(
        results,
        ["notes description", "other description", "missing", "wrong scope"],
        [
            {"path": "docs/notes.md", "user_id": "child"},
            {"file": "docs/other.md", "user_id": "child"},
            {"path": "docs/missing.md", "user_id": "child"},
            {"path": "docs/secret.md", "user_id": "other"},
        ],
        vault_root=str(tmp_path),
        type_exts={".md"},
        allowed_scope="child",
        detect_file_type=lambda name: "document",
    )

    assert results["docs/notes.md"]["description"] == "notes description"
    assert results["docs/other.md"] == {
        "name": "other.md",
        "path": "docs/other.md",
        "type": "document",
        "description": "other description",
        "serve_url": "/api/files/serve/docs/other.md",
    }
    assert "docs/missing.md" not in results
    assert "docs/secret.md" not in results
