from memory.v1 import short_term_extractor
from memory.v1.short_term_structured import (
    EXTRACT_KEYS,
    LABEL_ORDER,
    empty_extracted,
    flatten_to_metadata,
    flatten_to_note,
    flatten_to_search_text,
    parse_json_blob,
    should_skip,
    short_term_memory_metadata,
)


def test_short_term_extractor_uses_structured_helpers() -> None:
    assert short_term_extractor.EXTRACT_KEYS is EXTRACT_KEYS
    assert short_term_extractor._LABEL_ORDER is LABEL_ORDER
    assert short_term_extractor._empty_extracted is empty_extracted
    assert short_term_extractor._parse_json_blob is parse_json_blob
    assert short_term_extractor.should_skip is should_skip
    assert short_term_extractor.flatten_to_note is flatten_to_note
    assert short_term_extractor.flatten_to_search_text is flatten_to_search_text
    assert short_term_extractor.flatten_to_metadata is flatten_to_metadata


def test_parse_json_blob_handles_fences_embedded_objects_strings_and_lists() -> None:
    parsed = parse_json_blob(
        "preamble\n```json\n"
        '{"facts": "one fact with { braces } in text", "decisions": [" decided ", 42, ""], '
        '"open_loops": [], "artifacts": [" file.py "], "people": 123}'
        "\n```\ntrailing"
    )

    assert parsed == {
        "facts": ["one fact with { braces } in text"],
        "decisions": ["decided", "42"],
        "open_loops": [],
        "artifacts": ["file.py"],
        "people": [],
        "time_refs": [],
    }


def test_parse_json_blob_returns_none_for_missing_unbalanced_or_non_object_json() -> None:
    assert parse_json_blob("") is None
    assert parse_json_blob("no json here") is None
    assert parse_json_blob('{"facts": ["missing close"]') is None
    assert parse_json_blob("[1, 2, 3]") is None


def test_should_skip_requires_decision_open_loop_or_artifact() -> None:
    assert should_skip({})
    assert should_skip({**empty_extracted(), "facts": ["interesting but not actionable"]})
    assert not should_skip({**empty_extracted(), "decisions": ["changed setting"]})
    assert not should_skip({**empty_extracted(), "open_loops": ["run tests"]})
    assert not should_skip({**empty_extracted(), "artifacts": ["file.py"]})


def test_flatten_to_note_and_search_text_preserve_label_order_and_trim_items() -> None:
    extracted = {
        "facts": [" fact "],
        "decisions": ["changed code", ""],
        "open_loops": ["run tests"],
        "artifacts": [" file.py "],
        "people": ["Chieh"],
        "time_refs": ["today"],
    }

    assert flatten_to_note(extracted) == "\n".join([
        "Decisions: changed code",
        "Open loops: run tests",
        "Artifacts: file.py",
        "Facts: fact",
        "People: Chieh",
        "Time: today",
    ])
    assert flatten_to_search_text(extracted) == "\n".join([
        "changed code",
        "run tests",
        "file.py",
        "fact",
        "Chieh",
        "today",
    ])


def test_flatten_to_metadata_uses_primitive_flags_counts_and_capped_joined_lists() -> None:
    extracted = {
        "facts": ["f1", "f2"],
        "decisions": ["d1"],
        "open_loops": [],
        "artifacts": [f"file_{i}.py" for i in range(10)],
        "people": ["Chieh", "Jane"],
        "time_refs": ["today"],
    }

    assert flatten_to_metadata("code", extracted) == {
        "turn_kind": "code",
        "has_open_loop": False,
        "has_decision": True,
        "has_artifact": True,
        "artifact_paths": " | ".join(f"file_{i}.py" for i in range(8)),
        "person_names": "Chieh | Jane",
        "time_refs": "today",
        "n_facts": 2,
        "n_decisions": 1,
        "n_open_loops": 0,
    }


def test_short_term_memory_metadata_preserves_conversation_manager_shape() -> None:
    assert short_term_memory_metadata(
        session_id="session-1",
        timestamp="2026-07-02T12:34:56",
        expires_at="2026-07-16T12:34:56",
        raw_text="raw turn text",
        note="Decisions: keep helper",
        extracted_meta={
            "turn_kind": "code",
            "has_decision": True,
            "summary_style": "structured_short_term_v1",
        },
    ) == {
        "session_id": "session-1",
        "timestamp": "2026-07-02T12:34:56",
        "expires_at": "2026-07-16T12:34:56",
        "memory_type": "short_term",
        "author": "conversation_manager",
        "topic": "turn_memory",
        "role": "turn",
        "raw_chars": len("raw turn text"),
        "summary_chars": len("Decisions: keep helper"),
        "turn_kind": "code",
        "has_decision": True,
        "summary_style": "structured_short_term_v1",
    }
