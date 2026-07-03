"""Deterministic helpers for Stage 3 delegate acknowledgments."""

from __future__ import annotations

import re


ACK_FALLBACK = "Got it, give me a moment to look into that."


def estimate_duration(prompt: str) -> str:
    """Return 'a few seconds' | 'a minute or two' | 'a while' based on prompt."""
    p = prompt.lower()
    word_count = len(prompt.split())
    long_signals = (
        "build", "implement", "refactor", "write code",
        "debug", "analyze the codebase", "trace through",
        "compare and contrast", "summarize the entire",
    )
    medium_signals = (
        "research", "look online", "compare", "analyze",
        "explain how", "explain why", "walk me through",
        "what are the differences", "pros and cons",
        "investigate", "trace",
    )
    if any(signal in p for signal in long_signals) or word_count > 60:
        return "a while"
    if any(signal in p for signal in medium_signals) or word_count > 25:
        return "a minute or two"
    return "a few seconds"


def avoid_got_it_default(text: str, cls: str = "others") -> str:
    """Prevent the spoken ack from collapsing into a repeated "Got it" tic."""
    cleaned = (text or "").strip()
    if not cleaned.lower().startswith("got it"):
        return cleaned

    rest = re.sub(r"^got it[\s,.\-—:]*", "", cleaned, flags=re.IGNORECASE).strip()
    if rest:
        rest = rest[0].upper() + rest[1:]

    cls_key = (cls or "").strip().lower()
    if cls_key in {"read calendar", "read email", "read messages"} and rest:
        if rest.lower().startswith(("checking", "pulling", "looking", "reading")):
            return rest
        return f"Let me check, {rest[0].lower() + rest[1:]}"
    if cls_key in {"todo list", "send message", "shopping list", "timer"}:
        return f"Okay, {rest[0].lower() + rest[1:]}" if rest else "Okay, one sec."
    return f"On it, {rest[0].lower() + rest[1:]}" if rest else "On it."


def delegate_ack_prompt(
    prompt: str,
    *,
    cls: str,
    duration: str,
    flow_context: str = "",
) -> str:
    flow_section = ""
    if flow_context:
        flow_section = (
            "Recent conversation flow, oldest to newest. Use this only to avoid a disconnected ack; "
            "do not quote it or reveal internal state:\n"
            f"{flow_context}\n\n"
        )

    return (
        "You are writing a ONE-sentence acknowledgment Jane (a voice assistant) will speak OUT LOUD while she works on the user's request in the background. The reply itself is coming separately — this is just so the user knows Jane heard them.\n\n"
        + flow_section +
        "Requirements:\n"
        "1. Start with a varied, natural acknowledgment (\"Okay\", \"Sure\", \"One sec\", \"Let me check\", \"On it\"). Do not default to \"Got it\"; use it only when it is clearly the best fit. Never clown-speak (\"Heh\", \"Mmkay\", \"Oh nice\").\n"
        "2. Match the conversation flow. If the user is following up, correcting, confirming, or answering a question, acknowledge that continuation instead of treating the text as a brand-new topic.\n"
        "3. Briefly reference what the user asked about — 2–6 words max, no details. The user already knows what they asked; this is a breadcrumb that you heard the specific thing.\n"
        "4. End with a short time signal — \"one sec\", \"give me a moment\", \"this'll take a moment\", etc. Rough scale: " + duration + ".\n"
        "5. ONE sentence. 6–14 words total. No questions. No summarizing the likely answer. No filler. No emoji.\n\n"
        "Good examples:\n"
        "  user: \"What was the last email from Bob about?\" → \"Let me check your email, one sec.\"\n"
        "  user: \"Explain how rsync works\"                → \"Sure — rsync breakdown coming, give me a moment.\"\n"
        "  user: \"When did we talk about the scheduler?\"  → \"On it, let me pull up the scheduler thread.\"\n"
        "  user: \"Rewrite this function\"                  → \"Okay, refactoring now — this'll take a moment.\"\n\n"
        "Flow-aware examples:\n"
        "  previous: Jane asked which TODO category. user: \"clinic\" → \"Okay, checking the clinic TODOs now.\"\n"
        "  previous: discussing ack quality. user: \"it feels off\" → \"On it, tuning the ack flow now.\"\n"
        "  previous: drafting SMS. user: \"make it warmer\" → \"Okay, revising that message tone now.\"\n\n"
        "Bad examples:\n"
        "  \"Hmm, give me a sec.\"                           ← topic-blind, feels disconnected\n"
        "  \"Oh nice, this might take a minute or two.\"     ← clown opener, still disconnected\n"
        "  \"Let me check your email and summarize the three most recent threads.\"  ← over-specifying Opus's answer\n\n"
        f"Routing class: {cls}\n"
        f"User message: {(prompt or '').strip()[:400]}\n\n"
        "Your one-sentence acknowledgment (plain text, no quotes):"
    )


def normalize_delegate_ack_response(text: str, *, cls: str = "others") -> str:
    cleaned = (text or "").strip()
    cleaned = cleaned.strip('"').strip("'").strip()
    if cleaned.lower().startswith("acknowledgment:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    if len(cleaned) > 120:
        first_period = cleaned.find(".")
        if 10 < first_period < 120:
            cleaned = cleaned[:first_period + 1]
        else:
            cleaned = cleaned[:120]
    return avoid_got_it_default(cleaned, cls=cls)
