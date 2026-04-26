"""Stage-2 LLM summaries for marketplace saved searches.

Given a saved search's harvested listings, asks the local Stage-2 model
(qwen2.5:7b via Ollama by default) for a short brief: pricing patterns,
outliers worth looking at, and one or two things to watch out for. The
output lives at ``<search_dir>/summary_ai.json`` so the UI can read it
without a fresh LLM call.

Runs as part of the nightly marketplace cron after the harvester.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from . import config as _cfg
from . import harvester as _harv

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get(
    "MARKETPLACE_SUMMARY_MODEL",
    os.environ.get("JANE_SUMMARIZER_MODEL",
                   os.environ.get("JANE_LOCAL_LLM", "qwen2.5:7b")))
TIMEOUT = float(os.environ.get("MARKETPLACE_SUMMARY_TIMEOUT", "90"))
NUM_CTX = int(os.environ.get("MARKETPLACE_SUMMARY_NUM_CTX", "8192"))


def _build_prompt(search: dict, listings: list[dict]) -> str:
    label = search.get("label", search.get("name", "this search"))
    queries = ", ".join(search.get("queries", []))
    filters = search.get("filters", {})
    rows = []
    for i, L in enumerate(listings, start=1):
        rows.append(
            f"{i}. ${(L.get('price') or 0):,} · "
            f"{(L.get('miles') or 0):,} mi · "
            f"year {L.get('year') or '?'} · "
            f"{L.get('title') or ''} · "
            f"{L.get('location') or ''}"
        )
    listing_block = "\n".join(rows) if rows else "(no listings passed the filter)"
    return (
        f"You are a car-buying assistant reviewing the latest results from "
        f"a saved Facebook Marketplace search called {label!r}.\n\n"
        f"Search queries: {queries}\n"
        f"Filters applied: min_price=${filters.get('min_price', 0)}, "
        f"max_price=${filters.get('max_price')}, "
        f"max_miles={filters.get('max_miles')}, "
        f"require_clean_title={filters.get('require_clean_title')}, "
        f"suspicion_filter={filters.get('suspicion_filter')}.\n\n"
        f"Listings that passed all filters:\n{listing_block}\n\n"
        f"Write a concise brief (3–6 bullet points, total under 150 words) covering:\n"
        f"  • the best-value listing(s) and why\n"
        f"  • pricing patterns (e.g. most come in between $X and $Y)\n"
        f"  • any outliers worth a closer look\n"
        f"  • one thing a buyer should watch out for given this data\n\n"
        f"Plain Markdown, no headings, no preamble. If there are no listings, "
        f"say so in one sentence and recommend widening the filters."
    )


def _call_ollama(prompt: str) -> str:
    body = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.3, "num_ctx": NUM_CTX, "num_predict": 400},
        "keep_alive": -1,
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(OLLAMA_URL, json=body)
        r.raise_for_status()
        return (r.json().get("response") or "").strip()


def summarize(search_name: str) -> dict:
    """Generate and save an AI summary for one search. Returns the record."""
    search = _cfg.get_search(search_name)
    if search is None:
        raise KeyError(f"no saved search named {search_name!r}")
    data = _harv.listings_for(search_name)
    listings = data.get("listings", [])
    prompt = _build_prompt({**search, "name": search_name}, listings)
    logger.info("summarizing %r (%d listings) with %s",
                search_name, len(listings), MODEL)
    try:
        text = _call_ollama(prompt)
    except Exception as e:
        logger.warning("summarizer failed for %s: %s", search_name, e)
        text = f"_(summary unavailable: {e})_"
    record = {
        "search": search_name,
        "model": MODEL,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "listing_count": len(listings),
        "last_refreshed": data.get("last_refreshed"),
        "summary": text,
    }
    out = _cfg.search_data_dir(search_name) / "summary_ai.json"
    out.write_text(json.dumps(record, indent=2))
    return record


def summarize_all() -> list[dict]:
    results = []
    for s in _cfg.list_searches():
        try:
            results.append(summarize(s["name"]))
        except Exception as e:
            logger.exception("summarize failed for %s: %s", s["name"], e)
            results.append({"search": s["name"], "error": str(e)})
    return results


def get_summary(search_name: str) -> dict | None:
    p = _cfg.search_data_dir(search_name) / "summary_ai.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        r = summarize(sys.argv[1])
        print(json.dumps({"search": r["search"], "bytes": len(r["summary"])},
                         indent=2))
    else:
        rs = summarize_all()
        print(json.dumps([{"search": r.get("search"),
                           "ok": "error" not in r,
                           "bytes": len(r.get("summary", ""))} for r in rs],
                         indent=2))
