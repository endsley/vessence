from agent_skills import generate_code_map
from agent_skills.code_map_output import (
    combined_code_map_index,
    generated_header,
    merge_preserved_header,
    preserved_header,
    rendered_line_count,
    short_android_path,
)


def test_generate_code_map_uses_extracted_output_helpers():
    assert generate_code_map._combined_code_map_index is combined_code_map_index
    assert generate_code_map._generated_header is generated_header
    assert generate_code_map._merge_preserved_header is merge_preserved_header
    assert generate_code_map._rendered_line_count is rendered_line_count
    assert generate_code_map._short_android_path is short_android_path


def test_generated_header_preserves_existing_map_intro_lines():
    assert generated_header("# Code Map — Core (Python Backend)", "2026-07-02 12:00 UTC") == [
        "# Code Map — Core (Python Backend)",
        "_Auto-generated on 2026-07-02 12:00 UTC by `generate_code_map.py`_\n",
    ]


def test_preserved_header_keeps_text_through_marker_only():
    marker = "<!-- marker -->"
    existing = "Manual intro\n<!-- marker -->\nold generated content\n"

    assert preserved_header(existing, marker) == "Manual intro\n<!-- marker -->\n\n"
    assert preserved_header("Manual intro without marker", marker) == ""
    assert merge_preserved_header(existing, "new content", marker) == (
        "Manual intro\n<!-- marker -->\n\nnew content"
    )


def test_rendered_line_count_matches_legacy_counting():
    assert rendered_line_count("") == 1
    assert rendered_line_count("one") == 1
    assert rendered_line_count("one\n") == 2
    assert rendered_line_count("one\ntwo") == 2


def test_short_android_path_replaces_only_known_prefix():
    assert short_android_path(
        "android/app/src/main/java/com/vessences/android/MainActivity.kt"
    ) == "android:.../MainActivity.kt"
    assert short_android_path("android/build.gradle.kts") == "android/build.gradle.kts"


def test_combined_code_map_index_preserves_backcompat_text():
    assert combined_code_map_index() == (
        "# Code Map Index\n\n"
        "Split into three targeted maps:\n"
        "- `CODE_MAP_CORE.md` — Python backend (jane/, agent_skills/, startup_code/)\n"
        "- `CODE_MAP_WEB.md` — Web frontend (vault_web/templates/)\n"
        "- `CODE_MAP_ANDROID.md` — Android app (Kotlin)\n\n"
        "Run `python agent_skills/generate_code_map.py` to regenerate all, "
        "or pass `core`, `web`, or `android` to regenerate one.\n"
    )
