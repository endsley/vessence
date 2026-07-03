from dataclasses import dataclass
from collections.abc import Sequence

from context_builder.v1.recent_history import build_user_transcript, format_recent_history


PLATFORM_LABELS = {
	"android": "Android app",
	"web": "web interface",
	"cli": "CLI terminal",
}


@dataclass(frozen=True)
class ContextAssembly:
	system_prompt: str
	transcript: str
	retrieved_memory_summary: str


def platform_context_line(platform: str | None) -> str:
	if not platform:
		return ""
	label = PLATFORM_LABELS.get(platform, platform)
	return f"[Platform] The user is chatting from the {label}."


def final_system_sections(
	system_sections: Sequence[str],
	*,
	platform: str | None = None,
	tts_instruction: str = "",
	managed_user_block: str = "",
) -> list[str]:
	sections = list(system_sections)
	platform_line = platform_context_line(platform)
	if platform_line:
		sections.append(platform_line)
	if tts_instruction:
		sections.append(tts_instruction)
	if managed_user_block:
		sections.append(managed_user_block)
	return sections


def assemble_context_parts(
	system_sections: Sequence[str],
	*,
	message: str,
	history: list[dict],
	retrieved_memory_summary: str,
	platform: str | None = None,
	tts_instruction: str = "",
	managed_user_block: str = "",
) -> ContextAssembly:
	sections = final_system_sections(
		system_sections,
		platform=platform,
		tts_instruction=tts_instruction,
		managed_user_block=managed_user_block,
	)
	recent_history = format_recent_history(history)
	return ContextAssembly(
		system_prompt="\n\n".join(sections).strip(),
		transcript=build_user_transcript(message, recent_history),
		retrieved_memory_summary=retrieved_memory_summary,
	)
