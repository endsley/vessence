import datetime

from agent_skills import ambient_task_research
from agent_skills.ambient_task_research_rules import (
    build_search_query,
    extract_unchecked_tasks_from_text,
    is_cache_stale,
    openai_synthesis_messages,
    task_cache_key,
    task_research_discord_summary,
)


def test_ambient_task_research_exposes_rule_helpers():
    assert ambient_task_research._extract_unchecked_tasks_from_text is extract_unchecked_tasks_from_text
    assert ambient_task_research.task_cache_key is task_cache_key
    assert ambient_task_research.build_search_query is build_search_query
    assert ambient_task_research._openai_synthesis_messages is openai_synthesis_messages
    assert ambient_task_research.task_research_discord_summary is task_research_discord_summary


def test_extract_unchecked_tasks_accepts_current_numbered_progress_tracker():
    content = """
# Ambient App

## 8. Open Questions
- [ ] Not part of the tracker

## 11. Progress Tracker
### Phase 1 — Core Chat (MVP)
- [x] Completed task
- [ ] Flutter project scaffold with Android and Linux targets

### Phase 2 — Voice Mode
- [ ] Stream microphone audio to the local server
"""
    assert extract_unchecked_tasks_from_text(content) == [
        {
            "phase": "Phase 1 — Core Chat (MVP)",
            "task": "Flutter project scaffold with Android and Linux targets",
        },
        {
            "phase": "Phase 2 — Voice Mode",
            "task": "Stream microphone audio to the local server",
        },
    ]


def test_extract_unchecked_tasks_accepts_unnumbered_progress_tracker():
    content = """
## Progress Tracker
- [ ] Task before a phase heading
### Phase A
- [ ] Task in a phase
"""
    assert extract_unchecked_tasks_from_text(content) == [
        {"phase": "Unknown Phase", "task": "Task before a phase heading"},
        {"phase": "Phase A", "task": "Task in a phase"},
    ]
    assert extract_unchecked_tasks_from_text("## Other\n- [ ] Missing tracker") == []


def test_task_cache_key_preserves_existing_shape():
    assert task_cache_key("Persist chat/history in SQLite / sqflite!") == (
        "persist_chat_history_in_sqlite___sqflite!"
    )
    assert len(task_cache_key("x" * 100)) == 80


def test_is_cache_stale_preserves_ttl_and_error_fallbacks():
    now = datetime.datetime(2026, 7, 2, 12, 0, 0)
    assert is_cache_stale({}, "task", now=now)
    assert not is_cache_stale(
        {"task": {"last_researched": (now - datetime.timedelta(days=6)).isoformat()}},
        "task",
        now=now,
    )
    assert is_cache_stale(
        {"task": {"last_researched": (now - datetime.timedelta(days=7)).isoformat()}},
        "task",
        now=now,
    )
    assert is_cache_stale({"task": {"last_researched": "not-a-date"}}, "task", now=now)


def test_build_search_query_preserves_context_classification():
    assert build_search_query("Phase", "Persist SQLite chat history") == (
        "Flutter SQLite Persist SQLite chat history implementation tutorial 2024 2025"
    )
    assert build_search_query("Phase", "Stream SSE tokens to the UI") == (
        "Flutter SSE streaming ADK Stream SSE tokens to the UI implementation tutorial 2024 2025"
    )
    assert build_search_query("Phase", "Wake word standby detection") == (
        "Picovoice Porcupine wake word Python Wake word standby detection implementation tutorial 2024 2025"
    )
    assert build_search_query("Phase", "Implement invite auth") == (
        "FastAPI user authentication Implement invite auth implementation tutorial 2024 2025"
    )
    assert build_search_query("Phase", "Polish navigation") == (
        "Flutter cross-platform Polish navigation implementation tutorial 2024 2025"
    )


def test_openai_synthesis_messages_preserves_prompt_shape_and_web_truncation():
    messages = openai_synthesis_messages("Phase 1", "Build storage", "x" * 6001)

    assert messages[0]["role"] == "system"
    assert messages[0]["content"].startswith("You are a Senior Software Engineer advising on 'Project Ambient'")
    assert messages[1]["role"] == "user"
    assert messages[1]["content"].startswith("Phase: Phase 1\nTask: Build storage")
    assert "\n\nWeb search results:\n" in messages[1]["content"]
    assert messages[1]["content"].endswith("x" * 6000)
    assert "x" * 6001 not in messages[1]["content"]


def test_task_research_discord_summary_preserves_teaser_shape_and_limit():
    summary = task_research_discord_summary(
        [
            {
                "phase": "Phase 1",
                "task": "Build storage",
                "note": "line one\nline two\nline three\nline four",
            },
            {
                "phase": "Phase 2",
                "task": "Long note",
                "note": "x" * 240,
            },
        ],
        total_tasks=7,
        generated_label="2026-07-02 12:00",
        cache_path="/tmp/cache.json",
    )

    assert summary.startswith("🔬 **Ambient Task Research** (2026-07-02 12:00)")
    assert "Researched **2/7 tasks** remaining in the spec." in summary
    assert "**[Phase 1]** `Build storage`" in summary
    assert "> line one\nline two\nline three" in summary
    assert "**[Phase 2]** `Long note`" in summary
    assert "> " + ("x" * 200) in summary
    assert "x" * 201 not in summary
    assert summary.endswith("_Full notes in `/tmp/cache.json`_")
