from agent_skills import docs_tools
from agent_skills.docs_editing_helpers import (
    TodoAddSectionScan,
    TodoRemoveItemScan,
    build_insert_text_request,
    build_replace_all_text_request,
    build_todo_category_section,
    extract_text,
    find_end_of_section,
    plan_todo_add_item,
    plan_todo_remove_item,
    scan_todo_add_section,
    scan_todo_remove_item,
    todo_category_exists,
)


def test_docs_tools_keeps_private_helper_aliases():
    assert docs_tools._extract_text is extract_text
    assert docs_tools._find_end_of_section is find_end_of_section


def test_extract_text_walks_google_docs_body_text_runs():
    body = {
        "content": [
            {
                "paragraph": {
                    "elements": [
                        {"textRun": {"content": "Hello"}},
                        {"textRun": {"content": " world\n"}},
                        {"inlineObjectElement": {}},
                    ]
                }
            },
            {"table": {}},
        ]
    }

    assert extract_text(body) == "Hello world\n"


def test_find_end_of_section_stops_before_next_header():
    text = "Home\n1. Dishes\n2. Laundry\nWork\n- Email\n"

    assert find_end_of_section(text, "home") == len("Home\n1. Dishes\n2. Laundry\n")


def test_batch_update_request_builders_match_docs_api_shapes():
    assert build_insert_text_request(42, "hello") == {
        "insertText": {
            "location": {"index": 42},
            "text": "hello",
        }
    }
    assert build_replace_all_text_request("old", "new") == {
        "replaceAllText": {
            "containsText": {
                "text": "old",
                "matchCase": True,
            },
            "replaceText": "new",
        }
    }


def test_plan_todo_add_item_preserves_numbered_list_behavior():
    text = "Home\n1. Dishes\n2. Laundry\n\nWork\nCall Bob\n"

    plan = plan_todo_add_item(text, "Vacuum", "Home")

    assert scan_todo_add_section(text, "Home") == TodoAddSectionScan(
        found_section=True,
        insert_after_line="2. Laundry",
        numbered_insert_line="2. Laundry",
        last_item_num=2,
    )
    assert plan is not None
    assert plan.old_text == "2. Laundry"
    assert plan.new_text == "2. Laundry\n3. Vacuum"
    assert plan.success_message == "Added item #3 to Home: Vacuum"
    assert plan.failure_message == "Failed to add item to Home."


def test_plan_todo_add_item_preserves_plain_and_empty_section_behavior():
    plain_plan = plan_todo_add_item("Home\nDishes\nLaundry\n\n", "Vacuum", "Home")
    empty_plan = plan_todo_add_item("Home\n\nWork\n1. Email\n", "Vacuum", "Home")

    assert scan_todo_add_section("Home\n\nWork\n1. Email\n", "Home") == TodoAddSectionScan(
        found_section=True,
        insert_after_line="1. Email",
        numbered_insert_line="1. Email",
        last_item_num=1,
    )
    assert plain_plan is not None
    assert plain_plan.old_text == "Laundry"
    assert plain_plan.new_text == "Laundry\nVacuum"
    assert plain_plan.success_message == "Added item to Home: Vacuum"
    assert empty_plan is not None
    assert empty_plan.old_text == "1. Email"
    assert empty_plan.new_text == "1. Email\n2. Vacuum"


def test_plan_todo_add_item_returns_none_for_missing_category():
    assert plan_todo_add_item("Home\nDishes\n", "Vacuum", "Work") is None
    assert scan_todo_add_section("Home\nDishes\n", "Work") == TodoAddSectionScan(
        found_section=False,
        insert_after_line=None,
        numbered_insert_line=None,
        last_item_num=0,
    )


def test_plan_todo_remove_item_strips_list_marker_for_match_and_message():
    text = "Home\n- Dishes\n2. Laundry\n\nWork\n- Email\n"

    plan = plan_todo_remove_item(text, "lau", "Home")

    assert scan_todo_remove_item(text, "lau", "Home") == TodoRemoveItemScan(
        line="2. Laundry",
        item_body="Laundry",
    )
    assert plan is not None
    assert plan.old_text == "2. Laundry\n"
    assert plan.new_text == ""
    assert plan.success_message == "Removed: Laundry"
    assert plan.failure_message == "Found the item but failed to delete it."


def test_plan_todo_remove_item_without_category_scans_whole_doc():
    plan = plan_todo_remove_item("Home\n- Dishes\n\nWork\n- Email\n", "email")

    assert scan_todo_remove_item("Home\n- Dishes\n\nWork\n- Email\n", "email") == TodoRemoveItemScan(
        line="- Email",
        item_body="Email",
    )
    assert plan is not None
    assert plan.old_text == "- Email\n"
    assert plan.success_message == "Removed: Email"
    assert scan_todo_remove_item("Home\n- Dishes\n", "missing") is None


def test_category_helpers_preserve_existing_matching_and_placeholder_text():
    text = "Home\n- Dishes\n\nWork\n- Email\n"

    assert todo_category_exists(text, " work ")
    assert not todo_category_exists(text, "Errands")
    assert build_todo_category_section("Errands") == "\n\nErrands\n1. Nothing\n"
