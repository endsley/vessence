"""Pure output builders for generated essence folders."""

from __future__ import annotations


def should_write_custom_functions(custom_functions_answer: str) -> bool:
    cleaned = custom_functions_answer.strip()
    return bool(cleaned) and cleaned.lower() not in ("none", "n/a", "no")


def custom_tools_stub(essence_name: str, custom_functions_answer: str) -> str:
    return (
        f'"""\nCustom tools for {essence_name}\n\n'
        f"Based on spec:\n{custom_functions_answer}\n\n"
        f'TODO: Implement the functions described above.\n"""\n'
    )


def capped_output_note(text: str, max_chars: int = 500) -> str:
    return text[:max_chars] if len(text) > max_chars else text


def essence_layout_payload(ui_type: str, ui_answer: str) -> dict:
    return {
        "type": ui_type,
        "components": [
            {
                "id": "main",
                "type": f"{ui_type}_panel",
                "position": "main",
            }
        ],
        "notes": capped_output_note(ui_answer),
    }


def onboarding_payload(starters: list[str], interaction_answer: str) -> dict:
    return {
        "onboarding": {
            "conversation_starters": starters,
            "steps": [],
            "notes": capped_output_note(interaction_answer),
        }
    }
