from jane_web.canonical_docs import (
    CANONICAL_DOCS_WHITELIST,
    read_doc_body,
    read_doc_meta,
)


def test_canonical_docs_whitelist_preserves_public_slugs():
    assert list(CANONICAL_DOCS_WHITELIST) == [
        "architecture",
        "memory",
        "skills",
        "todos",
        "accomplishments",
        "cron",
    ]


def test_read_doc_meta_stats_whitelisted_file_without_body(tmp_path):
    whitelist = {"guide": {"file": "guide.md", "title": "Guide"}}
    path = tmp_path / "guide.md"
    path.write_text("hello", encoding="utf-8")

    meta = read_doc_meta("guide", whitelist=whitelist, config_dir=tmp_path)

    assert meta == {
        "slug": "guide",
        "title": "Guide",
        "file": "guide.md",
        "bytes": 5,
        "last_modified": int(path.stat().st_mtime),
    }


def test_read_doc_body_includes_content_and_metadata(tmp_path):
    whitelist = {"guide": {"file": "guide.md", "title": "Guide"}}
    path = tmp_path / "guide.md"
    path.write_text("# Guide\n", encoding="utf-8")

    body = read_doc_body("guide", whitelist=whitelist, config_dir=tmp_path)

    assert body == {
        "slug": "guide",
        "title": "Guide",
        "file": "guide.md",
        "content": "# Guide\n",
        "bytes": 8,
        "last_modified": int(path.stat().st_mtime),
    }


def test_read_doc_helpers_return_none_for_unknown_or_missing_docs(tmp_path):
    whitelist = {"guide": {"file": "missing.md", "title": "Guide"}}

    assert read_doc_meta("unknown", whitelist=whitelist, config_dir=tmp_path) is None
    assert read_doc_body("unknown", whitelist=whitelist, config_dir=tmp_path) is None
    assert read_doc_meta("guide", whitelist=whitelist, config_dir=tmp_path) is None
    assert read_doc_body("guide", whitelist=whitelist, config_dir=tmp_path) is None
