"""Prompt, payload, and response parsing helpers for the joke handler."""

from __future__ import annotations


PROMPT_TEMPLATE = """\
You are Jane, a voice assistant. The user just asked you to tell a joke.

{context_block}User: "{prompt}"

Tell ONE short clean joke. Setup + punchline. Two short sentences max.
If the recent conversation already has a joke from you, pick a NEW joke —
different topic, different style. No preamble like "Sure, here's one" —
just the joke itself.

Format your response as exactly TWO fields:

THOUGHT: <one short line: which joke style fits, anything to avoid>
REPLY: <the joke itself, plain spoken English for TTS, no markdown, no emoji>"""


def context_block(context: str) -> str:
    if context and context.strip():
        return f"Recent conversation:\n{context.strip()}\n\n"
    return ""


def build_joke_prompt(prompt: str, context: str = "") -> str:
    return PROMPT_TEMPLATE.format(
        prompt=(prompt or "").strip(),
        context_block=context_block(context),
    )


def joke_llm_payload(
    prompt_text: str,
    *,
    model: str,
    num_ctx: int,
    keep_alive: str | int,
) -> dict:
    return {
        "model": model,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.9,
            "num_predict": 100,
            "num_ctx": num_ctx,
        },
        "keep_alive": keep_alive,
    }


def parse_joke_response(raw: str) -> tuple[str, str]:
    thought = ""
    reply = (raw or "").strip()
    saw_reply_tag = False
    for line in (raw or "").splitlines():
        text = line.strip()
        if text.upper().startswith("THOUGHT:"):
            thought = text.split(":", 1)[1].strip()
        elif text.upper().startswith("REPLY:"):
            reply = text.split(":", 1)[1].strip()
            saw_reply_tag = True
    if not saw_reply_tag and thought:
        cleaned = []
        for line in (raw or "").splitlines():
            if line.strip().upper().startswith("THOUGHT:"):
                continue
            cleaned.append(line)
        reply = "\n".join(cleaned).strip() or thought
    reply = reply.strip().strip('"').strip("'").strip()
    return thought, reply
