"""NCBI/PubMed request and cache payload helpers for RA research."""

from __future__ import annotations

from typing import Any


def ncbi_params(extra: dict[str, Any], *, tool: str, email: str, api_key: str = "") -> dict[str, Any]:
    params = {"tool": tool, "email": email}
    if api_key.strip():
        params["api_key"] = api_key.strip()
    params.update(extra)
    return params


def pubmed_search_params(
    query: str,
    *,
    retmax: int,
    retstart: int,
    sort: str,
    tool: str,
    email: str,
    api_key: str = "",
) -> dict[str, Any]:
    return ncbi_params(
        {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax,
            "retstart": retstart,
            "sort": sort,
        },
        tool=tool,
        email=email,
        api_key=api_key,
    )


def pubmed_search_cache_payload(
    *,
    fetched_at: str,
    url: str,
    query: str,
    retmax: int,
    retstart: int,
    sort: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    return {
        "fetched_at": fetched_at,
        "url": url,
        "query": query,
        "retmax": retmax,
        "retstart": retstart,
        "sort": sort,
        "response": response,
    }


def pubmed_ids_from_search_response(data: dict[str, Any]) -> list[str]:
    return [str(pmid) for pmid in data.get("esearchresult", {}).get("idlist", [])]


def pubmed_fetch_params(
    pmids: list[str],
    *,
    tool: str,
    email: str,
    api_key: str = "",
) -> dict[str, Any]:
    return ncbi_params(
        {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
        tool=tool,
        email=email,
        api_key=api_key,
    )


def pubmed_fetch_cache_text(*, fetched_at: str, url: str, pmids: list[str], response_text: str) -> str:
    return "\n".join(
        [
            f"Fetched at: {fetched_at}",
            f"URL: {url}",
            f"PMIDs: {', '.join(pmids)}",
            "",
            response_text,
        ]
    )
