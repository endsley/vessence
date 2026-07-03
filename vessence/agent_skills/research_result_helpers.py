"""Pure result-shaping helpers for research analyzer scripts."""
from __future__ import annotations

import json


def analyzer_missing_file_result() -> dict:
    return {"confidence": "low", "cause": "File not found", "fix": "", "source": "", "found": False}


def analyzer_no_solution_result() -> dict:
    return {
        "confidence": "low",
        "cause": "No clear solution in data",
        "fix": "",
        "source": "",
        "found": False,
    }


def analyzer_error_result(error: Exception | str) -> dict:
    return {"confidence": "low", "cause": f"Analysis Error: {error}", "fix": "", "source": "", "found": False}


def analyzer_result_from_model_content(content: str) -> dict:
    cleaned = content.strip()
    if "NO_SOLUTION_FOUND" in cleaned:
        return analyzer_no_solution_result()
    result = json.loads(cleaned)
    result["found"] = True
    return result


def extract_json_text(text: str) -> str:
    if "```json" in text:
        return text.split("```json")[1].split("```")[0]
    if "```" in text:
        return text.split("```")[1].split("```")[0]
    return text


def parse_research_note_json(text: str) -> dict:
    return json.loads(extract_json_text(text).strip())
