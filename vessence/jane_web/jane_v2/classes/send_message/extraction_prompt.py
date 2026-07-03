"""Prompt and request builders for send-message extraction."""

from __future__ import annotations


EXTRACT_PROMPT = """\
The classifier thinks the user wants to SEND A TEXT MESSAGE to someone.
First, confirm: is the user actually asking to send/text/tell someone a message?
If NOT (e.g., they're discussing architecture, asking a question, or just mentioning \
a person's name without a send intent), output ONLY: WRONG_CLASS

If YES, extract the recipient and compose the message body AS IT SHOULD APPEAR IN THE TEXT.

CRITICAL: The user is speaking TO YOU about a third person. You must rewrite the \
body so it reads correctly FROM THE USER TO THE RECIPIENT. Convert perspective:
- "tell my wife I love her" → RECIPIENT: wife / BODY: I love you
- "tell my wife she is beautiful" → RECIPIENT: wife / BODY: You are beautiful
- "let mom know I'm on my way" → RECIPIENT: mom / BODY: I'm on my way
- "tell kathia I miss her today" → RECIPIENT: kathia / BODY: I miss you today
- "text my wife I'll be home soon" → RECIPIENT: wife / BODY: I'll be home soon
- "tell my dad happy birthday" → RECIPIENT: dad / BODY: Happy birthday!
- "text romeo hey sorry for using you as a test subject" → RECIPIENT: romeo / BODY: Hey, sorry for using you as a test subject
- "text john hey what's up" → RECIPIENT: john / BODY: Hey, what's up?
- "text sarah thanks for dinner last night" → RECIPIENT: sarah / BODY: Thanks for dinner last night

IMPORTANT: In "text [name] [message]", everything after the name IS the message body. \
Do NOT output (none) if there are words after the recipient name.

Output EXACTLY these 3 lines — nothing else:

RECIPIENT: <who to text — keep relational names like "wife", "mom", "dad" as-is>
BODY: <the actual text message to send, written from user to recipient>
COHERENT: yes or no (no = garbled, cut off mid-sentence, or contains background noise like Alexa/Siri commands)

If the user didn't include a message body (e.g., "text my wife"), output:
BODY: (none)
COHERENT: yes

Use the recent conversation below to resolve pronouns ("him", "her", "that") \
and to pick up an unspecified recipient from prior context.

{context_block}User: {prompt}"""


def extraction_context_block(context: str) -> str:
    """Build the optional recent-conversation block for extraction."""
    if context and context.strip():
        return f"Recent conversation:\n{context.strip()}\n\n"
    return ""


def build_extraction_prompt(prompt: str, context: str) -> str:
    return EXTRACT_PROMPT.format(
        prompt=(prompt or "").strip(),
        context_block=extraction_context_block(context),
    )


def extraction_request_payload(
    *,
    model: str,
    prompt: str,
    context: str,
    num_ctx: int,
    keep_alive: str | int = -1,
) -> dict:
    return {
        "model": model,
        "prompt": build_extraction_prompt(prompt, context),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 100, "num_ctx": num_ctx},
        "keep_alive": keep_alive,
    }
