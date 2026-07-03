"""HTML parsers for the education homework auditor."""
from __future__ import annotations

from bs4 import BeautifulSoup


def parse_prompt_from_question(html: str) -> tuple[str, str]:
    """Returns (raw_prompt_html, visible_text)."""
    soup = BeautifulSoup(html, "html.parser")
    div = soup.select_one("div.prompt")
    if not div:
        return "", ""
    raw_html = div.decode_contents()
    text = div.get_text(" ", strip=True)
    return raw_html, text


def parse_client_version(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one('input[name="client_version"]')
    if not el:
        return 0
    try:
        return int(el.get("value") or 0)
    except ValueError:
        return 0


def parse_answer_result(html: str) -> dict:
    """Parse the HTMX fragment returned after submitting an answer."""
    soup = BeautifulSoup(html, "html.parser")
    fb = soup.select_one("div.feedback")
    if not fb:
        return {"verdict": "unknown", "feedback_text": "", "displayed_response": None}
    classes = fb.get("class") or []
    text = fb.get_text(" ", strip=True)
    if "ok" in classes:
        verdict = "correct"
    elif "warn" in classes:
        verdict = "stale" if "already submitted" in text else "locked"
    elif "bad" in classes:
        verdict = "incorrect"
    else:
        verdict = "unknown"
    return {
        "verdict": verdict,
        "feedback_text": text,
        "displayed_response": _extract_displayed_response(fb),
    }


# If one of these appears in the rendered "Your answer: <code>X</code>" slot,
# the student_response Jinja filter or its caller is leaking the answer type
# instead of the submitted answer.
_ANSWER_TYPE_NAMES = frozenset({
    "number", "text", "math_expression", "fraction", "multiple_choice",
    "vector", "subspace_basis", "linear_system_solve", "classify_and_reach",
    "invertibility_with_blank", "solve_system_with_basis",
})


def _extract_displayed_response(feedback_div) -> str | None:
    """Pull the rendered student-response text from a feedback panel."""
    text = feedback_div.get_text(" ", strip=True)
    introducers = ("Your answer:", "You answered")
    if not any(intro in text for intro in introducers):
        return None
    for code in feedback_div.find_all("code"):
        prev = code.find_previous(string=True)
        if not prev:
            continue
        prev_str = str(prev)
        if any(intro in prev_str for intro in introducers):
            return code.get_text(strip=True)
    first = feedback_div.find("code")
    return first.get_text(strip=True) if first else None


def lint_displayed_response(
    displayed: str | None,
    submitted: str | None,
    answer_type: str,
) -> list[dict]:
    """Catch UI bugs where rendered answer text does not reflect submitted text."""
    issues: list[dict] = []
    if displayed is None:
        return issues
    if displayed in _ANSWER_TYPE_NAMES:
        issues.append({
            "severity": "high",
            "kind": "displayed_response_is_answer_type",
            "message": (
                f"Rendered 'Your answer: {displayed}' is the literal "
                f"answer-type identifier — the student_response filter is "
                f"swallowing the response and showing the type instead "
                f"(check Jinja filter call signature)."
            ),
        })
    if submitted and displayed.strip() == "":
        issues.append({
            "severity": "med",
            "kind": "displayed_response_empty",
            "message": (
                f"Rendered 'Your answer:' is empty but the student submitted "
                f"{submitted!r} — display layer dropped the value."
            ),
        })
    if submitted and displayed.strip().lower() == "(none)" and submitted.strip():
        issues.append({
            "severity": "high",
            "kind": "displayed_response_none",
            "message": (
                f"Rendered 'Your answer: (none)' but the student submitted "
                f"{submitted!r} — display layer is treating a real response "
                f"as empty."
            ),
        })
    return issues
