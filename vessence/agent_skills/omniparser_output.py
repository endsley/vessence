"""Pure output parsing helpers for OmniParser subprocess results."""

from __future__ import annotations

import json
from typing import Any


def json_text_from_output(output: str) -> str | None:
    start_idx = output.rfind('{"elements":')
    if start_idx == -1:
        start_idx = output.rfind("{")
    if start_idx == -1:
        return None
    return output[start_idx:]


def format_parsed_elements(elements: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            f"Element {index}: {element.get('type')} at {element.get('bbox')} - "
            f"Content: {element.get('content')}"
            for index, element in enumerate(elements)
        ]
    )


def parsed_result_from_output(output: str) -> dict[str, Any]:
    json_text = json_text_from_output(output)
    if json_text is None:
        raise Exception(f"Failed to find JSON in OmniParser output: {output}")
    data = json.loads(json_text)
    if "error" in data:
        raise Exception(
            f"OmniParser API Error: {data['error']}\n"
            f"Traceback: {data.get('traceback', 'N/A')}"
        )
    elements = data.get("elements", [])
    return {
        "labeled_image": data.get("labeled_image_base64", ""),
        "parsed_content": format_parsed_elements(elements),
        "elements": elements,
    }
