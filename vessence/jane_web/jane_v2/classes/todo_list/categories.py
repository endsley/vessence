"""Category matching and speech helpers for the TODO-list handler."""
from __future__ import annotations

import re


CATEGORY_ALIASES = {
    "immediately": "Do it Immediately",
    "urgent": "Do it Immediately",
    "asap": "Do it Immediately",
    "student": "For my students",
    "students": "For my students",
    "school": "For my students",
    "teaching": "For my students",
    "home": "For our Home",
    "house": "For our Home",
    "household": "For our Home",
    "clinic": "For the clinic",
    "kathia": "For the clinic",
    "water lily": "For the clinic",
}

SHORT_REPLY_WORDS = 10
EXCLUDED_CATEGORY_NAMES = {"ambient project goals", "jane"}


def normalize(value: str) -> str:
    value = (value or "").lstrip("\ufeff").lower().strip().strip(".!?,")
    return re.sub(r"\s+", " ", value)


def visible_categories(categories: list[dict]) -> list[dict]:
    """Filter out categories this handler does not answer from."""
    return [
        category for category in categories
        if normalize(category.get("name", "")) not in EXCLUDED_CATEGORY_NAMES
    ]


def category_by_name_or_alias(category_name: str, categories: list[dict]) -> dict | None:
    norm_target = normalize(category_name)
    if not norm_target:
        return None
    for category in categories:
        if normalize(category.get("name", "")) == norm_target:
            return category
    for alias, canonical in CATEGORY_ALIASES.items():
        if normalize(alias) != norm_target:
            continue
        for category in categories:
            if normalize(category.get("name", "")) == normalize(canonical):
                return category
    return None


def match_category(prompt: str, categories: list[dict]) -> dict | None:
    """Return the best-matching category dict or None if ambiguous."""
    if not categories:
        return None
    categories = visible_categories(categories)
    prompt_norm = normalize(prompt)
    is_short = len(prompt_norm.split()) <= SHORT_REPLY_WORDS

    for category in categories:
        if normalize(category.get("name", "")) in prompt_norm:
            return category

    if is_short:
        for alias, canonical in CATEGORY_ALIASES.items():
            if alias in prompt_norm:
                for category in categories:
                    if normalize(category.get("name", "")) == normalize(canonical):
                        return category

    if is_short:
        match = re.search(r"\b(\d+)(?:st|nd|rd|th)?\b", prompt_norm)
        if match:
            idx = int(match.group(1))
            if 1 <= idx <= len(categories):
                return categories[idx - 1]
        ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
        for word, n in ordinals.items():
            if re.search(rf"\b{word}\b", prompt_norm):
                if n <= len(categories):
                    return categories[n - 1]
    return None


def direct_category_query(prompt: str, categories: list[dict]) -> dict | None:
    """Return a category when the first-turn prompt already specifies one."""
    hit = match_category(prompt, categories)
    if hit:
        return hit
    return None


def friendly_category_name(raw: str) -> str:
    """Massage a category name into something natural for TTS."""
    name = raw.strip()
    lowered = name.lower()
    if "immediately" in lowered:
        return "your urgent list"
    if lowered.startswith("for the "):
        return "the " + name[len("For the "):].lower()
    if lowered.startswith("for our "):
        return name[len("For our "):].lower()
    if lowered.startswith("for my "):
        return name[len("For my "):].lower()
    return name


def category_list_label(raw: str) -> str:
    """Return the short spoken label used when listing categories."""
    name = raw.strip()
    lowered = name.lower()
    if "immediately" in lowered:
        return "the urgent stuff"
    if lowered.startswith("for the "):
        return "the " + name[len("For the "):].lower()
    if lowered.startswith("for our "):
        return name[len("For our "):].lower()
    if lowered.startswith("for my "):
        return name[len("For my "):].lower()
    return name.lower()


def speak_items(category: dict) -> str:
    name = friendly_category_name(category.get("name", "that"))
    items = [item for item in (category.get("items") or []) if item.strip()]
    if not items:
        return f"Nothing logged under {name} yet."
    if len(items) == 1:
        return f"For {name}: {items[0].rstrip('.').strip()}."
    if len(items) == 2:
        return (
            f"Two things for {name}. "
            f"First, {items[0].rstrip('.').strip()}. "
            f"And second, {items[1].rstrip('.').strip()}."
        )
    joined = "; ".join(item.rstrip(".").strip() for item in items[:-1])
    return (
        f"{len(items)} items for {name}. "
        f"{joined}; and finally, {items[-1].rstrip('.').strip()}."
    )


def speak_category_list(categories: list[dict]) -> str:
    categories = visible_categories(categories)
    names = [category.get("name", "").strip() for category in categories if category.get("items")]
    friendly = [category_list_label(name) for name in names]
    if not friendly:
        return "Your list is empty right now."
    if len(friendly) == 1:
        return f"Just one category — {friendly[0]}. Want me to read it?"
    if len(friendly) == 2:
        return (
            f"Two categories: {friendly[0]} and {friendly[1]}. "
            f"Which one do you want to hear?"
        )
    return (
        f"{len(friendly)} categories: "
        + ", ".join(friendly[:-1])
        + f", and {friendly[-1]}. "
        + "Which one do you want to hear?"
    )
