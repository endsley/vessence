"""Report scoring, filtering, and theme helpers for RA research summaries."""

from __future__ import annotations

from typing import Any

from agent_skills.ra_research_text import list_values, text_value


def summary_text_blob(summary: dict[str, Any]) -> str:
    fields = [
        summary.get("title", ""),
        summary.get("study_type", ""),
        summary.get("evidence_scope", ""),
        summary.get("remission_relevance", ""),
        summary.get("population", ""),
        summary.get("intervention_or_exposure", ""),
        " ".join(list_values(summary.get("main_findings"), max_items=8, max_chars=300)),
        " ".join(list_values(summary.get("limitations"), max_items=8, max_chars=300)),
    ]
    return " ".join(str(field) for field in fields if field).lower()


def summary_signal_score(summary: dict[str, Any]) -> int:
    text = summary_text_blob(summary)
    study_type = str(summary.get("study_type") or "").lower()
    scope = str(summary.get("evidence_scope") or "").lower()
    score = 0
    if "guideline" in study_type or "guideline" in scope:
        score += 6
    if "randomized" in study_type or "randomised" in study_type or "rct" in study_type:
        score += 5
    if "systematic" in study_type or "meta" in study_type:
        score += 4
    if "cohort" in study_type:
        score += 3
    if "review" in study_type:
        score += 2
    if "open_access_full_text" in scope or "guideline_or_review_page" in scope:
        score += 2
    if "abstract_only" in scope:
        score -= 1
    if list_values(summary.get("main_findings")):
        score += 1
    if list_values(summary.get("actionable_implications")) or list_values(summary.get("clinician_discussion_points")):
        score += 2
    if list_values(summary.get("tests_or_monitoring")):
        score += 2
    if list_values(summary.get("food_diet_implications")) or list_values(summary.get("lifestyle_implications")):
        score += 1
    if list_values(summary.get("technology_implications")):
        score += 1
    if summary.get("needs_llm_review"):
        score -= 5
    if "needs manual/llm review" in text:
        score -= 5
    if "does not directly address" in text or "did not directly address" in text or "not directly address" in text:
        score -= 3
    if "psoriatic arthritis" in text and "rheumatoid arthritis" not in text.replace("psoriatic arthritis", ""):
        score -= 4
    if "scenario" in text or "speculative" in text:
        score -= 2
    return score


def low_value_reason(summary: dict[str, Any]) -> str:
    text = summary_text_blob(summary)
    reasons: list[str] = []
    if summary.get("needs_llm_review") or "needs manual/llm review" in text:
        reasons.append("needs manual review before relying on it")
    if "abstract_only" in str(summary.get("evidence_scope") or "").lower():
        reasons.append("abstract-only")
    if "does not directly address" in text or "did not directly address" in text or "not directly address" in text:
        reasons.append("does not directly answer remission/asymptomatic strategy")
    if "psoriatic arthritis" in text and "rheumatoid arthritis" not in text.replace("psoriatic arthritis", ""):
        reasons.append("not actually RA-focused")
    if "scenario" in text or "speculative" in text:
        reasons.append("speculative/future-facing rather than actionable")
    return "; ".join(reasons)


def is_strong_evidence_type(summary: dict[str, Any]) -> bool:
    study_type = str(summary.get("study_type") or "").lower()
    scope = str(summary.get("evidence_scope") or "").lower()
    return any(
        needle in study_type or needle in scope
        for needle in ("guideline", "randomized", "randomised", "rct", "systematic", "meta")
    )


def is_low_value_summary(summary: dict[str, Any]) -> bool:
    reason = low_value_reason(summary)
    if not reason:
        return False
    score = summary_signal_score(summary)
    reasons = [part.strip() for part in reason.split(";") if part.strip()]
    serious_reasons = [part for part in reasons if part != "abstract-only"]
    if not serious_reasons:
        return score < 2
    if any("does not directly" in part for part in serious_reasons):
        return not (is_strong_evidence_type(summary) and score >= 7)
    return True


def evidence_label(summary: dict[str, Any]) -> str:
    parts = [
        text_value(summary.get("study_type", "unknown"), 80) or "unknown type",
        text_value(summary.get("evidence_scope", "unknown scope"), 80) or "unknown scope",
    ]
    return ", ".join(parts)


def is_usable_report_item(item: str) -> bool:
    item_lower = item.lower()
    if not item.strip():
        return False
    if item_lower.startswith("no safety concerns"):
        return False
    if item_lower.startswith("safety outcomes were similar"):
        return False
    if item_lower.startswith("feasibility concerns"):
        return False
    if "sle" in item_lower or "lupus" in item_lower:
        return False
    return True


def filter_report_items(items: list[str]) -> list[str]:
    return [item for item in items if is_usable_report_item(item)]


def collect_report_items(
    summaries: list[dict[str, Any]],
    fields: tuple[str, ...],
    *,
    max_items: int,
    max_chars: int = 220,
) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for summary in summaries:
        for field in fields:
            for item in list_values(summary.get(field), max_items=6, max_chars=max_chars):
                if not is_usable_report_item(item):
                    continue
                key = item.lower()
                if key in seen:
                    continue
                items.append(item)
                seen.add(key)
                if len(items) >= max_items:
                    return items
    return items


def infer_report_themes(summaries: list[dict[str, Any]], limit: int = 4) -> list[str]:
    rules = [
        (
            "treat-to-target and remission scoring",
            ("treat to target", "t2t", "das28", "cdai", "sdai", "boolean", "outcome measure"),
        ),
        (
            "medication strategy",
            (
                "methotrexate",
                "dmard",
                "biologic",
                "jak",
                "anti-tnf",
                "tofacitinib",
                "adalimumab",
                "upadacitinib",
                "otilimab",
            ),
        ),
        ("tapering or drug-free remission", ("taper", "discontinuation", "drug-free", "withdrawal", "dose reduction")),
        (
            "tests and biomarkers",
            ("biomarker", "anti-ccp", "rheumatoid factor", "crp", "esr", "granulocyte", "imaging", "ultrasound", "mri"),
        ),
        (
            "lifestyle and diet adjuncts",
            ("diet", "exercise", "sleep", "stress", "omega", "vitamin", "smoking", "periodontal", "lifestyle"),
        ),
        (
            "neuromodulation and technology",
            ("vagus", "neuromodulation", "bioelectronic", "auricular", "wearable", "digital", "car t", "genomic"),
        ),
        ("safety and comorbidities", ("safety", "infection", "cardiovascular", "lipid", "steroid", "adverse")),
    ]
    counts: dict[str, int] = {}
    for summary in summaries:
        text = summary_text_blob(summary)
        for theme, needles in rules:
            if any(needle in text for needle in needles):
                counts[theme] = counts.get(theme, 0) + 1
    return [theme for theme, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]]
