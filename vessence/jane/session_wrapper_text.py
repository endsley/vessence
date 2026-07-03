import re
from collections.abc import Sequence


ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
DEFAULT_PROMPT_PATTERNS = (
	re.compile(r'Type your message or @path/to/file'),
	re.compile(r'Press / for commands'),
)
NOISE_INDICATORS = (
	"Waiting for auth...",
	"Gemini CLI update available!",
	"Automatic update failed",
	"Ready (user)",
	"Logged in with Google",
	"screen reader-friendly view",
	"YOLO mode",
	"~ no sandbox",
	"Logging in...",
	"Logged in.",
	"Updated successfully",
	"update manually",
)


def normalize_output(text: str) -> str:
	return ANSI_ESCAPE_RE.sub('', text).replace('\r\n', '\n').replace('\r', '\n').strip()


def is_meaningful_text(text: str, noise_indicators: Sequence[str] = NOISE_INDICATORS) -> bool:
	stripped = text.strip()
	if len(stripped) <= 5:
		return False
	for indicator in noise_indicators:
		if indicator in stripped and len(stripped) < len(indicator) + 20:
			return False
	return True


def extract_prompt_split(
	text: str,
	prompt_patterns: Sequence[re.Pattern[str]] = DEFAULT_PROMPT_PATTERNS,
) -> tuple[str | None, str | None, str | None]:
	for pattern in prompt_patterns:
		match = pattern.search(text)
		if match:
			return text[:match.start()], text[match.end():], match.group(0)
	return None, None, None


def is_terminal_noise_input(user_input: str, *, max_length: int = 5000) -> bool:
	return user_input.startswith('\x1b') or len(user_input) > max_length


def wrapper_status_line(*, process_running: bool, generation: int, ready: bool) -> str:
	proc_state = "running" if process_running else "stopped"
	return f"process={proc_state} generation={generation} ready={ready}"
