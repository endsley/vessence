"""Pure helpers for evolve_code_map_keywords.py."""

from __future__ import annotations

import re
from collections import Counter


def tuple_assignment_inner(source: str, var_name: str) -> str | None:
    pattern = rf"{var_name}\s*=\s*\((.*?)\)"
    match = re.search(pattern, source, re.DOTALL)
    if not match:
        return None
    return match.group(1)


def parse_tuple_assignment(source: str, var_name: str) -> tuple[str, ...]:
    inner = tuple_assignment_inner(source, var_name)
    if inner is None:
        return ()
    return tuple(re.findall(r'"([^"]*)"', inner))


def extract_code_map_names(text: str) -> set[str]:
    names: set[str] = set()

    for match in re.finditer(r"###\s+(\S+\.(?:py|html|kt|js|ts))", text):
        full_path = match.group(1)
        filename = full_path.rsplit("/", 1)[-1]
        names.add(filename.lower())
        stem = filename.rsplit(".", 1)[0]
        names.add(stem.lower())

    for match in re.finditer(r"(\w+)\(\)\s*→\s*L\d+", text):
        name = match.group(1)
        if len(name) > 2:
            names.add(name.lower())

    for match in re.finditer(r"class\s+(\w+)", text):
        name = match.group(1)
        if len(name) > 2:
            names.add(name.lower())

    return names


def is_code_related_message(message: str, keywords: set[str], code_map_names: set[str]) -> bool:
    lowered = message.lower()
    if any(keyword in lowered for keyword in keywords):
        return True
    if any(name in lowered for name in code_map_names if len(name) > 3):
        return True
    return False


def extract_candidate_keywords(
    messages: list[str],
    existing_keywords: set[str],
    code_map_names: set[str],
    stopwords: set[str] | frozenset[str],
) -> list[str]:
    code_messages = [
        message for message in messages
        if is_code_related_message(message, existing_keywords, code_map_names)
    ]
    if len(code_messages) < 2:
        return []

    known_lower = {keyword.lower() for keyword in existing_keywords}
    known_lower.update(stopwords)

    word_counter: Counter[str] = Counter()
    for message in code_messages:
        words = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", message.lower()))
        for word in words:
            if (
                len(word) >= 3
                and word not in known_lower
                and not word.isdigit()
                and "_" not in word[:1]
            ):
                word_counter[word] += 1

    return [
        word for word, count in word_counter.most_common()
        if count >= 2
    ]


def keyword_insert_block(new_keywords: list[str]) -> str:
    keyword_lines = [f'    "{keyword}",' for keyword in new_keywords]
    return (
        "    # Auto-evolved from daily conversations\n"
        + "\n".join(keyword_lines)
        + "\n"
    )


def append_keywords_to_source(source: str, new_keywords: list[str]) -> str | None:
    pattern = r"(CODE_MAP_KEYWORDS\s*=\s*\(.*?)(^\))"
    match = re.search(pattern, source, re.DOTALL | re.MULTILINE)
    if not match:
        return None
    return source[:match.end(1)] + keyword_insert_block(new_keywords) + source[match.start(2):]
