"""SHOPPING_LIST — add/remove/show/check shopping list items."""

CLASS_NAME = "SHOPPING_LIST"
NEEDS_LLM = True

EXAMPLES = [
    "add milk to the list", "add eggs to my shopping list",
    "add bread and butter", "add bananas to the grocery list",
    "put coffee on the list", "put apples on my list",
    "I need to get milk", "I need to pick up some eggs",
    "don't forget the butter", "remind me to buy laundry detergent",
    "remove milk from the list", "take eggs off the list",
    "I already got the bread", "I bought the milk",
    "what's on my shopping list", "read me the shopping list",
    "show me my grocery list", "what do I need to buy",
    "what's on the list", "check the shopping list",
    "add chicken and rice to the list", "add cereal to the list",
    "put cheese on the list", "add some pasta",
    "I need toilet paper", "add dish soap",
    "add sparkling water", "put orange juice on the list",
    "add ketchup and mustard", "add some fruit",
    "remove the bread I already have it", "take cheese off the list",
    "add toothpaste", "add shampoo to the grocery list",
    "put yogurt on the list", "add some snacks",
    "clear the shopping list", "clear the list",
    "add avocado", "add some vegetables",
    "I need paper towels", "add paper towels to the list",
    "add two gallons of milk", "add a dozen eggs",
    "put frozen pizza on the list", "add some juice",
    "add nuts and granola", "put oat milk on the list",
    "add tomatoes and onions", "what do I still need to buy",
]

CONTEXT = """\
The user wants to add, remove, or view their shopping/grocery list.
Output exactly:
CLASSIFICATION: SHOPPING_LIST
ACTION: <verb + item, e.g. "add milk" or "remove eggs" or "show list">"""
