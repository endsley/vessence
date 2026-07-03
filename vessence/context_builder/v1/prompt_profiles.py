"""Prompt profile classification rules for Jane context construction."""
from __future__ import annotations

from dataclasses import dataclass

from jane.research_router import should_offload_research


TASK_KEYWORDS = (
    "task", "project", "working on", "roadmap", "transition", "migration",
    "bug", "fix", "implement", "patch", "code", "repo", "architecture",
    "deploy", "systemd", "cron", "backup", "chromadb", "optimiz", "todo",
)
AI_CODING_KEYWORDS = (
    "ml", "machine learning", "llm", "prompt engineering", "token usage", "coding",
    "code", "python", "javascript", "typescript", "bug", "debug", "api endpoint",
    "system prompt", "architecture", "repo", "database", "chromadb",
)
MUSIC_KEYWORDS = (
    "piano", "music", "song", "melody", "harmony", "chord", "practice", "compose",
)
SIMPLE_FACTUAL_PREFIXES = (
    "who", "what", "when", "where", "which", "favorite", "my favorite", "do you know",
)
ANAPHORIC_TOKENS = {
    "it", "that", "this", "them", "those", "these", "the button",
    "the file", "the page", "the link", "the thing", "the one",
}


@dataclass(frozen=True)
class PromptProfile:
    name: str
    include_user_background: bool = False
    include_task_state: bool = False
    include_conversation_summary: bool = False
    include_memory_summary: bool = True
    include_research: bool = False
    include_file_context: bool = False
    include_code_map: bool = False
    include_tool_protocols: bool = True
    tool_context_override: str | None = None


def _is_short_anaphoric(message: str) -> bool:
    """Return True when a short message relies on conversational context."""
    words = (message or "").strip().split()
    if len(words) > 8:
        return False
    lowered = " ".join(words).lower()
    return any(token in lowered for token in ANAPHORIC_TOKENS)


def _message_lower(message: str) -> str:
    return (message or "").strip().lower()


def _is_task_related(message: str) -> bool:
    lowered = _message_lower(message)
    return any(keyword in lowered for keyword in TASK_KEYWORDS)


def _should_include_conversation_summary(message: str) -> bool:
    lowered = _message_lower(message)
    if not lowered:
        return False
    if _is_task_related(message):
        return True
    if any(keyword in lowered for keyword in AI_CODING_KEYWORDS):
        return True
    if lowered.startswith(SIMPLE_FACTUAL_PREFIXES):
        return False
    if len(lowered) <= 40 and "?" in lowered:
        return False
    return True


def _profile_for_intent_level(
    intent_level: str | None,
    *,
    file_context: str | None = None,
    tool_context: str | None = None,
) -> PromptProfile | None:
    if intent_level == "tool_mode":
        return PromptProfile(
            name="tool_mode",
            include_user_background=True,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=False,
            include_research=False,
            include_file_context=False,
            include_code_map=False,
            include_tool_protocols=False,
            tool_context_override=tool_context,
        )
    if intent_level == "data_mode":
        return PromptProfile(
            name="data_mode",
            include_user_background=True,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=False,
            include_research=False,
            include_file_context=False,
            include_code_map=False,
            include_tool_protocols=False,
        )
    if intent_level == "greeting":
        return PromptProfile(
            name="greeting",
            include_user_background=False,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=False,
            include_file_context=False,
            include_tool_protocols=False,
        )
    if intent_level == "simple":
        return PromptProfile(
            name="simple_query",
            include_user_background=True,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=False,
            include_research=False,
            include_file_context=bool(file_context),
            include_tool_protocols=False,
        )
    return None


def _profile_for_message_category(
    message: str,
    file_context: str | None = None,
    *,
    research_decider=should_offload_research,
) -> PromptProfile:
    lowered = _message_lower(message)
    if file_context or any(marker in lowered for marker in ("file", "folder", "document", "pdf", "vault", "path")):
        return PromptProfile(
            name="file_lookup",
            include_user_background=False,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=True,
            include_research=False,
            include_file_context=True,
            include_code_map=True,
        )
    if _is_task_related(message) or any(keyword in lowered for keyword in AI_CODING_KEYWORDS):
        return PromptProfile(
            name="project_work",
            include_user_background=True,
            include_task_state=True,
            include_conversation_summary=True,
            include_memory_summary=True,
            include_research=research_decider(message),
            include_file_context=bool(file_context),
            include_code_map=True,
        )
    if lowered.startswith(SIMPLE_FACTUAL_PREFIXES) or (len(lowered) <= 40 and "?" in lowered):
        return PromptProfile(
            name="factual_personal",
            include_user_background=True,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=True,
            include_research=False,
            include_file_context=False,
        )
    return PromptProfile(
        name="casual_followup",
        include_user_background=True,
        include_task_state=False,
        include_conversation_summary=False,
        include_memory_summary=True,
        include_research=False,
        include_file_context=bool(file_context),
        include_code_map=False,
    )


def _classify_prompt_profile(
    message: str,
    file_context: str | None = None,
    intent_level: str | None = None,
    tool_context: str | None = None,
) -> PromptProfile:
    explicit_profile = _profile_for_intent_level(
        intent_level,
        file_context=file_context,
        tool_context=tool_context,
    )
    if explicit_profile is not None:
        return explicit_profile
    return _profile_for_message_category(message, file_context)
