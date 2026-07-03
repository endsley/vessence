import asyncio

from context_builder.v1 import context_builder


def test_async_context_builder_loads_saved_articles_for_article_prompt(monkeypatch):
	statuses: list[str] = []
	captured: dict[str, str] = {}

	monkeypatch.setattr(context_builder, "_managed_user_runtime_context", lambda user_id: ({}, None, ""))
	monkeypatch.setattr(context_builder, "_load_personal_facts", lambda data_root: {})
	monkeypatch.setattr(context_builder, "_build_saved_articles_context", lambda message: "ARTICLE CONTEXT")

	def fake_build_system_sections(*args, **kwargs):
		captured["saved_articles_context"] = kwargs["saved_articles_context"]
		return ["BASE", kwargs["saved_articles_context"]]

	monkeypatch.setattr(context_builder, "_build_system_sections", fake_build_system_sections)

	ctx = asyncio.run(
		context_builder.build_jane_context_async(
			"what did the saved article say about remission?",
			history=[],
			enable_memory_retrieval=False,
			on_status=statuses.append,
		)
	)

	assert captured["saved_articles_context"] == "ARTICLE CONTEXT"
	assert "ARTICLE CONTEXT" in ctx.system_prompt
	assert "Checking saved Daily Briefing articles..." in statuses
	assert "Saved briefing article context loaded." in statuses


def test_async_context_builder_skips_saved_article_loader_for_unrelated_prompt(monkeypatch):
	calls: list[str] = []

	monkeypatch.setattr(context_builder, "_managed_user_runtime_context", lambda user_id: ({}, None, ""))
	monkeypatch.setattr(context_builder, "_load_personal_facts", lambda data_root: {})
	monkeypatch.setattr(
		context_builder,
		"_build_saved_articles_context",
		lambda message: calls.append(message) or "ARTICLE CONTEXT",
	)
	monkeypatch.setattr(context_builder, "_build_system_sections", lambda *args, **kwargs: ["BASE"])

	ctx = asyncio.run(
		context_builder.build_jane_context_async(
			"hello there",
			history=[],
			enable_memory_retrieval=False,
			on_status=lambda status: None,
		)
	)

	assert calls == []
	assert ctx.system_prompt == "BASE"
