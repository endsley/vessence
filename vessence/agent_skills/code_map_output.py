"""Output-format helpers for generate_code_map.py."""

from __future__ import annotations


ANDROID_PATH_PREFIX = "android/app/src/main/java/com/vessences/android/"


def generated_header(title: str, generated_at: str) -> list[str]:
    return [title, f"_Auto-generated on {generated_at} by `generate_code_map.py`_\n"]


def preserved_header(existing: str, marker: str) -> str:
    if marker in existing:
        return existing[: existing.index(marker) + len(marker)] + "\n\n"
    return ""


def merge_preserved_header(existing: str, content: str, marker: str) -> str:
    return preserved_header(existing, marker) + content


def rendered_line_count(text: str) -> int:
    return text.count("\n") + 1


def short_android_path(rel_path: str) -> str:
    return rel_path.replace(ANDROID_PATH_PREFIX, "android:.../")


def combined_code_map_index() -> str:
    dash = "\u2014"
    return (
        "# Code Map Index\n\n"
        "Split into three targeted maps:\n"
        f"- `CODE_MAP_CORE.md` {dash} Python backend (jane/, agent_skills/, startup_code/)\n"
        f"- `CODE_MAP_WEB.md` {dash} Web frontend (vault_web/templates/)\n"
        f"- `CODE_MAP_ANDROID.md` {dash} Android app (Kotlin)\n\n"
        "Run `python agent_skills/generate_code_map.py` to regenerate all, "
        "or pass `core`, `web`, or `android` to regenerate one.\n"
    )
