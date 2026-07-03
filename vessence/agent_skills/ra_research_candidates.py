"""Candidate-selection helpers for the RA research cron."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def collect_seed_candidates(
    seed_sources: Iterable[dict[str, Any]],
    processed_sources: dict[str, Any],
    max_new: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    candidates: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for source in seed_sources:
        source_id = f"web_{source['id']}"
        findings.append({"kind": "seed_web_source", "source_id": source_id, "source": source})
        if source_id not in processed_sources:
            candidates.append({"kind": "web", "source": source, "source_id": source_id})
            if len(candidates) >= max_new:
                return candidates, findings, True
    return candidates, findings, False


def pubmed_search_finding(
    profile: dict[str, Any],
    *,
    retstart: int,
    retmax: int,
    sort: str,
    pmids: list[str],
) -> dict[str, Any]:
    return {
        "kind": "pubmed_search_result",
        "profile": profile["name"],
        "query": profile["query"],
        "retstart": retstart,
        "retmax": retmax,
        "sort": sort,
        "pmids": pmids,
    }


def select_pubmed_candidates(
    pmids: Iterable[str],
    processed_sources: dict[str, Any],
    *,
    profile_name: str,
    max_candidates: int,
) -> tuple[list[dict[str, Any]], int]:
    candidates: list[dict[str, Any]] = []
    consumed_from_page = 0
    for pmid in pmids:
        consumed_from_page += 1
        source_id = f"pubmed_{pmid}"
        if source_id in processed_sources:
            continue
        candidates.append({"kind": "pubmed", "pmid": pmid, "source_id": source_id, "profile": profile_name})
        if len(candidates) >= max_candidates:
            break
    return candidates, consumed_from_page
