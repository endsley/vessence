"""Pure helpers for homework LLM conceptual review."""

from __future__ import annotations

from typing import Any, Callable


def build_llm_review_prompt(findings: list[Any], instructions: str) -> str:
    parts = [instructions]
    for finding in findings:
        text = (finding.prompt_text or "").strip()
        if not text:
            text = "<EMPTY PROMPT>"
        parts.append(
            f"\n[Q{finding.n}] (key={finding.key}, type={finding.answer_type or 'default'})\n{text}\n"
        )
    return "".join(parts)


def normalize_llm_review_response(raw: dict[str, Any]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for entry in raw.get("reviews", []):
        n = entry.get("n")
        if n is None:
            continue
        issues = []
        for issue in entry.get("issues", []) or []:
            sev = issue.get("severity") or "low"
            kind = issue.get("kind") or "llm_review"
            msg = issue.get("message") or ""
            if not msg:
                continue
            issues.append({
                "severity": sev,
                "kind": f"llm_{kind}",
                "message": msg,
            })
        out[int(n)] = issues
    return out


def run_batched_llm_review(
    findings: list[Any],
    *,
    instructions: str,
    completion_json: Callable[..., dict[str, Any]],
    model_tier: str = "agent",
    timeout: int = 240,
    batch_size: int = 10,
) -> dict[int, list[dict]]:
    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")

    out: dict[int, list[dict]] = {}
    errors: list[str] = []

    for start in range(0, len(findings), batch_size):
        chunk = findings[start:start + batch_size]
        if not chunk:
            continue
        prompt = build_llm_review_prompt(chunk, instructions)

        try:
            raw = completion_json(prompt, tier=model_tier, timeout=timeout)
        except Exception as exc:
            qs = ", ".join(str(finding.n) for finding in chunk)
            errors.append(f"batch [{qs}] failed: {exc}")
            continue

        out.update(normalize_llm_review_response(raw))

    if errors and not out:
        raise RuntimeError("; ".join(errors))
    if errors:
        out.setdefault(-1, []).append({
            "severity": "low",
            "kind": "llm_partial_failure",
            "message": "; ".join(errors),
        })
    return out
