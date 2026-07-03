import pytest

from jane_web.briefing_articles import build_briefing_articles_response


def test_build_briefing_articles_response_normalizes_categories_and_image_urls():
    cards = [
        {
            "id": "a1",
            "topic": "Health",
            "tags": ["RA", "Clinical"],
            "image_path": "/tmp/a1.png",
            "full_summary": "long",
        },
        {
            "id": "a2",
            "topic": "Markets",
            "categories": ["Finance"],
            "image_path": "/tmp/a2.png",
            "image_url": "/custom",
        },
    ]

    response = build_briefing_articles_response(cards)

    assert response == {
        "status": "ok",
        "cards": [
            {
                "id": "a1",
                "topic": "Health",
                "tags": ["RA", "Clinical"],
                "categories": ["RA", "Clinical"],
                "image_path": "/tmp/a1.png",
                "image_url": "/api/briefing/image/a1",
            },
            {
                "id": "a2",
                "topic": "Markets",
                "categories": ["Finance"],
                "image_path": "/tmp/a2.png",
                "image_url": "/custom",
            },
        ],
        "card_count": 2,
        "total": 2,
        "offset": 0,
        "limit": 2,
        "has_more": False,
        "categories": ["Clinical", "Finance", "RA"],
    }


def test_build_briefing_articles_response_filters_saved_view_and_topic_case_insensitively():
    cards = [
        {"id": "a1", "topic": "Health", "state": "saved", "categories": ["A"]},
        {"id": "a2", "topic": "health", "state": "new", "categories": ["B"]},
        {"id": "a3", "topic": "Markets", "state": "saved", "categories": ["C"]},
    ]

    saved = build_briefing_articles_response(cards, view="saved")
    by_topic = build_briefing_articles_response(cards, topic="HEALTH")

    assert [card["id"] for card in saved["cards"]] == ["a1", "a3"]
    assert saved["categories"] == ["A", "C"]
    assert [card["id"] for card in by_topic["cards"]] == ["a1", "a2"]
    assert by_topic["categories"] == ["A", "B"]


def test_build_briefing_articles_response_paginates_and_strips_only_returned_page():
    cards = [
        {"id": "a1", "topic": "T", "full_summary": "one"},
        {"id": "a2", "topic": "T", "full_summary": "two"},
        {"id": "a3", "topic": "T", "full_summary": "three"},
    ]

    response = build_briefing_articles_response(cards, limit="1", offset="1")

    assert response["cards"] == [{"id": "a2", "topic": "T", "categories": ["T"]}]
    assert response["card_count"] == 1
    assert response["total"] == 3
    assert response["offset"] == 1
    assert response["limit"] == 1
    assert response["has_more"] is True
    assert "full_summary" in cards[0]
    assert "full_summary" not in cards[1]
    assert "full_summary" in cards[2]


def test_build_briefing_articles_response_rejects_bad_pagination_values():
    with pytest.raises(ValueError, match="limit/offset must be integers"):
        build_briefing_articles_response([], limit="bad", offset=0)
