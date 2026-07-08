from memory.v1.conversation_themes import (
    archivist_prompt,
    clean_theme_title_response,
    filter_short_term_theme_results,
    format_theme_registry_for_prompt,
    identity_signal_count,
    initial_theme_title_prompt,
    normalize_theme_title,
    oldest_theme_by_last_update,
    parse_theme_classification_response,
    short_term_theme_metadata,
    theme_classification_prompt,
    theme_entries_from_results,
    theme_summary_prompt,
    updated_short_term_theme_metadata,
)


def test_normalize_theme_title_strips_noise_and_truncates():
    assert normalize_theme_title("  - Project Vessence:  ") == "Project Vessence"
    assert normalize_theme_title("x" * 100) == "x" * 80
    assert normalize_theme_title(None) == ""


def test_format_theme_registry_for_prompt_matches_archivist_prompt_shape():
    assert format_theme_registry_for_prompt([]) == "- (none)"
    assert format_theme_registry_for_prompt(
        [
            {"theme_id": "identity", "title": "Identity", "description": "User context"},
            {"theme_id": "project", "title": "Project", "description": ""},
        ]
    ) == (
        "- identity: Identity — User context\n"
        "- project: Project — No description."
    )


def test_identity_signal_count_requires_multiple_signals_for_reclassification():
    assert identity_signal_count("The user prefers tea and his wife likes the clinic.") >= 2
    assert identity_signal_count("The user prefers tea.") == 1
    assert identity_signal_count("Architecture change in Vessence.") == 0


def test_initial_theme_title_prompt_and_clean_response_preserve_title_policy():
    prompt = initial_theme_title_prompt("x" * 600)

    assert prompt.startswith("Give a short (3-8 word) theme title")
    assert prompt.endswith("x" * 500)
    assert clean_theme_title_response(' "Project Refactor" ') == "Project Refactor"


def test_theme_classification_prompt_formats_existing_themes_and_truncates_turn():
    prompt = theme_classification_prompt(
        [
            {
                "document": "Summary " + ("a" * 120),
                "metadata": {"theme_title": "Vessence Refactor"},
            }
        ],
        "turn " + ("b" * 900),
    )

    assert '0. "Vessence Refactor" — Summary ' in prompt
    assert "Summary " + ("a" * 92) in prompt
    assert "turn " + ("b" * 795) in prompt
    assert "turn " + ("b" * 796) not in prompt
    assert "EXISTING: <number>" in prompt


def test_parse_theme_classification_response_handles_existing_new_and_unparseable():
    assert parse_theme_classification_response("EXISTING: 0", 2) == {
        "action": "existing",
        "theme_index": 0,
    }
    assert parse_theme_classification_response("EXISTING: 99", 2) == {
        "action": "existing",
        "theme_index": 1,
    }
    assert parse_theme_classification_response("NEW: 'Refactor Journal'", 2) == {
        "action": "new",
        "title": "Refactor Journal",
    }
    assert parse_theme_classification_response("something else", 2) is None


def test_theme_summary_prompt_preserves_new_and_update_shapes():
    new_prompt = theme_summary_prompt("", "new turn")
    update_prompt = theme_summary_prompt("current summary", "turn " + ("x" * 900))

    assert "Summarize this conversation turn" in new_prompt
    assert "outcome/current status" in new_prompt
    assert "Return ONLY the summary." in new_prompt
    assert "Here is the current summary" in update_prompt
    assert "current summary" in update_prompt
    assert "current state is clear" in update_prompt
    assert "turn " + ("x" * 795) in update_prompt
    assert "turn " + ("x" * 796) not in update_prompt
    assert "Return ONLY the updated summary." in update_prompt


def test_filter_short_term_theme_results_keeps_only_theme_rows():
    results = {
        "ids": ["turn-1", "theme-1", "theme-2"],
        "documents": ["turn doc", "theme one", "theme two"],
        "metadatas": [
            {"memory_type": "turn"},
            {"memory_type": "short_term_theme", "theme_index": 2},
            {"memory_type": "short_term_theme", "theme_index": 1},
        ],
    }

    assert filter_short_term_theme_results(results) == {
        "ids": ["theme-1", "theme-2"],
        "documents": ["theme one", "theme two"],
        "metadatas": [
            {"memory_type": "short_term_theme", "theme_index": 2},
            {"memory_type": "short_term_theme", "theme_index": 1},
        ],
    }


