"""Static prompt lint checks for the education homework auditor."""
from __future__ import annotations

import re


_TYPOS = {
    "recieve": "receive",
    "seperate": "separate",
    "occured": "occurred",
    "lenghth": "length",
    "definately": "definitely",
    "thier": "their",
    "untill": "until",
    "wich": "which",
    "begining": "beginning",
    "accomodate": "accommodate",
    "occurence": "occurrence",
    "neccessary": "necessary",
    "compatable": "compatible",
    "calender": "calendar",
    "consistant": "consistent",
    "independant": "independent",
    "dependant": "dependent",
    "existant": "existent",
    "noticable": "noticeable",
}


def lint_issue(severity: str, kind: str, message: str) -> dict:
    return {"severity": severity, "kind": kind, "message": message}


def prompt_without_display_math(prompt_html: str) -> str:
    return re.sub(r"\$\$.*?\$\$", "", prompt_html, flags=re.DOTALL)


def prompt_without_inline_or_environment_math(prompt_html: str) -> str:
    no_math = re.sub(r"\$[^$]*\$", "", prompt_html)
    return re.sub(r"\\begin\{[^}]+\}.*?\\end\{[^}]+\}", "", no_math, flags=re.DOTALL)


def typo_lint_issues(prompt_text: str) -> list[dict]:
    low = prompt_text.lower()
    return [
        lint_issue("med", "typo", f"Likely typo: '{bad}' -> '{good}'")
        for bad, good in _TYPOS.items()
        if re.search(rf"\b{re.escape(bad)}\b", low)
    ]


def lint_prompt(prompt_html: str, prompt_text: str) -> list[dict]:
    """Run cheap content checks on a question's prompt."""
    issues: list[dict] = []

    if "{{" in prompt_html or "{%" in prompt_html:
        issues.append(lint_issue(
            "high",
            "unrendered_jinja",
            "Prompt contains unrendered Jinja delimiters ({{ or {%)",
        ))

    stripped = prompt_without_display_math(prompt_html)
    dollar_count = stripped.count("$")
    if dollar_count % 2 != 0:
        issues.append(lint_issue(
            "high",
            "unbalanced_math",
            f"Odd number of `$` delimiters ({dollar_count} unpaired)",
        ))

    opens = prompt_html.count("{")
    closes = prompt_html.count("}")
    if abs(opens - closes) > 2:
        issues.append(lint_issue(
            "med",
            "brace_mismatch",
            f"Brace imbalance: {opens} `{{` vs {closes} `}}`",
        ))

    issues.extend(typo_lint_issues(prompt_text))

    if len(prompt_text.strip()) < 15:
        issues.append(lint_issue(
            "med",
            "short_prompt",
            f"Prompt is only {len(prompt_text.strip())} visible chars",
        ))

    if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", prompt_html):
        issues.append(lint_issue(
            "med",
            "marker",
            "Prompt contains TODO/FIXME/XXX/HACK marker",
        ))

    no_math = prompt_without_inline_or_environment_math(stripped)
    if re.search(r"\\(frac|sum|prod|int|sqrt)\b", no_math):
        issues.append(lint_issue(
            "med",
            "unwrapped_latex",
            "LaTeX command appears outside `$...$` (won't render)",
        ))

    if re.search(r"\bFraction\(\s*-?\d+,\s*-?\d+\s*\)", prompt_html):
        issues.append(lint_issue(
            "high",
            "fraction_repr_leak",
            "Prompt contains a `Fraction(a, b)` Python repr — renderer didn't format it",
        ))

    return issues
