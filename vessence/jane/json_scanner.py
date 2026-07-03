"""Small JSON object scanning helpers shared across Jane modules."""

from __future__ import annotations


def find_json_object_end(text: str, start: int = 0) -> int | None:
    """Return the exclusive end index of a balanced JSON object in text."""
    if start < 0 or start >= len(text) or text[start] != "{":
        return None

    depth = 0
    in_str = False
    escape = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return None
