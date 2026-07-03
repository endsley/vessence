"""Artifact naming and text extraction helpers for RA research."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from agent_skills.ra_research_text import clean_text


def slugify(value: str, max_len: int = 80) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-").lower()
    return (value or "source")[:max_len]


def html_to_text(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    return clean_text(soup.get_text(" "))


def pmc_xml_to_text(xml_text: str) -> str:
    soup = BeautifulSoup(xml_text, "xml")
    for tag in soup(["ref-list", "table-wrap", "fig", "permissions"]):
        tag.decompose()
    return clean_text(soup.get_text(" "))


def is_jats_article_xml(xml_text: str) -> bool:
    """Return True only for actual PMC/JATS article XML, not HTML wrappers."""
    try:
        soup = BeautifulSoup(xml_text, "xml")
        return soup.find("article") is not None and soup.find("body") is not None
    except Exception:
        return False


def source_folder(papers_dir: Path, record: dict[str, Any]) -> Path:
    title_slug = slugify(record.get("title") or record.get("source_id") or "source", 70)
    return papers_dir / f"{record['source_id']}_{title_slug}"


def pubmed_abstract_text(record: dict[str, Any]) -> str:
    return textwrap.dedent(
        f"""\
        Title: {record.get('title', '')}
        PMID: {record.get('pmid', '')}
        DOI: {record.get('doi', '')}
        PMCID: {record.get('pmcid', '')}
        Journal: {record.get('journal', '')}
        Published: {record.get('published', '')}
        URL: {record.get('url', '')}

        Abstract:
        {record.get('abstract', '')}
        """
    )


def web_source_record(source: dict[str, str], *, fetched_at: str) -> dict[str, str]:
    return {
        "source_type": "web_guideline",
        "source_id": f"web_{source['id']}",
        "title": source["title"],
        "url": source["url"],
        "kind": source.get("kind", ""),
        "fetched_at": fetched_at,
    }


def web_source_folder(papers_dir: Path, source: dict[str, str]) -> Path:
    return papers_dir / f"web_{source['id']}_{slugify(source['title'], 70)}"


def raw_source_suffix(content_type: str) -> str:
    if "xml" in content_type.lower():
        return ".xml"
    return ".html"
