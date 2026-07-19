"""Stage 2 handler for National Grid bill questions."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent_skills.nationalgrid_bills import fetch_bills, format_answer, infer_year
from agent_skills.web_ui_change import recover_website_ui_change


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


def _fetch_with_ui_recovery(*, prompt: str, year: int) -> dict:
    """Repair one high-confidence UI failure, then re-run the read-only fetch."""
    try:
        return fetch_bills(prompt=prompt, year=year)
    except Exception as exc:
        incident = recover_website_ui_change(
            skill="waterlily-nationalgrid-bills",
            intent="Read the requested National Grid bill-history amounts and bill PDFs for the selected known utility account without changing the account.",
            operation="National Grid bill-history extraction",
            exc=exc,
            project_root=Path(__file__).resolve().parents[4],
            retry_safe=False,
        )
        if incident is None:
            raise
    # The generic extractor is loaded fresh by fetch_bills, so a selector fix
    # made by the review is active for this one safe retry.
    return fetch_bills(prompt=prompt, year=year)


async def handle(prompt: str, context: str = "", params: dict | None = None) -> dict | None:
    year = infer_year(prompt)
    if year is None:
        # Keep this deterministic; Stage 3 can ask a follow-up if the user did
        # not specify a period.
        return None

    try:
        result = await asyncio.to_thread(_fetch_with_ui_recovery, prompt=prompt, year=year)
    except Exception as exc:
        return bill_fetch_error_response(exc)
    return bill_fetch_success_response(result)
