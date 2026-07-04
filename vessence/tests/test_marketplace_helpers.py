from datetime import datetime
from pathlib import Path

from jane_web.marketplace_helpers import (
    is_safe_listing_key,
    is_safe_marketplace_name,
    is_safe_photo_name,
    marketplace_create_search_payload,
    marketplace_refresh_command,
    marketplace_refresh_env,
    marketplace_refresh_log_header,
    marketplace_refresh_log_path,
)


def test_marketplace_name_validation_matches_route_contract():
    assert is_safe_marketplace_name("chairs_2026")
    assert is_safe_marketplace_name("a" * 40)
    assert not is_safe_marketplace_name("Chairs")
    assert not is_safe_marketplace_name("a" * 41)
    assert not is_safe_marketplace_name("../chairs")


def test_listing_key_validation_checks_slug_and_numeric_id():
    assert is_safe_listing_key("ikea-chair_1", "123456")
    assert not is_safe_listing_key("Ikea", "123456")
    assert not is_safe_listing_key("ikea", "123")
    assert not is_safe_listing_key("ikea", "12abc")


def test_photo_name_validation_matches_existing_photo_pattern():
    assert is_safe_photo_name("photo_01.jpg")
    assert is_safe_photo_name("photo_123.webp")
    assert not is_safe_photo_name("photo_1.jpg")
    assert not is_safe_photo_name("photo_001.gif")
    assert not is_safe_photo_name("../photo_01.jpg")


def test_marketplace_create_search_payload_normalizes_values():
    payload = marketplace_create_search_payload(
        {
            "name": "  chairs  ",
            "label": "Dining Chairs",
            "queries": [" chair ", "", 42],
            "filters": {"max_price": 40},
            "location_id": "",
        },
        default_location_id="boston",
    )

    assert payload == {
        "name": "chairs",
        "label": "Dining Chairs",
        "queries": ["chair", "42"],
        "raw_queries_valid": True,
        "filters": {"max_price": 40},
        "location_id": "boston",
    }


def test_marketplace_create_search_payload_preserves_raw_query_validation_order():
    assert marketplace_create_search_payload(
        {"name": "chairs", "queries": ["   "]},
        default_location_id="boston",
    )["raw_queries_valid"] is True
    assert marketplace_create_search_payload(
        {"name": "chairs", "queries": []},
        default_location_id="boston",
    )["raw_queries_valid"] is False
    assert marketplace_create_search_payload(
        {"name": "chairs", "queries": "chair"},
        default_location_id="boston",
    )["raw_queries_valid"] is False


def test_marketplace_refresh_launch_helpers_preserve_route_values():
    assert marketplace_refresh_command("/python", "chairs") == [
        "/python",
        "-m",
        "agent_skills.marketplace.refresh",
        "chairs",
    ]
    assert marketplace_refresh_env(
        {
            "DISPLAY": ":0",
            "WAYLAND_DISPLAY": "wayland-1",
            "KEEP": "yes",
        }
    ) == {"KEEP": "yes"}
    assert marketplace_refresh_log_path("/data", "chairs") == Path(
        "/data/logs/marketplace_refresh_chairs.log"
    )
    assert marketplace_refresh_log_header(
        "chairs",
        datetime(2026, 7, 3, 12, 34, 56, 900),
    ) == "\n=== manual refresh chairs at 2026-07-03T12:34:56 ===\n"
