import re

from jane import jane_session_wrapper
from jane.session_wrapper_text import (
	DEFAULT_PROMPT_PATTERNS,
	extract_prompt_split,
	is_meaningful_text,
	is_terminal_noise_input,
	normalize_output,
	wrapper_status_line,
)


def test_session_wrapper_uses_extracted_text_helpers():
	assert jane_session_wrapper.extract_prompt_split is extract_prompt_split
	assert jane_session_wrapper.is_meaningful_text is is_meaningful_text
	assert jane_session_wrapper.normalize_output is normalize_output


def test_normalize_output_strips_ansi_and_normalizes_newlines():
	assert normalize_output("\x1b[31mHello\r\nthere\rJane\x1b[0m  ") == "Hello\nthere\nJane"


def test_is_meaningful_text_preserves_noise_and_length_policy():
	assert not is_meaningful_text("short")
	assert not is_meaningful_text("Ready (user)")
	assert is_meaningful_text("Ready (user) with enough surrounding output to keep as content")


def test_extract_prompt_split_preserves_pattern_order_and_remainder():
	assert extract_prompt_split("answer Type your message or @path/to/file next") == (
		"answer ",
		" next",
		"Type your message or @path/to/file",
	)
	assert extract_prompt_split("answer Press / for commands") == (
		"answer ",
		"",
		"Press / for commands",
	)
	assert extract_prompt_split("Press / for commands before Type your message or @path/to/file after") == (
		"Press / for commands before ",
		" after",
		"Type your message or @path/to/file",
	)
	assert extract_prompt_split("no prompt") == (None, None, None)


def test_extract_prompt_split_accepts_custom_prompt_patterns():
	assert extract_prompt_split("before READY after", [re.compile("READY")]) == (
		"before ",
		" after",
		"READY",
	)


def test_terminal_noise_input_matches_wrapper_policy():
	assert is_terminal_noise_input("\x1b[A")
	assert is_terminal_noise_input("x" * 5001)
	assert not is_terminal_noise_input("x" * 5000)


def test_wrapper_status_line_preserves_cli_status_shape():
	assert wrapper_status_line(process_running=True, generation=3, ready=False) == (
		"process=running generation=3 ready=False"
	)
	assert wrapper_status_line(process_running=False, generation=4, ready=True) == (
		"process=stopped generation=4 ready=True"
	)


def test_default_prompt_patterns_are_ordered_for_legacy_matching():
	assert [pattern.pattern for pattern in DEFAULT_PROMPT_PATTERNS] == [
		"Type your message or @path/to/file",
		"Press / for commands",
	]
