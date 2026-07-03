from agent_skills import evolve_code_map_keywords
from agent_skills.code_keyword_evolution import (
    append_keywords_to_source,
    extract_candidate_keywords,
    extract_code_map_names,
    is_code_related_message,
    keyword_insert_block,
    parse_tuple_assignment,
    tuple_assignment_inner,
)


def test_evolve_keywords_uses_extracted_helpers():
    assert evolve_code_map_keywords._parse_tuple_assignment is parse_tuple_assignment
    assert evolve_code_map_keywords._extract_code_map_names is extract_code_map_names
    assert evolve_code_map_keywords._is_code_related_message is is_code_related_message
    assert evolve_code_map_keywords._extract_candidate_keywords is extract_candidate_keywords


def test_parse_tuple_assignment_extracts_double_quoted_values_only():
    source = 'CODE_MAP_KEYWORDS = (\n    "pipeline",\n    "stage2",\n)\n'
    assert tuple_assignment_inner(source, "CODE_MAP_KEYWORDS") == '\n    "pipeline",\n    "stage2",\n'
    assert parse_tuple_assignment(source, "CODE_MAP_KEYWORDS") == ("pipeline", "stage2")
    assert parse_tuple_assignment("CODE_MAP_KEYWORDS = ()\n", "CODE_MAP_KEYWORDS") == ()
    assert parse_tuple_assignment(source, "MISSING") == ()


def test_extract_code_map_names_gets_file_stems_functions_and_classes():
    text = "\n".join([
        "### jane_web/main.py (100 lines)",
        "  handle_chat() → L42",
        "  class JaneProxy → L10",
        "### static/app.ts (50 lines)",
    ])

    assert extract_code_map_names(text) == {
        "main.py",
        "main",
        "handle_chat",
        "janeproxy",
        "app.ts",
        "app",
    }


def test_is_code_related_message_checks_keywords_and_long_code_map_names():
    assert is_code_related_message("fix the pipeline", {"pipeline"}, set())
    assert is_code_related_message("look at janeproxy", set(), {"janeproxy"})
    assert not is_code_related_message("look at api", set(), {"api"})


def test_extract_candidate_keywords_requires_two_code_related_messages():
    messages = [
        "pipeline widget widget refactor",
        "pipeline widget cleanup widget",
        "general conversation widget",
    ]

    assert extract_candidate_keywords(
        messages,
        existing_keywords={"pipeline"},
        code_map_names=set(),
        stopwords=frozenset({"cleanup"}),
    ) == ["widget"]
    assert extract_candidate_keywords(
        ["pipeline widget"],
        existing_keywords={"pipeline"},
        code_map_names=set(),
        stopwords=frozenset(),
    ) == []


def test_keyword_insert_block_and_source_append_preserve_format():
    assert keyword_insert_block(["widget", "pipeline2"]) == (
        "    # Auto-evolved from daily conversations\n"
        '    "widget",\n'
        '    "pipeline2",\n'
    )

    source = 'CODE_MAP_KEYWORDS = (\n    "pipeline",\n)\n'
    assert append_keywords_to_source(source, ["widget"]) == (
        'CODE_MAP_KEYWORDS = (\n    "pipeline",\n'
        "    # Auto-evolved from daily conversations\n"
        '    "widget",\n'
        ")\n"
    )
    assert append_keywords_to_source("NOPE = ()\n", ["widget"]) is None
