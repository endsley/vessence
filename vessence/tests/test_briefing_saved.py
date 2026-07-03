from pathlib import Path

from jane_web.briefing_saved import (
    daily_briefing_article_path,
    saved_article_list,
    saved_article_record,
    saved_articles_index_path,
    saved_category_names,
    vault_saved_article_path,
)


def test_saved_article_paths_match_existing_route_layout():
    assert saved_articles_index_path(Path("/data/briefing_saved")) == Path("/data/briefing_saved/saved.json")
    assert daily_briefing_article_path("/tools", "a1") == Path(
        "/tools/daily_briefing/essence_data/articles/a1.json"
    )
    assert vault_saved_article_path(Path("/vault/saved_articles"), "Health", "a1") == Path(
        "/vault/saved_articles/Health/a1.json"
    )


def test_saved_article_record_shape_preserves_article_data():
    article = {"title": "A", "tags": ["x"]}

    assert saved_article_record("a1", "Health", "2026-07-02T10:00:00+00:00", article) == {
        "article_id": "a1",
        "category": "Health",
        "saved_at": "2026-07-02T10:00:00+00:00",
        "article": article,
    }


def test_saved_category_names_combines_vault_dirs_and_index_defaults():
    saved = {
        "a1": {"category": "Health"},
        "a2": {},
        "a3": {"category": "Finance"},
    }

    assert saved_category_names(["Health", "Research"], saved) == [
        "Finance",
        "Health",
        "Research",
        "Uncategorized",
    ]


def test_saved_article_list_filters_and_sorts_by_saved_at_descending():
    saved = {
        "old": {"article_id": "old", "category": "Health", "saved_at": "2026-01-01"},
        "new": {"article_id": "new", "category": "Health", "saved_at": "2026-02-01"},
        "other": {"article_id": "other", "category": "Finance", "saved_at": "2026-03-01"},
    }

    assert [item["article_id"] for item in saved_article_list(saved)] == ["other", "new", "old"]
    assert [item["article_id"] for item in saved_article_list(saved, "Health")] == ["new", "old"]
