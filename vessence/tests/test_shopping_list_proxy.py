from jane_web.shopping_list_proxy import (
    ShoppingListProxyAction,
    parse_shopping_list_proxy_action,
    shopping_list_legacy_response,
    shopping_list_v2_task_context,
)


def test_parse_shopping_list_proxy_action_adds_items_to_named_stores():
    assert parse_shopping_list_proxy_action("add milk").__dict__ == {
        "kind": "add",
        "item": "milk",
        "store": "default",
    }
    assert parse_shopping_list_proxy_action("add paper towels to walmart").__dict__ == {
        "kind": "add",
        "item": "paper towels",
        "store": "walmart",
    }
    assert parse_shopping_list_proxy_action("add eggs to the target list").__dict__ == {
        "kind": "add",
        "item": "eggs",
        "store": "target",
    }


def test_parse_shopping_list_proxy_action_removes_without_truncating_store_names():
    assert parse_shopping_list_proxy_action("remove soap from walmart").__dict__ == {
        "kind": "remove",
        "item": "soap",
        "store": "walmart",
    }
    assert parse_shopping_list_proxy_action("remove rice from the costco list").__dict__ == {
        "kind": "remove",
        "item": "rice",
        "store": "costco",
    }


def test_parse_shopping_list_proxy_action_clear_and_unknown_shapes():
    assert parse_shopping_list_proxy_action("clear").__dict__ == {
        "kind": "clear",
        "item": "",
        "store": "default",
    }
    assert parse_shopping_list_proxy_action("clear costco").__dict__ == {
        "kind": "clear",
        "item": "",
        "store": "costco",
    }
    assert parse_shopping_list_proxy_action("show me my list") is None


def test_shopping_list_proxy_response_helpers_preserve_text_styles():
    add = ShoppingListProxyAction(kind="add", item="milk", store="walmart")
    remove = ShoppingListProxyAction(kind="remove", item="soap", store="costco")
    clear = ShoppingListProxyAction(kind="clear", item="", store="default")

    assert shopping_list_v2_task_context(add, ["milk", "eggs"]) == (
        "Added 'milk' to the walmart list. Current list: milk, eggs"
    )
    assert shopping_list_v2_task_context(remove, []) == (
        "Removed 'soap' from the costco list. Current list: (empty)"
    )
    assert shopping_list_v2_task_context(clear) == "Cleared the default shopping list."

    assert shopping_list_legacy_response(add, ["milk", "eggs"]) == (
        "Added **milk** to the walmart list. Current list: milk, eggs"
    )
    assert shopping_list_legacy_response(remove, []) == (
        "Removed **soap** from the costco list. Current list: (empty)"
    )
    assert shopping_list_legacy_response(clear) == "Cleared the default shopping list."
