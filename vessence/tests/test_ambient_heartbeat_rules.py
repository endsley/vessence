import datetime

from agent_skills import ambient_heartbeat
from agent_skills.ambient_heartbeat_rules import (
    apply_research_note_to_spec,
    automation_synthesis_prompt,
    heartbeat_discord_summary,
    heartbeat_should_run,
    heartbeat_sleep_window,
    implementation_prompt,
    implementation_ready_tasks_from_text,
    is_cache_stale,
    phase1_unchecked_tasks,
    research_note_block,
    unanswered_open_questions,
)


def test_ambient_heartbeat_exposes_rule_helpers():
    assert ambient_heartbeat._is_cache_stale is is_cache_stale
    assert ambient_heartbeat._apply_research_note_to_spec is apply_research_note_to_spec
    assert ambient_heartbeat._automation_synthesis_prompt is automation_synthesis_prompt
    assert ambient_heartbeat._heartbeat_sleep_window is heartbeat_sleep_window
    assert ambient_heartbeat._heartbeat_should_run is heartbeat_should_run
    assert ambient_heartbeat._implementation_prompt is implementation_prompt
    assert ambient_heartbeat._unanswered_open_questions is unanswered_open_questions
    assert ambient_heartbeat._phase1_unchecked_tasks is phase1_unchecked_tasks
    assert ambient_heartbeat._implementation_ready_tasks_from_text is implementation_ready_tasks_from_text
    assert ambient_heartbeat.heartbeat_discord_summary is heartbeat_discord_summary


def test_is_cache_stale_preserves_valid_cache_behavior():
    now = datetime.datetime(2026, 7, 2, 12, 0, 0)
    assert is_cache_stale({}, "topic", now=now)
    assert not is_cache_stale(
        {"topic": {"last_researched": (now - datetime.timedelta(days=6)).isoformat()}},
        "topic",
        days=7,
        now=now,
    )
    assert is_cache_stale(
        {"topic": {"last_researched": (now - datetime.timedelta(days=7)).isoformat()}},
        "topic",
        days=7,
        now=now,
    )


def test_heartbeat_sleep_window_and_idle_policy_preserve_hour_bounds():
    assert heartbeat_sleep_window(datetime.datetime(2026, 7, 2, 1, 0))
    assert heartbeat_sleep_window(datetime.datetime(2026, 7, 2, 6, 59))
    assert not heartbeat_sleep_window(datetime.datetime(2026, 7, 2, 7, 0))
    assert not heartbeat_sleep_window(datetime.datetime(2026, 7, 2, 0, 59))
    assert heartbeat_should_run(False, datetime.datetime(2026, 7, 2, 12, 0))
    assert not heartbeat_should_run(True, datetime.datetime(2026, 7, 2, 12, 0))
    assert heartbeat_should_run(True, datetime.datetime(2026, 7, 2, 2, 0))


def test_apply_research_note_to_spec_inserts_skips_duplicates_and_appends():
    content = "# Spec\n\n## Target Heading\nBody\n"
    updated, action = apply_research_note_to_spec(
        content,
        heading="## Target Heading",
        topic_id="topic_a",
        note="Line 1\nLine 2",
        date_str="2026-07-02",
    )
    assert action == "inserted"
    assert updated == (
        "# Spec\n\n## Target Heading"
        "\n\n> **🔬 Research Note (2026-07-02 — auto):**\n"
        "> Line 1\n> Line 2\nBody\n"
    )

    duplicate, action = apply_research_note_to_spec(
        updated,
        heading="## Target Heading",
        topic_id="topic_a",
        note="New note",
        date_str="2026-07-02",
    )
    assert action == "duplicate"
    assert duplicate == updated

    appended, action = apply_research_note_to_spec(
        "# Spec\n",
        heading="## Missing",
        topic_id="topic_b",
        note="Fallback note",
        date_str="2026-07-02",
    )
    assert action == "appended"
    assert appended == "# Spec\n\n\n---\n\n### Research: topic_b (2026-07-02)\nFallback note"


def test_unanswered_open_questions_accepts_current_numbered_heading():
    content = """
## 10. Open Questions (Must Answer Before Coding)
1. Which database should be used?
2. ~~Which icon should be used?~~
19. Does this arbitrary numbered question block readiness?

## 11. Progress Tracker
- [ ] Task
"""
    assert unanswered_open_questions(content) == [
        "1. Which database should be used?",
        "19. Does this arbitrary numbered question block readiness?",
    ]
    assert unanswered_open_questions("## Other\n1. Missing?") == []


def test_phase1_unchecked_tasks_and_readiness_gate():
    content = """
## 10. Open Questions
1. Ready to code?

## 11. Progress Tracker
### Phase 1 — Core Chat (MVP)
- [x] Done
- [ ] Build shell
### Phase 2 — Voice
- [ ] Build voice
"""
    assert phase1_unchecked_tasks(content) == ["Build shell"]
    assert implementation_ready_tasks_from_text(content) == []

    answered = content.replace("1. Ready to code?", "1. ~~Ready to code?~~")
    assert implementation_ready_tasks_from_text(answered) == ["Build shell"]


def test_research_note_block_preserves_existing_block_shape():
    assert research_note_block("One\nTwo", "2026-07-02") == (
        "\n\n> **🔬 Research Note (2026-07-02 — auto):**\n> One\n> Two"
    )


def test_heartbeat_discord_summary_preserves_topic_and_implementation_shape():
    summary = heartbeat_discord_summary(
        research_done=["flutter_chat_ui", "adk_sse_streaming"],
        implementations_done=["✅ Build shell"],
        generated_label="2026-07-02 12:00",
    )

    assert summary == (
        "🔁 **Ambient Heartbeat** (2026-07-02 12:00)\n"
        "\n📚 **Researched 2 topics:**\n"
        "  • flutter chat ui\n"
        "  • adk sse streaming\n"
        "\n🔨 **Implemented:**\n"
        "  ✅ Build shell\n"
        "\n_Spec updated. Check `ambient_app.md` for new research notes._"
    )


def test_automation_synthesis_prompt_preserves_system_and_web_data_truncation():
    prompt = automation_synthesis_prompt("Research Flutter", "x" * 8001)

    assert prompt.startswith("You are a Senior Technical Researcher helping refine the spec for 'Project Ambient'")
    assert "\n\nResearch Flutter\n\nWeb Search Data:\n" in prompt
    assert prompt.endswith("x" * 8000)


def test_implementation_prompt_preserves_task_and_spec_context_shape():
    prompt = implementation_prompt("Build chat shell", "Spec excerpt")

    assert "Task to implement: Build chat shell" in prompt
    assert "Project spec context:\nSpec excerpt" in prompt
    assert prompt.endswith("After completing, report what was done in 2-3 sentences.")
