"""Pure display helpers for show_transcript.py."""

from __future__ import annotations


CONTEXT_PREFIXES = (
    "[CURRENT CONVERSATION STATE]",
    "[Recent exchanges]",
    "[WEB CHAT",
    "[ANDROID",
)


def speaker_label(role: str) -> str:
    return "YOU" if role == "user" else "JANE"


def strip_context_prefix(text: str) -> str:
    for prefix in CONTEXT_PREFIXES:
        if text.startswith(prefix):
            tail = text.find("]")
            if tail != -1 and len(text) > tail + 2:
                text = text[tail + 1:].strip()
            break
    return text


def first_user_preview_text(content: object, max_len: int = 80) -> str:
    text = " ".join(str(content).split())
    text = strip_context_prefix(text)
    return (text[:max_len] + "…") if len(text) > max_len else text


def parse_turns_flag_args(args: list[str]) -> tuple[int | None, list[str], str | None]:
    if "--turns" not in args:
        return None, args, None
    index = args.index("--turns")
    if index + 1 >= len(args):
        return None, args, "--turns requires a number"
    try:
        turns = int(args[index + 1])
    except ValueError:
        return None, args, f"--turns: not an integer: {args[index + 1]}"
    return turns, args[:index] + args[index + 2:], None
