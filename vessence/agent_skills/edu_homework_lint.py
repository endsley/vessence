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


def lint_prompt(prompt_html: str, prompt_text: str) -> list[dict]:
    """Run cheap content checks on a question's prompt."""
    issues: list[dict] = []

    if "{{" in prompt_html or "{%" in prompt_html:
        issues.append({
            "severity": "high",
            "kind": "unrendered_jinja",
            "message": "Prompt contains unrendered Jinja delimiters ({{ or {%)",
        })

    stripped = re.sub(r"\$\$.*?\$\$", "", prompt_html, flags=re.DOTALL)
    dollar_count = stripped.count("$")
    if dollar_count % 2 != 0:
        issues.append({
            "severity": "high",
            "kind": "unbalanced_math",
            "message": f"Odd number of `$` delimiters ({dollar_count} unpaired)",
        })

    opens = prompt_html.count("{")
    closes = prompt_html.count("}")
    if abs(opens - closes) > 2:
        issues.append({
            "severity": "med",
            "kind": "brace_mismatch",
            "message": f"Brace imbalance: {opens} `{{` vs {closes} `}}`",
        })

    low = prompt_text.lower()
    for bad, good in _TYPOS.items():
        if re.search(rf"\b{re.escape(bad)}\b", low):
            issues.append({
                "severity": "med",
                "kind": "typo",
                "message": f"Likely typo: '{bad}' -> '{good}'",
            })

    if len(prompt_text.strip()) < 15:
        issues.append({
            "severity": "med",
            "kind": "short_prompt",
            "message": f"Prompt is only {len(prompt_text.strip())} visible chars",
        })

    if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", prompt_html):
        issues.append({
            "severity": "med",
            "kind": "marker",
            "message": "Prompt contains TODO/FIXME/XXX/HACK marker",
        })

    no_math = re.sub(r"\$[^$]*\$", "", stripped)
    no_math = re.sub(r"\\begin\{[^}]+\}.*?\\end\{[^}]+\}", "", no_math, flags=re.DOTALL)
    if re.search(r"\\(frac|sum|prod|int|sqrt)\b", no_math):
        issues.append({
            "severity": "med",
            "kind": "unwrapped_latex",
            "message": "LaTeX command appears outside `$...$` (won't render)",
        })

    if re.search(r"\bFraction\(\s*-?\d+,\s*-?\d+\s*\)", prompt_html):
        issues.append({
            "severity": "high",
            "kind": "fraction_repr_leak",
            "message": "Prompt contains a `Fraction(a, b)` Python repr — renderer didn't format it",
        })

    return issues
