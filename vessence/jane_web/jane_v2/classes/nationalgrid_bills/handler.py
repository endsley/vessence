"""Stage 2 handler for National Grid bill questions."""

from __future__ import annotations

import asyncio

from agent_skills.nationalgrid_bills import fetch_bills, format_answer, infer_year


def bill_fetch_error_response(error: Exception | str) -> dict:
    return {
        "text": f"I could not fetch the National Grid bills yet: {error}",
        "error": str(error),
    }


def bill_fetch_success_response(result: dict) -> dict:
    return {
        "text": format_answer(result),
        "data": result,
    }


async def handle(prompt: str, context: str = "", params: dict | None = None) -> dict | None:
    year = infer_year(prompt)
    if year is None:
        # Keep this deterministic; Stage 3 can ask a follow-up if the user did
        # not specify a period.
        return None

    try:
        result = await asyncio.to_thread(fetch_bills, prompt=prompt, year=year)
    except Exception as exc:
        return bill_fetch_error_response(exc)
    return bill_fetch_success_response(result)
