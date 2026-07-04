"""Saved Daily Briefing article context selection."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from jane.config import VESSENCE_DATA_HOME

MAX_SAVED_ARTICLE_CONTEXT_CHARS = 5000

ARTICLE_REFERENCE_KEYWORDS = (
    "article", "story", "piece", "daily brief", "daily briefing", "briefing",
    "saved article", "saved articles", "news", "headline",
)


def article_query_terms(message: str) -> set[str]:
    stop = {
        "about", "after", "again", "article", "articles", "brief", "briefing",
        "could", "daily", "does", "from", "have", "into", "jane", "know",
        "more", "news", "piece", "read", "said", "save", "saved", "says",
        "some", "story", "that", "them", "there", "these", "this", "what",
        "when", "where", "which", "with", "would", "your",
    }
    return {
        term
        for term in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", (message or "").lower())
        if term not in stop
    }


def should_include_saved_articles(message: str) -> bool:
    lowered = (message or "").strip().lower()
    return any(keyword in lowered for keyword in ARTICLE_REFERENCE_KEYWORDS)


def saved_articles_index_path() -> Path:
    data_home = Path(os.environ.get("VESSENCE_DATA_HOME", VESSENCE_DATA_HOME))
    return data_home / "briefing_saved" / "saved.json"


def briefing_article_path(article_id: str) -> Path:
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    tools_dir = os.environ.get("TOOLS_DIR", os.path.join(ambient_base, "skills"))
    return Path(tools_dir) / "daily_briefing" / "essence_data" / "articles" / f"{article_id}.json"


def load_saved_article_entry_article(entry: dict) -> dict:
    article = entry.get("article")
    if isinstance(article, dict):
        return article
    article_id = str(entry.get("article_id") or "").strip()
    if not article_id or not re.match(r"^[a-zA-Z0-9_-]+$", article_id):
        return {}
    path = briefing_article_path(article_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def score_saved_article(message_terms: set[str], entry: dict, article: dict) -> int:
    haystacks = [
        str(entry.get("category") or ""),
        str(article.get("title") or ""),
        str(article.get("source") or ""),
        str(article.get("url") or ""),
        str(article.get("brief_summary") or ""),
        str(article.get("full_summary") or ""),
        str(article.get("full_text") or "")[:3000],
    ]
    score = 0
    for term in message_terms:
        for idx, haystack in enumerate(haystacks):
            if term in haystack.lower():
                score += 4 if idx <= 3 else 1
                break
    return score


def format_saved_article_context(entry: dict, article: dict, remaining_chars: int) -> str:
    article_id = str(entry.get("article_id") or article.get("id") or "").strip()
    category = str(entry.get("category") or "Uncategorized").strip()
    title = str(article.get("title") or article_id or "Untitled").strip()
    source = str(article.get("source") or "").strip()
    url = str(article.get("url") or "").strip()
    saved_at = str(entry.get("saved_at") or "").strip()
    summary = str(article.get("full_summary") or article.get("brief_summary") or "").strip()
    full_text = str(article.get("full_text") or "").strip()
    body = summary or full_text
    excerpt_budget = max(600, remaining_chars - 350)
    excerpt = " ".join(body.split())[:excerpt_budget].strip()
    parts = [
        f"Title: {title}",
        f"Category: {category}",
    ]
    if source:
        parts.append(f"Source: {source}")
    if saved_at:
        parts.append(f"Saved at: {saved_at}")
    if url:
        parts.append(f"URL: {url}")
    if excerpt:
        parts.append(f"Context excerpt: {excerpt}")
    return "\n".join(parts)


def load_saved_articles_index(path: Path | None = None) -> dict:
    path = path or saved_articles_index_path()
    if not path.exists():
        return {}
    try:
        saved = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return saved if isinstance(saved, dict) else {}


def saved_article_candidates(
    saved: dict,
    terms: set[str],
) -> list[tuple[int, str, dict, dict]]:
    candidates: list[tuple[int, str, dict, dict]] = []
    for _article_id, entry in saved.items():
        if not isinstance(entry, dict):
            continue
        article = load_saved_article_entry_article(entry)
        score = score_saved_article(terms, entry, article) if terms else 0
        saved_at = str(entry.get("saved_at") or "")
        candidates.append((score, saved_at, entry, article))
    return candidates


def ranked_saved_article_candidates(
    candidates: list[tuple[int, str, dict, dict]],
    terms: set[str],
) -> list[tuple[int, str, dict, dict]]:
    if terms and any(score > 0 for score, _saved_at, _entry, _article in candidates):
        candidates = [candidate for candidate in candidates if candidate[0] > 0]
    return sorted(candidates, key=lambda candidate: (candidate[0], candidate[1]), reverse=True)


def saved_article_context_sections(
    candidates: list[tuple[int, str, dict, dict]],
    *,
    max_chars: int = MAX_SAVED_ARTICLE_CONTEXT_CHARS,
    limit: int = 3,
) -> list[str]:
    sections: list[str] = []
    remaining = max_chars
    for score, _saved_at, entry, article in candidates[:limit]:
        block = format_saved_article_context(entry, article, remaining)
        if not block:
            continue
        if len(block) > remaining:
            block = block[:remaining].rstrip()
        sections.append(block)
        remaining -= len(block) + 80
        if remaining <= 800:
            break
    return sections


def build_saved_articles_context(message: str) -> str:
    if not should_include_saved_articles(message):
        return ""
    saved = load_saved_articles_index()
    if not saved:
        return ""

    terms = article_query_terms(message)
    candidates = saved_article_candidates(saved, terms)
    if not candidates:
        return ""
    candidates = ranked_saved_article_candidates(candidates, terms)
    sections = saved_article_context_sections(candidates)

    if not sections:
        return ""
    return (
        "These are the most relevant user-saved Daily Briefing articles for the current question. "
        "Use this article context when answering; if it is not enough, say what is missing.\n\n"
        + "\n\n---\n\n".join(sections)
    )
