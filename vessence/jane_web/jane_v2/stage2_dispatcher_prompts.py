"""Prompt builders for Stage 2 dispatcher gate checks."""

from __future__ import annotations


CLASS_DESCRIPTIONS = {
    "send message": "the user wants to text/SMS another person",
    "read messages": "the user wants to read or check their text messages",
    "sync messages": "the user wants to force-sync SMS from the phone",
    "read email": "the user wants to read or check their email inbox",
    "read calendar": "the user wants to read or check events on their Google Calendar",
    "shopping list": "the user wants to add/remove/view items on a shopping list",
    "weather": "the user wants the current/forecast weather",
    "music play": "the user wants to play/queue music",
    "greeting": "the user is just greeting (hi/hello/how are you)",
    "get time": "the user wants the current time",
    "end conversation": "the user is ending the conversation (bye/cancel/stop/never mind)",
    "todo list": "the user wants to read/add/remove items on their personal TODO list",
}


def _context_block(context: str) -> str:
    return f"Recent conversation:\n{context.strip()}\n\n" if context and context.strip() else ""


def continuation_check_prompt(
    class_name: str,
    prompt: str,
    context: str,
    *,
    pending_question: str | None = None,
) -> str:
    ctx_block = _context_block(context)

    if pending_question and pending_question.strip():
        return (
            f"Jane just asked the user this exact question:\n"
            f"  \"{pending_question.strip()}\"\n\n"
            f"Examples:\n"
            f"  Q: \"Which category? Home, clinic, or students?\"\n"
            f"    \"clinic\" → SAME\n"
            f"    \"the clinic one\" → SAME\n"
            f"    \"actually forget that, what's the weather\" → CHANGED\n"
            f"    \"tell Sarah I'm running late\" → CHANGED\n"
            f"    \"how does the pipeline route this?\" → CHANGED (meta question)\n"
            f"  Q: \"What should I call this timer?\"\n"
            f"    \"pasta\" → SAME\n"
            f"    \"no label\" → SAME\n"
            f"    \"play some music\" → CHANGED\n\n"
            f"{ctx_block}User's reply: {prompt.strip()}\n\n"
            f"Is the user's reply an ANSWER to Jane's question, or did they "
            f"CHANGE the subject?\n"
            f"Answer ONE word — SAME or CHANGED:"
        )

    desc = CLASS_DESCRIPTIONS.get(class_name, class_name)
    return (
        f"Jane just asked the user a follow-up question about: {desc}\n\n"
        f"{ctx_block}User's reply: {prompt.strip()}\n\n"
        f"Is the user answering Jane's question or continuing the same topic? "
        f"Or did they change the subject to something unrelated?\n"
        f"Answer ONE word — SAME or CHANGED:"
    )


def gate_check_prompt(class_name: str, prompt: str, context: str) -> str | None:
    desc = CLASS_DESCRIPTIONS.get(class_name)
    if not desc:
        return None

    ctx_block = _context_block(context)
    return (
        f"The classifier predicted: {desc}\n\n"
        f"Answer NO if ANY of these apply:\n"
        f"- The prompt is a complaint or meta question about this feature\n"
        f"- The prompt is a follow-up to a DIFFERENT topic in the conversation\n"
        f"- The prompt doesn't actually request this specific action\n\n"
        f"Examples:\n"
        f"  \"what time is it\" → YES\n"
        f"  \"the time you told me was wrong\" → NO (complaint)\n"
        f"  \"how about tomorrow\" after weather conversation → NO (follow-up to weather, not this)\n"
        f"  \"read my messages\" → YES\n"
        f"  \"and next week?\" after weather conversation → NO (follow-up to weather)\n"
        f"  \"hello jane\" → YES\n"
        f"  \"how does the greeting handler work\" → NO (meta)\n\n"
        f"{ctx_block}User prompt: {prompt.strip()}\n\n"
        f"Is this a genuine request for {desc}? Answer ONE word — YES or NO:"
    )
