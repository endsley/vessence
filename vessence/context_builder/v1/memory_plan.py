from dataclasses import dataclass

from context_builder.v1.memory_summary import normalize_memory_summary
from context_builder.v1.prompt_profiles import _is_short_anaphoric


SHORT_ANAPHORA_STATUS = "Short contextual message — using session context instead of memory."
RETRIEVING_MEMORY_STATUS = "Retrieving memory from ChromaDB..."


@dataclass(frozen=True)
class MemorySummaryPlan:
	force_conversation_summary: bool
	should_retrieve: bool
	memory_summary: str
	status_message: str = ""


def build_memory_summary_plan(
	message: str,
	*,
	include_memory_summary: bool,
	enable_memory_retrieval: bool = True,
	memory_summary_override: str | None = None,
	memory_summary_fallback: str | None = None,
) -> MemorySummaryPlan:
	if _is_short_anaphoric(message):
		return MemorySummaryPlan(
			force_conversation_summary=True,
			should_retrieve=False,
			memory_summary="",
			status_message=SHORT_ANAPHORA_STATUS,
		)
	if memory_summary_override is not None:
		return MemorySummaryPlan(
			force_conversation_summary=False,
			should_retrieve=False,
			memory_summary=normalize_memory_summary(memory_summary_override, memory_summary_fallback),
		)
	if enable_memory_retrieval and include_memory_summary:
		return MemorySummaryPlan(
			force_conversation_summary=False,
			should_retrieve=True,
			memory_summary="",
			status_message=RETRIEVING_MEMORY_STATUS,
		)
	return MemorySummaryPlan(
		force_conversation_summary=False,
		should_retrieve=False,
		memory_summary=normalize_memory_summary("", memory_summary_fallback),
	)
