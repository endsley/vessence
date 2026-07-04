from jane_web.jane_v2.classes.todo_list import handler
from jane_web.jane_v2.classes.todo_list.categories import (
    category_list_label,
    category_by_name_or_alias,
    direct_category_query,
    friendly_category_name,
    match_category,
    normalize,
    speak_category_list,
    speak_items,
    visible_categories,
)


def _categories() -> list[dict]:
    return [
        {"name": "Do it Immediately", "items": ["pay taxes"]},
        {"name": "For my students", "items": ["grade projects"]},
        {"name": "For our Home", "items": ["buy milk"]},
        {"name": "For the clinic", "items": ["order forms"]},
        {"name": "Ambient project goals", "items": ["refactor"]},
        {"name": "Jane", "items": ["internal note"]},
    ]


def test_handler_uses_extracted_category_helpers() -> None:
    assert handler._match_category is match_category
    assert handler._speak_items is speak_items
    assert handler._category_by_name_or_alias is category_by_name_or_alias


def test_normalize_and_visible_categories_hide_internal_sections() -> None:
    assert normalize("\ufeff Clinic!!") == "clinic"
    assert [category["name"] for category in visible_categories(_categories())] == [
        "Do it Immediately",
        "For my students",
        "For our Home",
        "For the clinic",
    ]


def test_match_category_accepts_names_short_aliases_and_ordinals() -> None:
    categories = _categories()
    assert match_category("what is on my For the clinic list?", categories)["name"] == "For the clinic"
    assert match_category("clinic", categories)["name"] == "For the clinic"
    assert match_category("second", categories)["name"] == "For my students"
    assert match_category("2", categories)["name"] == "For my students"


def test_category_by_name_or_alias_matches_exact_names_and_aliases() -> None:
    categories = _categories()

    assert category_by_name_or_alias("For the clinic", categories)["name"] == "For the clinic"
    assert category_by_name_or_alias("clinic", categories)["name"] == "For the clinic"
    assert category_by_name_or_alias("urgent", categories)["name"] == "Do it Immediately"
    assert category_by_name_or_alias("", categories) is None
    assert category_by_name_or_alias("not a category", categories) is None


def test_match_category_ignores_incidental_aliases_in_long_prompts() -> None:
    categories = _categories()
    prompt = "I was thinking about stage 2 and students but this is not a category reply"
    assert match_category(prompt, categories) is None


def test_direct_category_query_reuses_category_matching() -> None:
    assert direct_category_query("what is on my home list", _categories())["name"] == "For our Home"


def test_friendly_category_name_and_item_speech() -> None:
    assert friendly_category_name("Do it Immediately") == "your urgent list"
    assert friendly_category_name("For the clinic") == "the clinic"
    assert category_list_label("Do it Immediately") == "the urgent stuff"
    assert category_list_label("For the clinic") == "the clinic"
    assert category_list_label("For our Home") == "home"
    assert category_list_label("For my Students") == "students"

    assert speak_items({"name": "For our Home", "items": []}) == "Nothing logged under home yet."
    assert speak_items({"name": "For my students", "items": ["Grade essays."]}) == (
        "For students: Grade essays."
    )
    assert speak_items({"name": "For the clinic", "items": ["Order forms.", "Call vendor"]}) == (
        "Two things for the clinic. First, Order forms. And second, Call vendor."
    )
    assert speak_items({"name": "Do it Immediately", "items": ["Pay bill.", "Book visit.", "Email Sam"]}) == (
        "3 items for your urgent list. Pay bill; Book visit; and finally, Email Sam."
    )


def test_speak_category_list_filters_empty_and_internal_categories() -> None:
    categories = _categories()
    categories[1]["items"] = []

    assert speak_category_list(categories) == (
        "3 categories: the urgent stuff, home, and the clinic. "
        "Which one do you want to hear?"
    )
    assert speak_category_list([{"name": "Jane", "items": ["internal note"]}]) == (
        "Your list is empty right now."
    )
