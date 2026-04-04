from jane.context_builder import build_jane_context


def test_build_jane_context_includes_recent_history_in_transcript():
    ctx = build_jane_context(
        message="What was her name again?",
        history=[
            {"role": "user", "content": "I met a new contact yesterday. Her name is Maya."},
            {"role": "assistant", "content": "I'll remember Maya as your new contact."},
        ],
        enable_memory_retrieval=False,
    )

    assert "Recent Conversation:" in ctx.transcript
    assert "User: I met a new contact yesterday. Her name is Maya." in ctx.transcript
    assert "Jane: I'll remember Maya as your new contact." in ctx.transcript
    assert ctx.transcript.rstrip().endswith("Jane:")


def test_build_jane_context_bounds_recent_history():
    long_content = "x" * 5000
    ctx = build_jane_context(
        message="Summarize that.",
        history=[{"role": "assistant", "content": long_content}] * 10,
        enable_memory_retrieval=False,
    )

    assert "Recent Conversation:" in ctx.transcript
    assert len(ctx.transcript) < 2600


def test_build_jane_context_casual_followup_still_retrieves_memory(monkeypatch):
    monkeypatch.setattr(
        "jane.context_builder.get_memory_summary",
        lambda *args, **kwargs: "Relevant contact: Maya from yesterday's meeting.",
    )
    # Prevent code map from consuming system prompt space
    monkeypatch.setattr("jane.context_builder._load_code_map", lambda: "")
    # Clear the code map cache to ensure the monkeypatch takes effect
    import jane.context_builder as cb
    cb._context_cache.pop("code_map_core", None)

    ctx = build_jane_context(
        message="What was her name again?",
        history=[],
        enable_memory_retrieval=True,
    )

    assert "## Retrieved Memory" in ctx.system_prompt
    assert "Relevant contact: Maya" in ctx.system_prompt


def test_build_jane_context_uses_fallback_memory_when_retrieval_is_empty(monkeypatch):
    monkeypatch.setattr(
        "jane.context_builder.get_memory_summary",
        lambda *args, **kwargs: "No relevant context found.",
    )

    ctx = build_jane_context(
        message="What was her name again?",
        history=[],
        enable_memory_retrieval=True,
        memory_summary_fallback="Relevant contact: Maya from yesterday's meeting.",
    )

    assert "## Retrieved Memory" in ctx.system_prompt
    assert "Relevant contact: Maya" in ctx.system_prompt
