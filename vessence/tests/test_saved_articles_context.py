import json

from context_builder.v1 import saved_articles_context as saved


def test_article_query_terms_filters_saved_article_stop_words():
    assert saved.article_query_terms("What does the saved article say about remission monitoring?") == {
        "remission",
        "monitoring",
        "say",
        "the",
    }


def test_score_saved_article_weights_title_and_metadata_above_body():
    entry = {"category": "Health"}
    article = {
        "title": "Remission target",
        "brief_summary": "remission appears here too",
        "full_text": "monitoring only appears in body",
    }

    assert saved.score_saved_article({"remission", "monitoring"}, entry, article) == 5


def test_build_saved_articles_context_selects_relevant_inline_article(tmp_path, monkeypatch):
    data_home = tmp_path / "data"
    index_dir = data_home / "briefing_saved"
    index_dir.mkdir(parents=True)
    (index_dir / "saved.json").write_text(
        json.dumps(
            {
                "a1": {
                    "article_id": "a1",
                    "category": "Health",
                    "saved_at": "2026-07-02T10:00:00",
                    "article": {
                        "title": "RA remission monitoring",
                        "source": "Journal",
                        "url": "https://example.test/a1",
                        "brief_summary": "Track CDAI remission and medication safety.",
                    },
                },
                "a2": {
                    "article_id": "a2",
                    "category": "Sports",
                    "saved_at": "2026-07-02T11:00:00",
                    "article": {"title": "Soccer scores", "brief_summary": "Unrelated."},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(data_home))

    context = saved.build_saved_articles_context("what did the saved article say about remission?")

    assert "RA remission monitoring" in context
    assert "Track CDAI remission" in context
    assert "Soccer scores" not in context


def test_load_saved_article_entry_article_reads_external_article_file(tmp_path, monkeypatch):
    tools_dir = tmp_path / "skills"
    article_dir = tools_dir / "daily_briefing" / "essence_data" / "articles"
    article_dir.mkdir(parents=True)
    (article_dir / "a1.json").write_text('{"title": "External"}', encoding="utf-8")
    monkeypatch.setenv("TOOLS_DIR", str(tools_dir))

    assert saved.load_saved_article_entry_article({"article_id": "a1"}) == {"title": "External"}
    assert saved.load_saved_article_entry_article({"article_id": "../bad"}) == {}
