from context_builder.v1 import context_builder
from context_builder.v1.memory_plan import (
	RETRIEVING_MEMORY_STATUS,
	SHORT_ANAPHORA_STATUS,
	build_memory_summary_plan,
)


def test_context_builder_reexports_memory_plan_helper():
	assert context_builder._build_memory_summary_plan is build_memory_summary_plan


def test_memory_plan_skips_short_anaphora_and_forces_conversation_summary():
	plan = build_memory_summary_plan(
		"remove it",
		include_memory_summary=True,
		enable_memory_retrieval=True,
		memory_summary_fallback="fallback",
	)

	assert plan.force_conversation_summary is True
	assert plan.should_retrieve is False
	assert plan.memory_summary == ""
	assert plan.status_message == SHORT_ANAPHORA_STATUS


def test_memory_plan_uses_override_before_retrieval():
	plan = build_memory_summary_plan(
		"what was Maya's name?",
		include_memory_summary=True,
		enable_memory_retrieval=True,
		memory_summary_override="  Relevant contact: Maya  ",
		memory_summary_fallback="fallback",
	)

	assert plan.force_conversation_summary is False
	assert plan.should_retrieve is False
	assert plan.memory_summary == "Relevant contact: Maya"
	assert plan.status_message == ""


def test_memory_plan_retrieves_only_when_enabled_and_profile_allows_memory():
	plan = build_memory_summary_plan(
		"what was Maya's name?",
		include_memory_summary=True,
		enable_memory_retrieval=True,
	)

	assert plan.should_retrieve is True
	assert plan.memory_summary == ""
	assert plan.status_message == RETRIEVING_MEMORY_STATUS

	disabled = build_memory_summary_plan(
		"what was Maya's name?",
		include_memory_summary=True,
		enable_memory_retrieval=False,
		memory_summary_fallback="fallback",
	)
	profile_skipped = build_memory_summary_plan(
		"what was Maya's name?",
		include_memory_summary=False,
		enable_memory_retrieval=True,
		memory_summary_fallback="fallback",
	)

	assert disabled.should_retrieve is False
	assert disabled.memory_summary == "fallback"
	assert profile_skipped.should_retrieve is False
	assert profile_skipped.memory_summary == "fallback"


def test_memory_plan_normalizes_empty_fallbacks():
	plan = build_memory_summary_plan(
		"what was Maya's name?",
		include_memory_summary=False,
		memory_summary_fallback="No relevant context found.",
	)

	assert plan.should_retrieve is False
	assert plan.memory_summary == ""
