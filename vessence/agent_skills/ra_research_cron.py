#!/usr/bin/env python3
"""Research rheumatoid arthritis remission evidence on a fixed cron cadence.

The job is intentionally evidence-caching first:
- PubMed/PMC and guideline sources are fetched online.
- Every source that is processed gets a saved artifact under the vault.
- Every processed source gets a JSON summary cache keyed by PMID/DOI/source URL.
- A living recommendation scheme and explicit action plan are regenerated from
  the cached summaries.

This is research support for Chieh and Kathia, not medical instruction. The
generated scheme must be discussed with Kathia's rheumatologist before any
medication, supplement, or treatment change.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import ADK_VENV_PYTHON, ENV_FILE_PATH, FRONTIER_MODEL, VESSENCE_DATA_HOME, VAULT_DIR
from jane_web.jane_v2.models import LOCAL_LLM, LOCAL_LLM_NUM_CTX

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - python-dotenv is present in Jane runtime
    load_dotenv = None

if load_dotenv:
    load_dotenv(ENV_FILE_PATH)


LOGGER = logging.getLogger("ra_research_cron")
TZ = ZoneInfo("America/New_York")

DATA_ROOT = Path(VESSENCE_DATA_HOME) / "research" / "rheumatoid_arthritis_remission"
VAULT_ROOT = Path(VAULT_DIR) / "research" / "rheumatoid_arthritis_remission"
PAPERS_DIR = VAULT_ROOT / "papers"
SUMMARY_DIR = VAULT_ROOT / "summaries"
REPORTS_DIR = VAULT_ROOT / "reports"
RECOMMENDATIONS_DIR = VAULT_ROOT / "recommendations"
CODEX_DIR = VAULT_ROOT / "codex_synthesis"
CONTEXT_DIR = VAULT_ROOT / "context"
CACHE_DIR = DATA_ROOT / "cache"
STATE_PATH = DATA_ROOT / "state.json"
RECOMMENDATION_PATH = VAULT_ROOT / "ra_remission_recommendation_scheme.md"
ACTION_PLAN_PATH = RECOMMENDATIONS_DIR / "recommendation_plan.md"
LATEST_ACTION_PLAN_PATH = RECOMMENDATIONS_DIR / "latest_recommendation_plan.md"
COMPRESSED_CONTEXT_PATH = CONTEXT_DIR / "compressed_context.md"
DISCOVERIES_PATH = VAULT_ROOT / "discoveries.md"
LATEST_CODEX_SYNTHESIS_PATH = CODEX_DIR / "latest_codex_synthesis.md"

RECIPIENT_EMAIL = os.environ.get("RA_RESEARCH_REPORT_TO", "chieh.t.wu@gmail.com")
REPORT_FROM_EMAIL = os.environ.get("RA_RESEARCH_REPORT_FROM", "julioprocess@gmail.com")
REPORT_INTERVAL_HOURS = int(os.environ.get("RA_RESEARCH_REPORT_INTERVAL_HOURS", "72"))
INITIAL_REPORT_AFTER_RUNS = int(os.environ.get("RA_RESEARCH_INITIAL_REPORT_AFTER_RUNS", "4"))
SMART_PROVIDER = os.environ.get("RA_RESEARCH_SMART_PROVIDER", "codex")
SMART_MODEL_LABEL = os.environ.get("RA_RESEARCH_SMART_MODEL_LABEL", FRONTIER_MODEL)
SMART_TIMEOUT_SECONDS = int(os.environ.get("RA_RESEARCH_SMART_TIMEOUT_SECONDS", "1200"))
NCBI_TOOL = os.environ.get("NCBI_TOOL", "jane_ra_research_cron")
NCBI_EMAIL = os.environ.get("NCBI_EMAIL", RECIPIENT_EMAIL)

MISSION_STATEMENT = (
    "Chieh's goal is to help his wife Kathia, who has rheumatoid arthritis, reach an "
    "asymptomatic state/sustained remission. The loop is not over until Chieh explicitly "
    "stops it or Kathia is confirmed asymptomatic. The research may investigate whether "
    "true cure/durable drug-free remission is possible, but it must not claim a cure or "
    "recommend unsupervised medication/supplement changes."
)

PUBMED_SEARCHES = [
    {
        "name": "core_remission_latest",
        "mode": "latest",
        "sort": "pub date",
        "retmax": 8,
        "query": (
            '("rheumatoid arthritis"[Title/Abstract] OR "Rheumatoid Arthritis"[MeSH]) '
            'AND (remission[Title/Abstract] OR "treat to target"[Title/Abstract] '
            'OR asymptomatic[Title/Abstract] OR "low disease activity"[Title/Abstract])'
        ),
    },
    {
        "name": "core_remission_backlog",
        "mode": "backlog",
        "sort": "relevance",
        "retmax": 8,
        "query": (
            '("rheumatoid arthritis"[Title/Abstract] OR "Rheumatoid Arthritis"[MeSH]) '
            'AND (remission[Title/Abstract] OR "treat to target"[Title/Abstract] '
            'OR "disease activity"[Title/Abstract])'
        ),
    },
    {
        "name": "therapeutics_backlog",
        "mode": "backlog",
        "sort": "relevance",
        "retmax": 8,
        "query": (
            '("rheumatoid arthritis"[Title/Abstract] OR "Rheumatoid Arthritis"[MeSH]) '
            'AND (methotrexate OR biologic OR "JAK inhibitor" OR DMARD OR tapering '
            'OR "shared decision") AND (remission OR "low disease activity")'
        ),
    },
    {
        "name": "lifestyle_adjuncts_backlog",
        "mode": "backlog",
        "sort": "relevance",
        "retmax": 8,
        "query": (
            '("rheumatoid arthritis"[Title/Abstract] OR "Rheumatoid Arthritis"[MeSH]) '
        'AND (diet OR "Mediterranean diet" OR exercise OR sleep OR stress OR '
        'microbiome OR "omega-3" OR smoking OR periodontal OR "vitamin D" OR '
        'fasting OR "anti-inflammatory diet")'
        ),
    },
    {
        "name": "tests_biomarkers_monitoring_backlog",
        "mode": "backlog",
        "sort": "relevance",
        "retmax": 8,
        "query": (
            '("rheumatoid arthritis"[Title/Abstract] OR "Rheumatoid Arthritis"[MeSH]) '
            'AND (biomarker OR biomarkers OR "anti-CCP" OR "rheumatoid factor" OR CRP OR ESR '
            'OR ultrasound OR MRI OR "disease activity score" OR CDAI OR SDAI OR DAS28) '
            'AND (remission OR prognosis OR monitoring)'
        ),
    },
    {
        "name": "neuromodulation_technology_backlog",
        "mode": "backlog",
        "sort": "relevance",
        "retmax": 8,
        "query": (
            '("rheumatoid arthritis"[Title/Abstract] OR "Rheumatoid Arthritis"[MeSH]) '
            'AND ("vagus nerve" OR "vagus nerve stimulation" OR neuromodulation OR bioelectronic '
            'OR "auricular stimulation" OR wearable OR digital)'
        ),
    },
    {
        "name": "patient_reported_asymptomatic_latest",
        "mode": "latest",
        "sort": "pub date",
        "retmax": 8,
        "query": (
            '("rheumatoid arthritis"[Title/Abstract] OR "Rheumatoid Arthritis"[MeSH]) '
            'AND ("patient global" OR pain OR fatigue OR "morning stiffness" OR '
            '"patient-reported outcome" OR function) AND remission'
        ),
    },
]

SEED_SOURCES = [
    {
        "id": "acr_2021_guideline_pmc",
        "title": "2021 American College of Rheumatology Guideline for the Treatment of Rheumatoid Arthritis",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC9273041/",
        "kind": "guideline",
    },
    {
        "id": "acr_ra_guideline_page",
        "title": "American College of Rheumatology Rheumatoid Arthritis Guideline Page",
        "url": "https://rheumatology.org/rheumatoid-arthritis-guideline",
        "kind": "guideline_index",
    },
    {
        "id": "eular_2022_dmard_recommendations",
        "title": "EULAR recommendations for the management of RA with synthetic and biological DMARDs: 2022 update",
        "url": "https://ard.bmj.com/content/82/1/3",
        "kind": "guideline",
    },
    {
        "id": "treat_to_target_2014_update",
        "title": "Treating rheumatoid arthritis to target: 2014 update",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4717393/",
        "kind": "recommendations",
    },
    {
        "id": "acr_eular_remission_criteria_2022",
        "title": "ACR/EULAR Remission Criteria for Rheumatoid Arthritis: 2022 Revision",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10092655/",
        "kind": "criteria",
    },
]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def local_now() -> dt.datetime:
    return dt.datetime.now(TZ)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return None


def slugify(value: str, max_len: int = 80) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-").lower()
    return (value or "source")[:max_len]


def ensure_dirs() -> None:
    for path in (
        DATA_ROOT,
        VAULT_ROOT,
        PAPERS_DIR,
        SUMMARY_DIR,
        REPORTS_DIR,
        RECOMMENDATIONS_DIR,
        CODEX_DIR,
        CONTEXT_DIR,
        CACHE_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: dict | list) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {
            "created_at": iso_now(),
            "processed_sources": {},
            "query_offsets": {},
            "last_report_sent_at": None,
            "last_report_source_count": 0,
            "initial_report_sent": False,
            "run_count": 0,
            "status": "active_until_chieh_stops_or_kathia_confirmed_asymptomatic",
            "mission": MISSION_STATEMENT,
        }
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        LOGGER.exception("State file was unreadable; starting with empty state")
        return {
            "created_at": iso_now(),
            "processed_sources": {},
            "query_offsets": {},
            "last_report_sent_at": None,
            "last_report_source_count": 0,
            "initial_report_sent": False,
            "run_count": 0,
            "status": "active_until_chieh_stops_or_kathia_confirmed_asymptomatic",
            "mission": MISSION_STATEMENT,
        }


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = iso_now()
    atomic_write_json(STATE_PATH, state)


def http_get(url: str, *, params: dict[str, Any] | None = None, timeout: int = 30) -> requests.Response:
    headers = {
        "User-Agent": "JaneRAResearchCron/1.0 (personal research assistant; contact chieh.t.wu@gmail.com)"
    }
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response


def ncbi_params(extra: dict[str, Any]) -> dict[str, Any]:
    params = {"tool": NCBI_TOOL, "email": NCBI_EMAIL}
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key
    params.update(extra)
    return params


def pubmed_search(
    query: str,
    *,
    retmax: int,
    retstart: int,
    sort: str,
    cache_path: Path | None = None,
) -> list[str]:
    response = http_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params=ncbi_params(
            {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": retmax,
                "retstart": retstart,
                "sort": sort,
            }
        ),
        timeout=30,
    )
    data = response.json()
    if cache_path:
        atomic_write_json(
            cache_path,
            {
                "fetched_at": iso_now(),
                "url": response.url,
                "query": query,
                "retmax": retmax,
                "retstart": retstart,
                "sort": sort,
                "response": data,
            },
        )
    return [str(pmid) for pmid in data.get("esearchresult", {}).get("idlist", [])]


def pubmed_fetch(pmids: list[str], *, cache_path: Path | None = None) -> list[dict[str, Any]]:
    if not pmids:
        return []
    response = http_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        params=ncbi_params({"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}),
        timeout=45,
    )
    if cache_path:
        atomic_write_text(
            cache_path,
            "\n".join(
                [
                    f"Fetched at: {iso_now()}",
                    f"URL: {response.url}",
                    f"PMIDs: {', '.join(pmids)}",
                    "",
                    response.text,
                ]
            ),
        )
    root = ET.fromstring(response.text)
    records = []
    for article in root.findall(".//PubmedArticle"):
        parsed = parse_pubmed_article(article)
        if parsed:
            records.append(parsed)
    return records


def text_of(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def parse_pub_date(article: ET.Element) -> str:
    article_date = article.find(".//ArticleDate")
    if article_date is not None:
        year = text_of(article_date.find("Year"))
        month = text_of(article_date.find("Month")) or "01"
        day = text_of(article_date.find("Day")) or "01"
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}" if year else ""

    pub_date = article.find(".//JournalIssue/PubDate")
    if pub_date is None:
        return ""
    year = text_of(pub_date.find("Year"))
    month = text_of(pub_date.find("Month"))
    day = text_of(pub_date.find("Day")) or "01"
    month_map = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
        "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
    }
    if month and not month.isdigit():
        month = month_map.get(month[:3], "01")
    month = (month or "01").zfill(2)
    return f"{year}-{month}-{day.zfill(2)}" if year else text_of(pub_date)


def parse_authors(article: ET.Element, limit: int = 12) -> list[str]:
    authors = []
    for author in article.findall(".//AuthorList/Author")[:limit]:
        last = text_of(author.find("LastName"))
        fore = text_of(author.find("ForeName"))
        collective = text_of(author.find("CollectiveName"))
        name = collective or " ".join(part for part in (fore, last) if part)
        if name:
            authors.append(name)
    return authors


def parse_article_ids(article: ET.Element) -> dict[str, str]:
    ids: dict[str, str] = {}
    for node in article.findall(".//ArticleIdList/ArticleId"):
        id_type = (node.attrib.get("IdType") or "").lower()
        value = text_of(node)
        if id_type and value:
            ids[id_type] = value
    return ids


def parse_pubmed_article(article: ET.Element) -> dict[str, Any] | None:
    pmid = text_of(article.find(".//PMID"))
    if not pmid:
        return None
    ids = parse_article_ids(article)
    abstract_parts = []
    for node in article.findall(".//Abstract/AbstractText"):
        label = node.attrib.get("Label") or node.attrib.get("NlmCategory") or ""
        content = text_of(node)
        if content:
            abstract_parts.append(f"{label}: {content}" if label else content)
    title = text_of(article.find(".//ArticleTitle"))
    journal = text_of(article.find(".//Journal/Title")) or text_of(article.find(".//Journal/ISOAbbreviation"))
    publication_types = [text_of(node) for node in article.findall(".//PublicationTypeList/PublicationType")]
    mesh_terms = [text_of(node.find("DescriptorName")) for node in article.findall(".//MeshHeadingList/MeshHeading")]
    return {
        "source_type": "pubmed",
        "source_id": f"pubmed_{pmid}",
        "pmid": pmid,
        "pmcid": ids.get("pmc", ""),
        "doi": ids.get("doi", ""),
        "title": title,
        "journal": journal,
        "published": parse_pub_date(article),
        "authors": parse_authors(article),
        "abstract": "\n".join(abstract_parts),
        "publication_types": [p for p in publication_types if p],
        "mesh_terms": [m for m in mesh_terms if m],
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


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


def source_folder(record: dict[str, Any]) -> Path:
    title_slug = slugify(record.get("title") or record.get("source_id") or "source", 70)
    return PAPERS_DIR / f"{record['source_id']}_{title_slug}"


def save_pubmed_artifacts(record: dict[str, Any]) -> tuple[Path, str, str]:
    """Save metadata, abstract, and open-access full text/PDF when available."""
    folder = source_folder(record)
    folder.mkdir(parents=True, exist_ok=True)
    atomic_write_json(folder / "metadata.json", record)

    abstract_text = textwrap.dedent(
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
    atomic_write_text(folder / "abstract.txt", abstract_text)

    evidence_scope = "abstract_only"
    readable_text = abstract_text
    pmcid = (record.get("pmcid") or "").strip()
    if pmcid:
        if not pmcid.upper().startswith("PMC"):
            pmcid = f"PMC{pmcid}"
        try:
            xml_resp = http_get(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/?report=xml", timeout=45)
            xml_path = folder / f"{pmcid}_report_response.xml"
            atomic_write_text(xml_path, xml_resp.text)
            if is_jats_article_xml(xml_resp.text):
                full_text = pmc_xml_to_text(xml_resp.text)
                atomic_write_text(folder / "full_text.txt", full_text)
                readable_text = full_text
                evidence_scope = "open_access_full_text"
            else:
                LOGGER.info("PMC report response for %s was not article XML; kept as raw artifact only", pmcid)
        except Exception as exc:
            LOGGER.info("PMC full-text fetch failed for %s: %s", pmcid, exc)

        time.sleep(0.35)
        try:
            pdf_resp = http_get(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/", timeout=45)
            content_type = pdf_resp.headers.get("content-type", "").lower()
            if "pdf" in content_type or pdf_resp.content.startswith(b"%PDF"):
                pdf_path = folder / f"{pmcid}.pdf"
                pdf_path.write_bytes(pdf_resp.content)
        except Exception as exc:
            LOGGER.info("PMC PDF fetch failed for %s: %s", pmcid, exc)

    return folder, readable_text, evidence_scope


def save_web_source_artifacts(source: dict[str, str]) -> tuple[Path, str, str]:
    source_id = f"web_{source['id']}"
    folder = PAPERS_DIR / f"{source_id}_{slugify(source['title'], 70)}"
    folder.mkdir(parents=True, exist_ok=True)
    record = {
        "source_type": "web_guideline",
        "source_id": source_id,
        "title": source["title"],
        "url": source["url"],
        "kind": source.get("kind", ""),
        "fetched_at": iso_now(),
    }
    response = http_get(source["url"], timeout=45)
    suffix = ".html"
    if "xml" in response.headers.get("content-type", "").lower():
        suffix = ".xml"
    raw_path = folder / f"source{suffix}"
    if suffix == ".html":
        atomic_write_text(raw_path, response.text)
        readable_text = html_to_text(response.text)
    else:
        atomic_write_text(raw_path, response.text)
        readable_text = pmc_xml_to_text(response.text)
    atomic_write_json(folder / "metadata.json", record)
    atomic_write_text(folder / "readable_text.txt", readable_text)
    return folder, readable_text, "guideline_or_review_page"


def ollama_chat_json(system_prompt: str, user_prompt: str, *, timeout: int = 120) -> dict[str, Any] | None:
    base = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    base = base.rstrip("/")
    if base.endswith("/api/generate") or base.endswith("/api/chat"):
        base = base.rsplit("/api/", 1)[0]
    model = os.environ.get("RA_RESEARCH_MODEL", LOCAL_LLM)
    try:
        response = requests.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "keep_alive": -1,
                "options": {"num_ctx": LOCAL_LLM_NUM_CTX, "temperature": 0.1},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        text = response.json().get("message", {}).get("content", "")
        return parse_json_from_text(text)
    except Exception as exc:
        LOGGER.warning("Local LLM JSON call failed: %s", exc)
        return None


def ollama_chat_text(system_prompt: str, user_prompt: str, *, timeout: int = 180) -> str | None:
    base = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    base = base.rstrip("/")
    if base.endswith("/api/generate") or base.endswith("/api/chat"):
        base = base.rsplit("/api/", 1)[0]
    model = os.environ.get("RA_RESEARCH_MODEL", LOCAL_LLM)
    try:
        response = requests.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "keep_alive": -1,
                "options": {"num_ctx": LOCAL_LLM_NUM_CTX, "temperature": 0.1},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()
    except Exception as exc:
        LOGGER.warning("Local LLM text call failed: %s", exc)
        return None


def parse_json_from_text(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def fallback_summary(record: dict[str, Any], evidence_scope: str, artifact_dir: Path, text: str) -> dict[str, Any]:
    first_sentence = clean_text(text).split(". ")[0][:500]
    return {
        "source_id": record["source_id"],
        "title": record.get("title", ""),
        "citation": citation_for(record),
        "url": record.get("url", ""),
        "evidence_scope": evidence_scope,
        "study_type": ", ".join(record.get("publication_types", [])[:4]) or record.get("kind", "unknown"),
        "population": "Not extracted by fallback summarizer.",
        "intervention_or_exposure": "Not extracted by fallback summarizer.",
        "main_findings": [first_sentence] if first_sentence else [],
        "remission_relevance": "Needs manual/LLM review; source was saved and cached.",
        "safety_concerns": [],
        "actionable_implications": [],
        "tests_or_monitoring": [],
        "food_diet_implications": [],
        "lifestyle_implications": [],
        "technology_implications": [],
        "limitations": ["Fallback summary because local LLM was unavailable or returned invalid JSON."],
        "clinician_discussion_points": [],
        "artifact_dir": str(artifact_dir),
        "needs_llm_review": True,
        "summarized_at": iso_now(),
    }


def source_cache_key(record: dict[str, Any]) -> str:
    for key in ("pmid", "pmcid", "doi", "source_id", "url"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return record["source_id"]


def citation_for(record: dict[str, Any]) -> str:
    authors = record.get("authors") or []
    author_part = ", ".join(authors[:3])
    if len(authors) > 3:
        author_part += " et al."
    return " ".join(
        part
        for part in [
            author_part,
            f"({record.get('published')})" if record.get("published") else "",
            record.get("title", ""),
            record.get("journal", ""),
            f"PMID:{record.get('pmid')}" if record.get("pmid") else "",
            f"DOI:{record.get('doi')}" if record.get("doi") else "",
        ]
        if part
    )


def summarize_source(record: dict[str, Any], artifact_dir: Path, readable_text: str, evidence_scope: str) -> dict[str, Any]:
    summary_path = SUMMARY_DIR / f"{record['source_id']}.json"
    existing_summary: dict[str, Any] | None = None
    if summary_path.exists():
        try:
            existing_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if not existing_summary.get("needs_llm_review"):
                return existing_summary
        except Exception:
            existing_summary = None

    system_prompt = (
        "You are an evidence reviewer helping Jane maintain a rheumatoid arthritis remission research dossier. "
        "You are not providing medical care. Extract only what is supported by the supplied source. "
        "If the source is abstract-only, state that limitation plainly. "
        "Return one valid JSON object and no prose."
    )
    user_prompt = json.dumps(
        {
            "mission": MISSION_STATEMENT,
            "task": "Summarize this source for an RA remission/asymptomatic-state recommendation scheme.",
            "required_schema": {
                "source_id": "string",
                "title": "string",
                "citation": "string",
                "url": "string",
                "evidence_scope": evidence_scope,
                "study_type": "guideline|RCT|cohort|systematic_review|mechanistic|case_series|other",
                "population": "string",
                "intervention_or_exposure": "string",
                "main_findings": ["short bullets"],
                "remission_relevance": "how this affects remission/asymptomatic strategy",
                "safety_concerns": ["risks, contraindications, uncertainty"],
                "actionable_implications": ["clinician-discussion or lifestyle-tracking ideas only"],
                "tests_or_monitoring": ["labs, imaging, biomarkers, symptom scores, clinician measurements mentioned"],
                "food_diet_implications": ["food, diet, nutrition, supplement implications if any"],
                "lifestyle_implications": ["exercise, sleep, stress, oral health, smoking, weight/metabolic implications if any"],
                "technology_implications": ["vagus nerve stimulation, neuromodulation, wearables, digital monitoring, other technology implications if any"],
                "limitations": ["limitations"],
                "clinician_discussion_points": ["questions for rheumatologist"],
            },
            "source_metadata": record,
            "citation": citation_for(record),
            "source_text": readable_text[:24000],
        },
        ensure_ascii=False,
    )
    summary = ollama_chat_json(system_prompt, user_prompt)
    if summary is None and existing_summary is not None:
        return existing_summary
    if summary is None:
        summary = fallback_summary(record, evidence_scope, artifact_dir, readable_text)
    else:
        summary["needs_llm_review"] = False

    summary.setdefault("source_id", record["source_id"])
    summary.setdefault("title", record.get("title", ""))
    summary.setdefault("citation", citation_for(record))
    summary.setdefault("url", record.get("url", ""))
    summary.setdefault("evidence_scope", evidence_scope)
    summary["artifact_dir"] = str(artifact_dir)
    summary["cache_key"] = source_cache_key(record)
    summary["summarized_at"] = iso_now()
    atomic_write_json(summary_path, summary)
    atomic_write_text(SUMMARY_DIR / f"{record['source_id']}.md", summary_to_markdown(summary))
    return summary


def summary_to_markdown(summary: dict[str, Any]) -> str:
    def list_md(values: Any) -> str:
        if isinstance(values, list) and values:
            return "\n".join(f"- {clean_text(str(v))}" for v in values if str(v).strip())
        if values:
            return f"- {clean_text(str(values))}"
        return "- None captured."

    return textwrap.dedent(
        f"""\
        # {summary.get('title', 'Untitled source')}

        - Source ID: `{summary.get('source_id', '')}`
        - Citation: {summary.get('citation', '')}
        - URL: {summary.get('url', '')}
        - Evidence scope: {summary.get('evidence_scope', '')}
        - Study type: {summary.get('study_type', '')}
        - Saved artifact directory: `{summary.get('artifact_dir', '')}`

        ## Population
        {summary.get('population', '')}

        ## Intervention Or Exposure
        {summary.get('intervention_or_exposure', '')}

        ## Main Findings
        {list_md(summary.get('main_findings'))}

        ## Remission Relevance
        {summary.get('remission_relevance', '')}

        ## Actionable Implications
        {list_md(summary.get('actionable_implications'))}

        ## Tests Or Monitoring
        {list_md(summary.get('tests_or_monitoring'))}

        ## Food / Diet Implications
        {list_md(summary.get('food_diet_implications'))}

        ## Lifestyle Implications
        {list_md(summary.get('lifestyle_implications'))}

        ## Technology Implications
        {list_md(summary.get('technology_implications'))}

        ## Safety Concerns
        {list_md(summary.get('safety_concerns'))}

        ## Limitations
        {list_md(summary.get('limitations'))}

        ## Clinician Discussion Points
        {list_md(summary.get('clinician_discussion_points'))}
        """
    ).strip() + "\n"


def collect_candidate_sources(state: dict[str, Any], max_new: int, run_cache_dir: Path) -> list[dict[str, Any]]:
    processed = state.setdefault("processed_sources", {})
    candidates: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []

    for source in SEED_SOURCES:
        source_id = f"web_{source['id']}"
        all_findings.append({"kind": "seed_web_source", "source_id": source_id, "source": source})
        if source_id not in processed:
            candidates.append({"kind": "web", "source": source, "source_id": source_id})
            if len(candidates) >= max_new:
                atomic_write_json(run_cache_dir / "all_candidate_findings.json", all_findings)
                atomic_write_json(run_cache_dir / "selected_candidates.json", candidates)
                return candidates

    query_offsets = state.setdefault("query_offsets", {})
    for profile in PUBMED_SEARCHES:
        if len(candidates) >= max_new:
            break
        retmax = int(profile.get("retmax", 8))
        retstart = 0 if profile["mode"] == "latest" else int(query_offsets.get(profile["name"], 0))
        try:
            pmids = pubmed_search(
                profile["query"],
                retmax=retmax,
                retstart=retstart,
                sort=profile.get("sort", "pub date"),
                cache_path=run_cache_dir / f"pubmed_search_{slugify(profile['name'])}_{retstart}.json",
            )
            time.sleep(0.35)
        except Exception as exc:
            LOGGER.warning("PubMed search failed for %s: %s", profile["name"], exc)
            continue
        all_findings.append(
            {
                "kind": "pubmed_search_result",
                "profile": profile["name"],
                "query": profile["query"],
                "retstart": retstart,
                "retmax": retmax,
                "sort": profile.get("sort", "pub date"),
                "pmids": pmids,
            }
        )
        consumed_from_page = 0
        for pmid in pmids:
            consumed_from_page += 1
            source_id = f"pubmed_{pmid}"
            if source_id in processed:
                continue
            candidates.append({"kind": "pubmed", "pmid": pmid, "source_id": source_id, "profile": profile["name"]})
            if len(candidates) >= max_new:
                break
        if profile["mode"] == "backlog":
            query_offsets[profile["name"]] = retstart + consumed_from_page
    atomic_write_json(run_cache_dir / "all_candidate_findings.json", all_findings)
    atomic_write_json(run_cache_dir / "selected_candidates.json", candidates)
    return candidates


def process_candidates(candidates: list[dict[str, Any]], state: dict[str, Any], run_cache_dir: Path) -> list[dict[str, Any]]:
    processed_summaries = []
    processed = state.setdefault("processed_sources", {})

    pubmed_pmids = [c["pmid"] for c in candidates if c["kind"] == "pubmed"]
    pubmed_records = (
        {
            r["pmid"]: r
            for r in pubmed_fetch(
                pubmed_pmids,
                cache_path=run_cache_dir / f"pubmed_efetch_{local_now().strftime('%Y%m%d_%H%M%S')}.xml",
            )
        }
        if pubmed_pmids
        else {}
    )
    if pubmed_pmids:
        time.sleep(0.35)

    for candidate in candidates:
        source_id = candidate["source_id"]
        if source_id in processed:
            continue
        try:
            if candidate["kind"] == "web":
                artifact_dir, readable_text, evidence_scope = save_web_source_artifacts(candidate["source"])
                record = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
            else:
                record = pubmed_records.get(candidate["pmid"])
                if not record:
                    LOGGER.warning("PMID %s was not returned by efetch", candidate["pmid"])
                    continue
                artifact_dir, readable_text, evidence_scope = save_pubmed_artifacts(record)

            summary = summarize_source(record, artifact_dir, readable_text, evidence_scope)
            processed[source_id] = {
                "title": record.get("title", ""),
                "url": record.get("url", ""),
                "processed_at": iso_now(),
                "artifact_dir": str(artifact_dir),
                "summary_path": str(SUMMARY_DIR / f"{source_id}.json"),
                "evidence_scope": evidence_scope,
                "cache_key": source_cache_key(record),
            }
            processed_summaries.append(summary)
            LOGGER.info("Processed %s: %s", source_id, record.get("title", "")[:120])
        except Exception as exc:
            LOGGER.exception("Failed to process %s: %s", source_id, exc)
        time.sleep(0.35)

    return processed_summaries


def readable_text_from_artifact(artifact_dir: Path) -> str:
    for name in ("full_text.txt", "readable_text.txt", "abstract.txt"):
        path = artifact_dir / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
    return ""


def retry_pending_llm_reviews(state: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """Re-upgrade degraded fallback summaries once the local LLM is healthy."""
    upgraded: list[dict[str, Any]] = []
    processed = state.get("processed_sources", {})
    for summary_path in sorted(SUMMARY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
        if len(upgraded) >= limit:
            break
        try:
            existing = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not existing.get("needs_llm_review"):
            continue
        source_id = existing.get("source_id") or summary_path.stem
        entry = processed.get(source_id, {})
        artifact_dir = Path(entry.get("artifact_dir") or existing.get("artifact_dir") or "")
        if not artifact_dir.exists():
            continue
        metadata_path = artifact_dir / "metadata.json"
        if not metadata_path.exists():
            continue
        try:
            record = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        readable_text = readable_text_from_artifact(artifact_dir)
        if not readable_text:
            continue
        before_mtime = summary_path.stat().st_mtime
        summary = summarize_source(record, artifact_dir, readable_text, entry.get("evidence_scope") or existing.get("evidence_scope", "unknown"))
        if not summary.get("needs_llm_review") and summary_path.stat().st_mtime >= before_mtime:
            upgraded.append(summary)
            LOGGER.info("Upgraded fallback summary for %s", source_id)
    return upgraded


def load_all_summaries(limit: int = 120) -> list[dict[str, Any]]:
    summaries = []
    for path in sorted(SUMMARY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            summaries.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        if len(summaries) >= limit:
            break
    return summaries


def compact_summary_payload(summaries: list[dict[str, Any]], limit: int = 120) -> list[dict[str, Any]]:
    payload = []
    for summary in summaries[:limit]:
        payload.append(
            {
                "source_id": summary.get("source_id", ""),
                "title": summary.get("title", ""),
                "citation": summary.get("citation", ""),
                "url": summary.get("url", ""),
                "scope": summary.get("evidence_scope", ""),
                "type": summary.get("study_type", ""),
                "findings": summary.get("main_findings", []),
                "relevance": summary.get("remission_relevance", ""),
                "actions": summary.get("actionable_implications", []),
                "tests_or_monitoring": summary.get("tests_or_monitoring", []),
                "food_diet": summary.get("food_diet_implications", []),
                "lifestyle": summary.get("lifestyle_implications", []),
                "technology": summary.get("technology_implications", []),
                "safety": summary.get("safety_concerns", []),
                "limitations": summary.get("limitations", []),
                "clinician_questions": summary.get("clinician_discussion_points", []),
                "artifact_dir": summary.get("artifact_dir", ""),
            }
        )
    return payload


def previous_context_text() -> str:
    if COMPRESSED_CONTEXT_PATH.exists():
        try:
            return COMPRESSED_CONTEXT_PATH.read_text(encoding="utf-8")[:30000]
        except Exception:
            return ""
    return ""


def run_codex_synthesis(
    summaries: list[dict[str, Any]],
    new_summaries: list[dict[str, Any]],
    run_cache_dir: Path,
) -> dict[str, Any] | None:
    """Ask the smartest configured model to re-read the evidence state.

    The default provider is Codex/OpenAI using the configured frontier model
    label. The fallback path is local deterministic/LLM synthesis, but the cron
    stores the failure so it is visible instead of silent.
    """
    prompt_payload = {
        "mission": MISSION_STATEMENT,
        "safety_boundary": (
            "You are building a traceable research dossier, not giving medical advice. "
            "Do not recommend unsupervised medication, biologic/JAK inhibitor, steroid, NSAID, "
            "supplement, diet, or treatment changes. Frame concrete next steps as clinician "
            "discussion points or tracking tasks."
        ),
        "model_policy": (
            f"Use the smartest available Jane model for this task. Current configured frontier model label: "
            f"{SMART_MODEL_LABEL}. Provider requested by cron: {SMART_PROVIDER}."
        ),
        "instructions": [
            "Re-read everything found so far from the compressed context and source summaries.",
            "Reiterate the mission: help Kathia reach an asymptomatic state/sustained remission; investigate cure/drug-free remission carefully without promising it.",
            "Compress everything learned so far into a concise context summary for the next cron run.",
            "Update the recommendation scheme using only cached evidence summaries.",
            "Combine all cached research into a practical recommendation plan with specific categories: tests/labs/imaging to discuss, food/diet, lifestyle, medications/medical strategy, supplements only if evidence/safety supports clinician discussion, and emerging technologies such as vagus-nerve stimulation.",
            "For every recommendation, include evidence strength, source IDs, why it might help symptoms/remission, safety caveats, and whether it is actionable at home now, a tracking/logging step, or only a clinician discussion point.",
            "Be medically conservative: no unsupervised medication, supplement, or treatment changes.",
            "Preserve source IDs and artifact paths so Jane can trace every claim.",
        ],
        "previous_compressed_context": previous_context_text(),
        "new_source_ids_this_run": [s.get("source_id", "") for s in new_summaries],
        "all_cached_source_summaries": compact_summary_payload(summaries, limit=140),
        "required_output": {
            "format": "strict JSON object only",
            "keys": {
                "mission_restatement": "short paragraph",
                "compressed_context": "Markdown context for next run, <=2500 words",
                "recommendation_scheme_markdown": "full Markdown scheme with sections: Status, Safety Boundary, Working Model, Recommendation Scheme, Tracking Checklist, Clinician Questions, Evidence Register, New Evidence This Run, Next Research Questions",
                "recommendation_plan_markdown": "action-oriented Markdown with sections: Executive Summary, At-Home Actions Now, Tracking Steps, Tests To Discuss, Food/Diet Options, Lifestyle Changes, Medical Strategy Questions, Emerging Technology/Neuromodulation, What Not To Do Without Clinician, Evidence Matrix, What Would Change This Plan",
                "discoveries": ["high-signal discoveries or changed beliefs this run"],
                "open_questions": ["specific research questions for future runs"],
                "safety_flags": ["risks or places requiring rheumatologist discussion"],
            },
        },
    }
    prompt = (
        "You are Jane's highest-judgment RA research synthesis pass. You are a careful "
        "medical-literature synthesis assistant, not a treating clinician. Output strict JSON only.\n\n"
        + json.dumps(prompt_payload, ensure_ascii=False)
    )
    atomic_write_json(run_cache_dir / "codex_prompt_payload.json", prompt_payload)

    try:
        from jane.automation_runner import run_automation_prompt

        response = run_automation_prompt(
            prompt,
            system_prompt=(
                "You are a careful medical-literature synthesis assistant. "
                "You do not provide medical advice; you build a traceable research dossier."
            ),
            timeout_seconds=SMART_TIMEOUT_SECONDS,
            provider=SMART_PROVIDER,
            workdir=str(Path(__file__).resolve().parents[1]),
        )
        atomic_write_text(run_cache_dir / "codex_raw_response.txt", response)
        parsed = parse_json_from_text(response)
        if parsed:
            return parsed
        LOGGER.warning("Codex synthesis returned non-JSON output")
        return {
            "mission_restatement": MISSION_STATEMENT,
            "compressed_context": response[:12000],
            "recommendation_scheme_markdown": "",
            "recommendation_plan_markdown": "",
            "discoveries": ["Codex returned non-JSON output; raw response cached."],
            "open_questions": [],
            "safety_flags": [],
        }
    except Exception as exc:
        LOGGER.warning("Codex synthesis failed: %s", exc)
        atomic_write_text(run_cache_dir / "codex_error.txt", f"{iso_now()}\n{exc}\n")
        return None


def write_codex_outputs(
    codex_result: dict[str, Any] | None,
    run_id: str,
    fallback_recommendation: str,
    fallback_action_plan: str,
) -> tuple[str, str, Path | None, Path]:
    action_plan_path = RECOMMENDATIONS_DIR / f"recommendation_plan_{run_id}.md"
    if not codex_result:
        atomic_write_text(
            COMPRESSED_CONTEXT_PATH,
            deterministic_compressed_context(load_all_summaries()),
        )
        atomic_write_text(action_plan_path, fallback_action_plan)
        atomic_write_text(ACTION_PLAN_PATH, fallback_action_plan)
        atomic_write_text(LATEST_ACTION_PLAN_PATH, fallback_action_plan)
        return fallback_recommendation, fallback_action_plan, None, action_plan_path

    codex_path = CODEX_DIR / f"codex_synthesis_{run_id}.md"
    discoveries = codex_result.get("discoveries") or []
    open_questions = codex_result.get("open_questions") or []
    safety_flags = codex_result.get("safety_flags") or []
    codex_md = textwrap.dedent(
        f"""\
        # Codex RA Synthesis {run_id}

        ## Mission Restatement
        {codex_result.get('mission_restatement', MISSION_STATEMENT)}

        ## Discoveries
        {list_to_markdown(discoveries)}

        ## Safety Flags
        {list_to_markdown(safety_flags)}

        ## Open Questions
        {list_to_markdown(open_questions)}

        ## Compressed Context
        {codex_result.get('compressed_context', '')}
        """
    ).strip() + "\n"
    atomic_write_text(codex_path, codex_md)
    atomic_write_text(LATEST_CODEX_SYNTHESIS_PATH, codex_md)

    compressed_context = str(codex_result.get("compressed_context") or "").strip()
    if compressed_context:
        context_header = f"# RA Research Compressed Context\n\nUpdated: {local_now().isoformat()}\n\n"
        atomic_write_text(COMPRESSED_CONTEXT_PATH, context_header + compressed_context + "\n")
    else:
        atomic_write_text(COMPRESSED_CONTEXT_PATH, deterministic_compressed_context(load_all_summaries()))

    append_discoveries(run_id, discoveries, safety_flags, open_questions)

    scheme = str(codex_result.get("recommendation_scheme_markdown") or "").strip()
    if len(scheme) < 800:
        scheme = fallback_recommendation
    else:
        scheme = scheme + "\n"

    action_plan = str(codex_result.get("recommendation_plan_markdown") or "").strip()
    if len(action_plan) < 800:
        action_plan = fallback_action_plan
    else:
        action_plan = action_plan + "\n"
    atomic_write_text(action_plan_path, action_plan)
    atomic_write_text(ACTION_PLAN_PATH, action_plan)
    atomic_write_text(LATEST_ACTION_PLAN_PATH, action_plan)
    return scheme, action_plan, codex_path, action_plan_path


def deterministic_compressed_context(summaries: list[dict[str, Any]]) -> str:
    lines = [
        "# RA Research Compressed Context",
        "",
        f"Updated: {local_now().isoformat()}",
        "",
        f"Mission: {MISSION_STATEMENT}",
        "",
        "## Evidence Learned So Far",
    ]
    for summary in summaries[:40]:
        lines.append(
            f"- `{summary.get('source_id', '')}` {summary.get('title', '')}: "
            f"{clean_text(str(summary.get('remission_relevance', '')))[:350]} "
            f"(scope: {summary.get('evidence_scope', '')}; artifact: {summary.get('artifact_dir', '')})"
        )
    lines.extend(
        [
            "",
            "## Standing Safety Boundary",
            "- This is research support, not medical advice.",
            "- Medication, supplement, steroid, biologic, or JAK inhibitor changes require Kathia's rheumatologist.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def deterministic_action_plan(summaries: list[dict[str, Any]]) -> str:
    now = local_now().strftime("%Y-%m-%d %H:%M %Z")
    evidence_rows = []
    for summary in summaries[:40]:
        evidence_rows.append(
            "| {source} | {type} | {scope} | {implication} |".format(
                source=f"`{summary.get('source_id', '')}` {clean_text(summary.get('title', ''))[:90]}".replace("|", "\\|"),
                type=clean_text(summary.get("study_type", ""))[:40].replace("|", "\\|"),
                scope=clean_text(summary.get("evidence_scope", ""))[:40].replace("|", "\\|"),
                implication=clean_text(str(summary.get("remission_relevance", "")))[:180].replace("|", "\\|"),
            )
        )
    if not evidence_rows:
        evidence_rows.append("| No sources processed yet | | | |")

    header = textwrap.dedent(
        f"""\
        # RA Recommendation Plan

        Last updated: {now}

        ## Executive Summary

        Current evidence base is still small. The best-supported strategy so far
        is rheumatologist-led treat-to-target care with validated disease-activity
        monitoring and shared decisions. This plan is a research/action dossier
        for Chieh and Kathia to discuss with her clinician.

        ## At-Home Actions Now

        1. **Build a symptom and treatment log.** Track morning stiffness, pain,
           fatigue, function, flares, side effects, infections, missed doses, and
           what improves or worsens symptoms.
        2. **Prepare a one-page rheumatology visit brief.** Bring current symptoms,
           medication list, side effects, flare history, and top questions.
        3. **Use adjunct habits as symptom support.** Food, sleep, movement, stress,
           oral health, and trigger tracking can be started carefully, but they do
           not replace disease-control treatment.

        ## Tracking Steps

        - Weekly: symptoms, morning stiffness, fatigue, function, flares, side
          effects, missed doses, diet/sleep/activity notes.
        - At visits: clinician disease activity score, labs, medication plan,
          safety monitoring, target date for reassessment.

        ## Tests To Discuss

        1. **Define the target and score.** Ask which validated score is being used
           to judge remission or low disease activity: CDAI, SDAI, DAS28, or
           ACR/EULAR Boolean remission criteria.
        2. **Make medication strategy explicit with the rheumatologist.** If not
           at target, ask what evidence-supported escalation or adjustment is
           appropriate for Kathia's current regimen and risk profile.

        - Disease activity score used by the rheumatologist.
        - ESR/CRP trends.
        - Tender/swollen joint count.
        - RF/anti-CCP status if not already known.
        - Medication-specific safety labs, especially for DMARDs.
        - Imaging such as ultrasound/MRI only if the rheumatologist thinks it
          would clarify inflammatory activity versus residual pain.

        ## Food/Diet Options

        - Treat diet as an adjunct, not a replacement for disease control.
        - Research priority: Mediterranean/anti-inflammatory dietary patterns,
          omega-3/fish intake, weight/metabolic health, alcohol interactions with
          medication safety, and trigger tracking.
        - No supplement should be added without medication-interaction review.

        ## Lifestyle Changes

        - Low-impact aerobic activity and strength/mobility work as tolerated.
        - Sleep regularity and fatigue tracking.
        - Stress reduction as symptom-support, not as a standalone RA treatment.
        - Smoking avoidance and oral/periodontal health review.

        ## Medical Strategy Questions

        - What is Kathia's current target and timeline for reassessment?
        - If she is not at target, what is the next clinician-supervised step?
        - Are steroids being used, and what is the steroid-sparing plan?
        - What safety monitoring is required for her exact medications?

        ## Emerging Technology / Neuromodulation

        - Research priority: vagus-nerve stimulation, auricular stimulation,
          bioelectronic medicine, wearables, and digital symptom tracking.
        - Treat as experimental/clinician-discussion until enough high-quality RA
          evidence is cached.

        ## What Not To Do Without Clinician

        - Do not stop/start/change DMARDs, biologics, JAK inhibitors, steroids,
          NSAIDs, or supplements from this dossier alone.

        ## Evidence Matrix

        | Source | Type | Scope | Implication |
        |---|---|---|---|
        """
    ).strip()

    footer = textwrap.dedent(
        """\
        ## What Would Change This Plan

        - Evidence that Kathia is already in objective remission but remains
          symptomatic would shift focus toward residual pain/fatigue mechanisms.
        - Evidence of active inflammation despite treatment would shift focus
          toward clinician-supervised escalation or adjustment.
        - Strong RCT/guideline evidence for a diet, lifestyle intervention, or
          technology would move it from research priority to clinician-discussion
          recommendation.
        """
    ).strip() + "\n"
    return header + "\n" + "\n".join(evidence_rows) + "\n\n" + footer


def list_to_markdown(values: Any) -> str:
    if isinstance(values, list) and values:
        return "\n".join(f"- {clean_text(str(v))}" for v in values if str(v).strip())
    if values:
        return f"- {clean_text(str(values))}"
    return "- None captured."


def append_discoveries(run_id: str, discoveries: Any, safety_flags: Any, open_questions: Any) -> None:
    block = (
        f"\n## Run {run_id} — {local_now().strftime('%Y-%m-%d %H:%M %Z')}\n\n"
        f"Mission: {MISSION_STATEMENT}\n\n"
        f"### Discoveries\n{list_to_markdown(discoveries)}\n\n"
        f"### Safety Flags\n{list_to_markdown(safety_flags)}\n\n"
        f"### Open Questions\n{list_to_markdown(open_questions)}\n"
    )
    if not DISCOVERIES_PATH.exists():
        atomic_write_text(DISCOVERIES_PATH, "# RA Research Discoveries\n")
    with DISCOVERIES_PATH.open("a", encoding="utf-8") as f:
        f.write(block)


def deterministic_recommendation_scheme(summaries: list[dict[str, Any]]) -> str:
    now = local_now().strftime("%Y-%m-%d %H:%M %Z")
    evidence_rows = []
    for summary in summaries[:30]:
        evidence_rows.append(
            "| {title} | {scope} | {relevance} | {path} |".format(
                title=clean_text(summary.get("title", ""))[:110].replace("|", "\\|"),
                scope=clean_text(summary.get("evidence_scope", "")),
                relevance=clean_text(summary.get("remission_relevance", ""))[:180].replace("|", "\\|"),
                path=summary.get("artifact_dir", ""),
            )
        )
    evidence_rows = evidence_rows or ["| No sources processed yet | | | |"]
    header = textwrap.dedent(
        f"""\
        # RA Remission / Asymptomatic-State Research Scheme

        Last updated: {now}

        ## Status

        This loop remains active until Chieh explicitly stops it or Kathia is
        confirmed asymptomatic/in sustained remission. The script cannot verify
        Kathia's symptoms directly, so this document treats status as **ongoing**.

        ## Safety Boundary

        This is a research dossier, not medical advice. Medication starts,
        stops, dose changes, biologic/JAK inhibitor choices, steroid use, and
        supplement decisions must go through Kathia's rheumatologist.

        ## Current Working Model

        1. Use treat-to-target care with the rheumatologist: define remission or
           low disease activity as the target, measure disease activity regularly,
           and adjust therapy if the target is not met.
        2. Separate "feels asymptomatic" from validated remission. Ask for the
           specific measure being used: CDAI, SDAI, DAS28, or ACR/EULAR Boolean
           remission criteria.
        3. Keep the medication conversation clinician-led. The research loop
           can prepare questions and evidence summaries, but it should not
           recommend unsupervised DMARD, biologic, JAK inhibitor, or steroid changes.
        4. Track modifiable adjuncts that plausibly affect inflammation or
           symptoms: exercise/strength, sleep, stress, smoking exposure, oral
           health, weight/metabolic health, diet quality, and carefully reviewed
           supplements only when safe with her medications.
        5. Track patient-important symptoms separately: morning stiffness,
           fatigue, pain, function, swollen/tender joints, flares, side effects,
           infections, and work/home impact.

        ## Minimum Data To Personalize This

        - Current RA medications, doses, start dates, missed doses, and side effects.
        - Recent ESR/CRP and the rheumatologist's disease activity score.
        - Tender/swollen joint count if available.
        - Morning stiffness duration, fatigue, pain, sleep, and flare log.
        - Comorbidities, pregnancy plans, infection history, vaccines, and supplement list.

        ## Evidence Register

        | Source | Scope | Remission relevance | Saved artifact |
        |---|---|---|---|
        """
    ).strip()

    footer = textwrap.dedent(
        """\
        ## Next Research Questions

        - Which treat-to-target escalation patterns have the best remission odds
          for patients matching Kathia's current therapy history?
        - Which lifestyle adjuncts have randomized-trial evidence for clinically
          meaningful disease activity, pain, or fatigue improvement?
        - Which predictors distinguish inflammatory activity from residual pain,
          central sensitization, osteoarthritis, or fatigue when formal remission
          criteria are partly met?
        - What monitoring schedule best catches loss of remission early while
          avoiding overtreatment?
        """
    ).strip() + "\n"
    return header + "\n" + "\n".join(evidence_rows) + "\n\n" + footer


def build_recommendation_scheme(summaries: list[dict[str, Any]], new_summaries: list[dict[str, Any]]) -> str:
    system_prompt = (
        "You are Jane's medical literature synthesis assistant for rheumatoid arthritis research. "
        "Your output is a cautious research plan for Chieh to discuss with Kathia and her rheumatologist. "
        "Never instruct medication changes. Distinguish strong guideline evidence from weak adjunct evidence. "
        "Be concrete about what to track, what to ask the clinician, and what evidence has been saved."
    )
    user_prompt = (
        "Regenerate the living RA remission/asymptomatic-state recommendation scheme as Markdown. "
        "Required sections: Status, Safety Boundary, Current Working Model, Recommendation Scheme, "
        "Tracking Checklist, Clinician Questions, Evidence Register, New Evidence This Run, "
        "Next Research Questions. The loop status is ongoing until Chieh reports Kathia is asymptomatic "
        "or stops the cron. Use only the evidence summaries below.\n\n"
        + json.dumps(
            {
                "generated_at": local_now().isoformat(),
                "mission": MISSION_STATEMENT,
                "new_source_ids_this_run": [s.get("source_id") for s in new_summaries],
                "summaries": compact_summary_payload(summaries, limit=80),
            },
            ensure_ascii=False,
        )
    )
    generated = ollama_chat_text(system_prompt, user_prompt)
    if not generated or len(generated) < 1000:
        return deterministic_recommendation_scheme(summaries)
    if "medical advice" not in generated.lower() and "rheumatologist" not in generated.lower():
        generated = (
            "Safety note: this is a research dossier, not medical advice. Medication and supplement "
            "changes must be discussed with Kathia's rheumatologist.\n\n"
            + generated
        )
    return generated.strip() + "\n"


def write_run_report(new_summaries: list[dict[str, Any]], recommendation_text: str, action_plan_text: str) -> Path:
    ts = local_now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"ra_research_run_{ts}.md"
    lines = [
        f"# RA Research Run {local_now().strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        f"New sources processed: {len(new_summaries)}",
        f"Recommendation file: `{RECOMMENDATION_PATH}`",
        f"Action plan: `{ACTION_PLAN_PATH}`",
        f"Compressed context: `{COMPRESSED_CONTEXT_PATH}`",
        f"Latest Codex synthesis: `{LATEST_CODEX_SYNTHESIS_PATH}`",
        f"Discoveries log: `{DISCOVERIES_PATH}`",
        "",
        "## New Source Summaries",
    ]
    if not new_summaries:
        lines.append("- No new sources processed this run; cached recommendation scheme was refreshed.")
    for summary in new_summaries:
        lines.extend(
            [
                f"### {summary.get('title', 'Untitled')}",
                f"- Source ID: `{summary.get('source_id', '')}`",
                f"- URL: {summary.get('url', '')}",
                f"- Scope: {summary.get('evidence_scope', '')}",
                f"- Saved artifact: `{summary.get('artifact_dir', '')}`",
                f"- Remission relevance: {summary.get('remission_relevance', '')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Current Action Plan Snapshot",
            "",
            action_plan_text[:12000],
            "",
            "## Current Scheme Snapshot",
            "",
            recommendation_text[:8000],
        ]
    )
    atomic_write_text(report_path, "\n".join(lines).strip() + "\n")
    return report_path


def should_send_report(state: dict[str, Any], force: bool) -> bool:
    if force:
        return True
    run_count = int(state.get("run_count", 0))
    if not state.get("initial_report_sent"):
        return run_count >= INITIAL_REPORT_AFTER_RUNS
    last = parse_iso(state.get("last_report_sent_at"))
    if last is None:
        return run_count >= INITIAL_REPORT_AFTER_RUNS
    return (utc_now() - last) >= dt.timedelta(hours=REPORT_INTERVAL_HOURS)


def send_email_report(
    state: dict[str, Any],
    report_path: Path,
    recommendation_text: str,
    action_plan_text: str,
    force: bool,
) -> bool:
    if not should_send_report(state, force):
        return False

    try:
        from agent_skills.email_tools import send_email

        processed_count = len(state.get("processed_sources", {}))
        subject = f"RA research update: remission/asymptomatic evidence ({local_now().strftime('%Y-%m-%d')})"
        body = textwrap.dedent(
            f"""\
            Chieh,

            The RA remission research cron is still running. It has processed and cached {processed_count} sources so far.

            Latest report:
            {report_path}

            Latest living recommendation scheme:
            {RECOMMENDATION_PATH}

            Latest action plan:
            {ACTION_PLAN_PATH}

            Action plan snapshot:

            {action_plan_text[:12000]}

            Research scheme snapshot:

            {recommendation_text[:6000]}

            Safety boundary: this is a research dossier for discussion with Kathia and her rheumatologist, not medical advice. Medication, supplement, or treatment changes should not be made from this report alone.
            """
        ).strip()
        send_email(
            to=RECIPIENT_EMAIL,
            subject=subject,
            body=body,
            from_email=REPORT_FROM_EMAIL,
        )
        state["last_report_sent_at"] = iso_now()
        state["last_report_source_count"] = processed_count
        state["initial_report_sent"] = True
        state["last_report_error"] = None
        LOGGER.info("Sent RA research report to %s from %s", RECIPIENT_EMAIL, REPORT_FROM_EMAIL)
        return True
    except Exception as exc:
        state["last_report_error"] = f"{iso_now()}: {exc}"
        LOGGER.warning("Email report failed: %s", exc)
        return False


def log_short_term(new_count: int, processed_total: int) -> None:
    fact = (
        f"RA research cron ran at {iso_now()}. New sources processed: {new_count}. "
        f"Total cached sources: {processed_total}. Recommendation scheme: {RECOMMENDATION_PATH}"
    )
    try:
        subprocess.run(
            [
                ADK_VENV_PYTHON,
                str(Path(__file__).resolve().parents[0] / "add_forgettable_memory.py"),
                fact,
                "--topic",
                "cron_logs",
                "--subtopic",
                "ra_research",
                "--author",
                "jane",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        pass


def run_once(max_new_sources: int, *, no_email: bool, force_report: bool) -> dict[str, Any]:
    ensure_dirs()
    state = load_state()
    state["status"] = "active_until_chieh_stops_or_kathia_confirmed_asymptomatic"
    state["mission"] = MISSION_STATEMENT
    state["run_count"] = int(state.get("run_count", 0)) + 1
    state["last_run_started_at"] = iso_now()
    run_id = local_now().strftime("%Y%m%d_%H%M%S")
    run_cache_dir = CACHE_DIR / "runs" / run_id
    run_cache_dir.mkdir(parents=True, exist_ok=True)

    candidates = collect_candidate_sources(state, max_new_sources, run_cache_dir)
    new_summaries = process_candidates(candidates, state, run_cache_dir)
    upgraded_summaries = retry_pending_llm_reviews(state)
    if upgraded_summaries:
        new_summaries.extend(upgraded_summaries)
    summaries = load_all_summaries()
    fallback_recommendation = build_recommendation_scheme(summaries, new_summaries)
    fallback_action_plan = deterministic_action_plan(summaries)
    codex_result = run_codex_synthesis(summaries, new_summaries, run_cache_dir)
    recommendation_text, action_plan_text, codex_path, action_plan_path = write_codex_outputs(
        codex_result,
        run_id,
        fallback_recommendation,
        fallback_action_plan,
    )
    atomic_write_text(RECOMMENDATION_PATH, recommendation_text)
    report_path = write_run_report(new_summaries, recommendation_text, action_plan_text)

    state["last_run_finished_at"] = iso_now()
    state["last_new_source_count"] = len(new_summaries)
    state["last_report_path"] = str(report_path)
    state["recommendation_path"] = str(RECOMMENDATION_PATH)
    state["action_plan_path"] = str(ACTION_PLAN_PATH)
    state["last_action_plan_path"] = str(action_plan_path)
    state["compressed_context_path"] = str(COMPRESSED_CONTEXT_PATH)
    state["discoveries_path"] = str(DISCOVERIES_PATH)
    state["last_run_cache_dir"] = str(run_cache_dir)
    state["last_codex_synthesis_path"] = str(codex_path) if codex_path else None
    state["smart_provider"] = SMART_PROVIDER
    state["smart_model_label"] = SMART_MODEL_LABEL

    email_sent = False
    if not no_email:
        email_sent = send_email_report(state, report_path, recommendation_text, action_plan_text, force_report)
    state["last_email_sent_this_run"] = email_sent
    save_state(state)
    log_short_term(len(new_summaries), len(state.get("processed_sources", {})))

    return {
        "new_sources": len(new_summaries),
        "total_sources": len(state.get("processed_sources", {})),
        "report_path": str(report_path),
        "recommendation_path": str(RECOMMENDATION_PATH),
        "action_plan_path": str(ACTION_PLAN_PATH),
        "compressed_context_path": str(COMPRESSED_CONTEXT_PATH),
        "codex_synthesis_path": str(codex_path) if codex_path else "",
        "email_sent": email_sent,
        "run_count": state["run_count"],
        "initial_report_sent": bool(state.get("initial_report_sent")),
    }


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [ra_research] %(levelname)s: %(message)s",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="RA remission research cron")
    parser.add_argument("--max-new-sources", type=int, default=int(os.environ.get("RA_RESEARCH_MAX_NEW_SOURCES", "10")))
    parser.add_argument("--no-email", action="store_true", help="Do not send the 3-day email report")
    parser.add_argument("--send-report-now", action="store_true", help="Send report even if 72h have not elapsed")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if load_dotenv:
        load_dotenv(ENV_FILE_PATH)
    configure_logging(args.verbose)

    result = run_once(
        max_new_sources=max(1, args.max_new_sources),
        no_email=args.no_email,
        force_report=args.send_report_now,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