def test_theme_entries_from_results_sorts_by_theme_index_and_defaults_metadata():
    entries = theme_entries_from_results(
        {
            "ids": ["late", "missing-meta", "early"],
            "documents": ["late doc", "missing doc", "early doc"],
            "metadatas": [
                {"theme_index": 5, "theme_title": "Late"},
                None,
                {"theme_index": 1, "theme_title": "Early"},
            ],
        }
    )

    assert entries == [
        {"id": "missing-meta", "document": "missing doc", "metadata": {}},
        {"id": "early", "document": "early doc", "metadata": {"theme_index": 1, "theme_title": "Early"}},
        {"id": "late", "document": "late doc", "metadata": {"theme_index": 5, "theme_title": "Late"}},
    ]


def test_short_term_theme_metadata_preserves_conversation_manager_shape():
    assert short_term_theme_metadata(
        session_id="session-1",
        theme_title="Project Vessence",
        theme_index=3,
        now_iso="2026-07-03T12:00:00",
        expires_iso="2026-08-02T12:00:00",
    ) == {
        "session_id": "session-1",
        "theme_title": "Project Vessence",
        "theme_index": 3,
        "turn_count": 1,
        "first_turn_at": "2026-07-03T12:00:00",
        "last_updated_at": "2026-07-03T12:00:00",
        "memory_type": "short_term_theme",
        "expires_at": "2026-08-02T12:00:00",
    }
    assert short_term_theme_metadata(
        session_id="session-1",
        theme_title="Project Vessence",
        theme_index=3,
        now_iso="2026-07-03T12:00:00",
        expires_iso="2026-08-02T12:00:00",
        turn_count=4,
        first_turn_at="2026-07-01T09:00:00",
    )["first_turn_at"] == "2026-07-01T09:00:00"


def test_updated_short_term_theme_metadata_preserves_existing_theme_update_shape():
    assert updated_short_term_theme_metadata(
        {
            "theme_title": "Project Vessence",
            "theme_index": 2,
            "turn_count": 4,
            "first_turn_at": "2026-07-01T09:00:00",
            "last_updated_at": "old",
            "expires_at": "old-expiry",
        },
        now_iso="2026-07-03T12:00:00",
        expires_iso="2026-08-02T12:00:00",
    ) == {
        "theme_title": "Project Vessence",
        "theme_index": 2,
        "turn_count": 5,
        "first_turn_at": "2026-07-01T09:00:00",
        "last_updated_at": "2026-07-03T12:00:00",
        "expires_at": "2026-08-02T12:00:00",
    }
    assert updated_short_term_theme_metadata(
        {"theme_title": "Untitled"},
        now_iso="now",
        expires_iso="later",
    )["turn_count"] == 2


def test_oldest_theme_by_last_update_preserves_eviction_ordering():
    missing_timestamp = {
        "id": "missing",
        "metadata": {"theme_title": "Missing timestamp"},
    }
    early = {
        "id": "early",
        "metadata": {
            "theme_title": "Early",
            "last_updated_at": "2026-07-01T09:00:00",
        },
    }
    late = {
        "id": "late",
        "metadata": {
            "theme_title": "Late",
            "last_updated_at": "2026-07-03T09:00:00",
        },
    }

    assert oldest_theme_by_last_update([late, early]) is early
    assert oldest_theme_by_last_update([late, missing_timestamp, early]) is missing_timestamp


def test_archivist_prompt_includes_registry_topics_schema_and_transcript_tail():
    transcript = "old" + ("x" * 21000)
    prompt = archivist_prompt(
        transcript,
        theme_registry_text="- project_vessence: Project: vessence — System state",
        atomic_topics=("Decision", "Commitment"),
    )

    assert prompt.startswith("You are The Thematic Archivist")
    assert "- project_vessence: Project: vessence — System state" in prompt
    assert "- Valid atomic topics: Decision, Commitment" in prompt
    assert "- 'existing_theme_id': registered theme id or ''" in prompt
    assert "If nothing in the transcript is worth remembering, return []." in prompt
    transcript_section = prompt.split("Transcript (truncated if needed):\n", 1)[1]
    assert "old" not in transcript_section
    assert transcript_section == "x" * 20000
