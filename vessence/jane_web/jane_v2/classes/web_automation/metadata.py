"""Web automation class — classifier metadata.

Phase 1 always escalates to Stage 3 (Opus) — the brain decides which
browser tools to call based on the accessibility snapshot. This class
is essentially a signpost for Stage 1 so that a clear browser intent
doesn't accidentally match a different handler.
"""

from __future__ import annotations


def _description() -> str:
    return (
        "[web_automation]\n"
        "The user wants Jane to OPERATE a real web browser on their behalf — "
        "navigate to a URL, fill forms, click buttons, read information off "
        "a page, download a file, or replay a saved workflow.\n"
        "Examples:\n"
        "  - 'Go to weather.gov and tell me tomorrow's forecast'\n"
        "  - 'Open my bank's website and look up the balance'\n"
        "  - 'Log in to the city water site and download the current bill'\n"
        "  - 'Run pay water bill' (saved workflow — Phase 3)\n"
        "NOT this class:\n"
        "  - 'Search for X' (generic web search, goes through Stage 3 research)\n"
        "  - 'What's the weather?' (local weather cache, see weather class)\n"
        "  - 'Read an article' (briefing-share or vault retrieval)\n"
    )


def _escalation_context() -> str:
    """Stage 3 brain context — tells Opus it has the web-automation tool
    surface available and reminds it of the user-facing UX rules."""
    return (
        "Web-automation tool surface is available. Emit CLIENT_TOOL calls "
        "of the form `[[CLIENT_TOOL:web.<action>:<args_json>]]` where "
        "<action> is one of: navigate, snapshot, status, click, fill, "
        "press, select, wait, extract, screenshot.\n\n"
        "Typical first move: `web.navigate({\"url\": \"...\"})` then "
        "`web.snapshot({})` to get element refs, then plan clicks/fills.\n\n"
        "UX rules:\n"
        "- Speak in human terms — never mention selectors, CDP, or Playwright.\n"
        "- Ask before any action that could pay money, send a message, "
        "submit an official form, or change account settings.\n"
        "- On a login page, tell the user: 'This site needs you to log in. "
        "Let me know when you're through.' — do NOT try to type credentials.\n"
        "- After each action, read the returned message/snapshot and plan "
        "the next step. Stop when the user's goal is satisfied and give a "
        "short plain-language summary.\n"
    )


METADATA = {
    "name": "web_automation",
    "priority": 5,
    "description": _description,
    "escalation_context": _escalation_context,
    "few_shot": [
        ("Go to weather.gov and tell me tomorrow's forecast",    "web_automation:High"),
        ("Open my bank's website",                                "web_automation:High"),
        ("Download the PDF from this page",                       "web_automation:High"),
        ("Fill out the form on citywater.com/billing",            "web_automation:High"),
        ("Log in to my water company and grab this month's bill", "web_automation:High"),
        ("Search for the best pasta recipe",                      "others:Low"),
        ("What's the weather tomorrow?",                          "weather:High"),
    ],
    "ack": "Opening the browser now…",
    "escalate_ack": "Let me drive that in the browser — give me a moment.",
}
