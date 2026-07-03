from context_builder.v1 import context_builder
from context_builder.v1.context_assembly import (
	assemble_context_parts,
	final_system_sections,
	platform_context_line,
)
from jane import context_builder as jane_context_builder


def test_context_builder_reexports_context_assembly_helpers():
	assert context_builder._assemble_context_parts is assemble_context_parts
	assert context_builder._platform_context_line is platform_context_line
	assert jane_context_builder._assemble_context_parts is assemble_context_parts
	assert jane_context_builder._platform_context_line is platform_context_line


def test_platform_context_line_preserves_labels_and_fallbacks():
	assert platform_context_line(None) == ""
	assert platform_context_line("") == ""
	assert platform_context_line("android") == "[Platform] The user is chatting from the Android app."
	assert platform_context_line("web") == "[Platform] The user is chatting from the web interface."
	assert platform_context_line("cli") == "[Platform] The user is chatting from the CLI terminal."
	assert platform_context_line("watch") == "[Platform] The user is chatting from the watch."


def test_final_system_sections_appends_late_context_without_mutating_base():
	base = ["BASE", "TOOLS"]

	assert final_system_sections(
		base,
		platform="web",
		tts_instruction="TTS",
		managed_user_block="MANAGED",
	) == [
		"BASE",
		"TOOLS",
		"[Platform] The user is chatting from the web interface.",
		"TTS",
		"MANAGED",
	]
	assert base == ["BASE", "TOOLS"]


def test_assemble_context_parts_preserves_prompt_transcript_and_memory_summary():
	assembly = assemble_context_parts(
		["BASE"],
		message="What next?",
		history=[{"role": "assistant", "content": "Prior answer"}],
		retrieved_memory_summary="memory",
		platform="cli",
		tts_instruction="TTS",
		managed_user_block="MANAGED",
	)

	assert assembly.system_prompt == (
		"BASE\n\n"
		"[Platform] The user is chatting from the CLI terminal.\n\n"
		"TTS\n\n"
		"MANAGED"
	)
	assert assembly.transcript == (
		"Recent Conversation:\n"
		"Jane: Prior answer\n"
		"\n"
		"User: What next?\n"
		"\n"
		"Jane:"
	)
	assert assembly.retrieved_memory_summary == "memory"
