from agent_skills import fetch_todo_list
from agent_skills.todo_doc_helpers import (
    build_todo_cache_payload,
    decode_doc_body,
    export_url,
    is_category_header,
    is_login_wall_body,
    is_todo_title_line,
    list_item_text,
    next_nonblank_index,
    parse_categories,
    strip_doc_bom,
    todo_item_count,
)


def test_fetch_todo_list_exposes_helper_parser_and_export_url():
    assert fetch_todo_list.parse_categories is parse_categories
    assert fetch_todo_list._export_url is export_url


def test_parse_category_line_helpers_preserve_marker_and_header_rules():
    lines = ["Home", "", "- Dishes", "Footer"]

    assert strip_doc_bom("\ufeffTODO list") == "TODO list"
    assert strip_doc_bom("TODO list") == "TODO list"
    assert is_todo_title_line(0, "Todo List")
    assert not is_todo_title_line(1, "Todo List")
    assert list_item_text("  2) Call the office") == "Call the office"
    assert list_item_text("Footer") is None
    assert next_nonblank_index(lines, 1) == 2
    assert is_category_header(lines, 0)
    assert not is_category_header(lines, 2)


def test_parse_categories_handles_titles_headers_markers_and_noise():
    text = (
        "\ufeffTODO list\n"
        "\n"
        "Intro prose ignored\n"
        "\n"
        "Do it Immediately\n"
        "1. Deal with email\n"
        "2) Call the office\n"
        "\n"
        "For the clinic\n"
        "- Curtain rods\n"
        "* Inventory towels\n"
        "• Pay utility bill\n"
        "\n"
        "Footer prose ignored\n"
    )

    assert parse_categories(text) == [
        {"name": "Do it Immediately", "items": ["Deal with email", "Call the office"]},
        {
            "name": "For the clinic",
            "items": ["Curtain rods", "Inventory towels", "Pay utility bill"],
        },
    ]


def test_parse_categories_attaches_orphan_items_to_uncategorized():
    assert parse_categories("1. Orphan task\n\nHome\n- Dishes\n") == [
        {"name": "Uncategorized", "items": ["Orphan task"]},
        {"name": "Home", "items": ["Dishes"]},
    ]


def test_login_wall_detection_samples_initial_body_only():
    assert is_login_wall_body("prefix <HTML><body>Sign in - Google Accounts</body>")
    assert not is_login_wall_body("safe" + ("x" * 2000) + "<html>")


def test_decode_doc_body_replaces_invalid_utf8():
    assert decode_doc_body(b"valid") == "valid"
    assert decode_doc_body(b"bad: \xff").startswith("bad: ")


def test_cache_payload_and_item_count():
    categories = [{"name": "Home", "items": ["Dishes", "Laundry"]}]

    assert todo_item_count(categories) == 2
    assert build_todo_cache_payload(
        categories,
        "raw text",
        "doc123",
        fetched_at="2026-07-02T12:00:00Z",
    ) == {
        "fetched_at": "2026-07-02T12:00:00Z",
        "doc_id": "doc123",
        "source_url": "https://docs.google.com/document/d/doc123/export?format=txt",
        "categories": categories,
        "raw_text": "raw text",
    }
