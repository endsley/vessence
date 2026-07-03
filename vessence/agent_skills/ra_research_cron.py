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
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import ADK_VENV_PYTHON, ENV_FILE_PATH, FRONTIER_MODEL, VESSENCE_DATA_HOME, VAULT_DIR
from jane_web.jane_v2.models import LOCAL_LLM, LOCAL_LLM_NUM_CTX
from agent_skills.ra_research_artifacts import (
    html_to_text,
    is_jats_article_xml,
    pmc_xml_to_text,
    pubmed_abstract_text,
    raw_source_suffix,
    slugify,
    source_folder as _source_folder,
    web_source_folder,
    web_source_record,
)
from agent_skills.ra_research_delivery import (
    build_app_report_payload,
    build_email_report_body,
    email_report_subject,
    mark_email_report_sent,
    mark_app_report_sent,
    normalize_report_channel,
    should_send_report as _should_send_report,
)
from agent_skills.ra_research_discoveries import discovery_block as _discovery_block
from agent_skills.ra_research_candidates import (
    collect_seed_candidates,
    pubmed_search_finding,
    select_pubmed_candidates,
)
from agent_skills.ra_research_codex_prompt import (
    CODEX_AUTOMATION_SYSTEM_PROMPT as _CODEX_AUTOMATION_SYSTEM_PROMPT,
    codex_synthesis_payload as _codex_synthesis_payload,
    codex_synthesis_prompt as _codex_synthesis_prompt,
    non_json_codex_result as _non_json_codex_result,
)
from agent_skills.ra_research_codex_outputs import (
    codex_synthesis_markdown as _codex_synthesis_markdown,
    compressed_context_document as _compressed_context_document,
    selected_codex_markdown as _selected_codex_markdown,
)
from agent_skills.ra_research_html import build_report_html, markdown_to_report_html, report_id_from_path
from agent_skills.ra_research_ollama import (
    normalize_ollama_base_url as _normalize_ollama_base_url,
    ollama_chat_payload as _ollama_chat_payload,
)
from agent_skills.ra_research_ncbi import (
    ncbi_params as _ncbi_params,
    pubmed_fetch_cache_text,
    pubmed_fetch_params,
    pubmed_ids_from_search_response,
    pubmed_search_cache_payload,
    pubmed_search_params,
)
from agent_skills.ra_research_pubmed import parse_pubmed_article
from agent_skills.ra_research_report_markdown import (
    build_deterministic_action_plan as _build_deterministic_action_plan,
    build_deterministic_compressed_context as _build_deterministic_compressed_context,
    build_deterministic_recommendation_scheme as _build_deterministic_recommendation_scheme,
    build_run_report_markdown,
    build_useful_report_markdown as _build_useful_report_markdown,
    list_to_markdown,
)
from agent_skills.ra_research_recommendation_prompt import (
    RECOMMENDATION_SYSTEM_PROMPT as _RECOMMENDATION_SYSTEM_PROMPT,
    ensure_safety_note as _ensure_safety_note,
    recommendation_user_prompt as _recommendation_user_prompt,
)
from agent_skills.ra_research_summary_cache import (
    build_processed_source_entry,
    finalize_summary_for_cache,
    load_cached_summary,
    readable_text_from_artifact,
    read_json_dict,
    summary_to_markdown,
)
from agent_skills.ra_research_summary_prompt import (
    SUMMARY_SYSTEM_PROMPT as _SUMMARY_SYSTEM_PROMPT,
    summary_user_prompt as _summary_user_prompt,
)
from agent_skills.ra_research_source_utils import (
    citation_for,
    fallback_summary_payload as _fallback_summary_payload,
    source_cache_key,
)
from agent_skills.ra_research_state import (
    default_research_state as _default_research_state,
    record_delivery_result as _record_delivery_result,
    record_run_artifacts as _record_run_artifacts,
    record_run_started as _record_run_started,
    run_result_payload as _run_result_payload,
)
from agent_skills.ra_research_text import (
    dedupe_summaries,
    parse_json_from_text,
)

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
HTML_REPORTS_DIR = REPORTS_DIR / "html"
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
REPORT_CHANNEL = os.environ.get("RA_RESEARCH_REPORT_CHANNEL", "app").strip().lower()
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


def ensure_dirs() -> None:
    for path in (
        DATA_ROOT,
        VAULT_ROOT,
        PAPERS_DIR,
        SUMMARY_DIR,
        REPORTS_DIR,
        HTML_REPORTS_DIR,
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
        return _default_research_state(created_at=iso_now(), mission_statement=MISSION_STATEMENT)
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        LOGGER.exception("State file was unreadable; starting with empty state")
        return _default_research_state(created_at=iso_now(), mission_statement=MISSION_STATEMENT)


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
    return _ncbi_params(
        extra,
        tool=NCBI_TOOL,
        email=NCBI_EMAIL,
        api_key=os.environ.get("NCBI_API_KEY", ""),
    )


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
        params=pubmed_search_params(
            query,
            retmax=retmax,
            retstart=retstart,
            sort=sort,
            tool=NCBI_TOOL,
            email=NCBI_EMAIL,
            api_key=os.environ.get("NCBI_API_KEY", ""),
        ),
        timeout=30,
    )
    data = response.json()
    if cache_path:
        atomic_write_json(
            cache_path,
            pubmed_search_cache_payload(
                fetched_at=iso_now(),
                url=response.url,
                query=query,
                retmax=retmax,
                retstart=retstart,
                sort=sort,
                response=data,
            ),
        )
    return pubmed_ids_from_search_response(data)


def pubmed_fetch(pmids: list[str], *, cache_path: Path | None = None) -> list[dict[str, Any]]:
    if not pmids:
        return []
    response = http_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        params=pubmed_fetch_params(
            pmids,
            tool=NCBI_TOOL,
            email=NCBI_EMAIL,
            api_key=os.environ.get("NCBI_API_KEY", ""),
        ),
        timeout=45,
    )
    if cache_path:
        atomic_write_text(
            cache_path,
            pubmed_fetch_cache_text(
                fetched_at=iso_now(),
                url=response.url,
                pmids=pmids,
                response_text=response.text,
            ),
        )
    root = ET.fromstring(response.text)
    records = []
    for article in root.findall(".//PubmedArticle"):
        parsed = parse_pubmed_article(article)
        if parsed:
            records.append(parsed)
    return records


def source_folder(record: dict[str, Any]) -> Path:
    return _source_folder(PAPERS_DIR, record)


def save_pubmed_artifacts(record: dict[str, Any]) -> tuple[Path, str, str]:
    """Save metadata, abstract, and open-access full text/PDF when available."""
    folder = source_folder(record)
    folder.mkdir(parents=True, exist_ok=True)
    atomic_write_json(folder / "metadata.json", record)

    abstract_text = pubmed_abstract_text(record)
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
    folder = web_source_folder(PAPERS_DIR, source)
    folder.mkdir(parents=True, exist_ok=True)
    record = web_source_record(source, fetched_at=iso_now())
    response = http_get(source["url"], timeout=45)
    suffix = raw_source_suffix(response.headers.get("content-type", ""))
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
    base = _normalize_ollama_base_url(
        os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    )
    model = os.environ.get("RA_RESEARCH_MODEL", LOCAL_LLM)
    try:
        response = requests.post(
            f"{base}/api/chat",
            json=_ollama_chat_payload(model, system_prompt, user_prompt, num_ctx=LOCAL_LLM_NUM_CTX),
            timeout=timeout,
        )
        response.raise_for_status()
        text = response.json().get("message", {}).get("content", "")
        return parse_json_from_text(text)
    except Exception as exc:
        LOGGER.warning("Local LLM JSON call failed: %s", exc)
        return None


def ollama_chat_text(system_prompt: str, user_prompt: str, *, timeout: int = 180) -> str | None:
    base = _normalize_ollama_base_url(
        os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    )
    model = os.environ.get("RA_RESEARCH_MODEL", LOCAL_LLM)
    try:
        response = requests.post(
            f"{base}/api/chat",
            json=_ollama_chat_payload(model, system_prompt, user_prompt, num_ctx=LOCAL_LLM_NUM_CTX),
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()
    except Exception as exc:
        LOGGER.warning("Local LLM text call failed: %s", exc)
        return None


def fallback_summary(record: dict[str, Any], evidence_scope: str, artifact_dir: Path, text: str) -> dict[str, Any]:
    return _fallback_summary_payload(
        record,
        evidence_scope,
        artifact_dir,
        text,
        summarized_at=iso_now(),
    )


def summarize_source(record: dict[str, Any], artifact_dir: Path, readable_text: str, evidence_scope: str) -> dict[str, Any]:
    summary_path = SUMMARY_DIR / f"{record['source_id']}.json"
    existing_summary, reusable_summary = load_cached_summary(summary_path)
    if reusable_summary and existing_summary is not None:
        return existing_summary

    system_prompt = _SUMMARY_SYSTEM_PROMPT
    user_prompt = _summary_user_prompt(
        MISSION_STATEMENT,
        record,
        evidence_scope,
        citation_for(record),
        readable_text,
    )
    summary = ollama_chat_json(system_prompt, user_prompt)
    if summary is None and existing_summary is not None:
        return existing_summary
    if summary is None:
        summary = fallback_summary(record, evidence_scope, artifact_dir, readable_text)
    else:
        summary["needs_llm_review"] = False

    summary = finalize_summary_for_cache(
        summary,
        record,
        artifact_dir=artifact_dir,
        evidence_scope=evidence_scope,
        cache_key=source_cache_key(record),
        summarized_at=iso_now(),
        citation=citation_for(record),
    )
    atomic_write_json(summary_path, summary)
    atomic_write_text(SUMMARY_DIR / f"{record['source_id']}.md", summary_to_markdown(summary))
    return summary


def collect_candidate_sources(state: dict[str, Any], max_new: int, run_cache_dir: Path) -> list[dict[str, Any]]:
    processed = state.setdefault("processed_sources", {})
    candidates, all_findings, seed_limit_reached = collect_seed_candidates(SEED_SOURCES, processed, max_new)
    if seed_limit_reached:
        atomic_write_json(run_cache_dir / "all_candidate_findings.json", all_findings)
        atomic_write_json(run_cache_dir / "selected_candidates.json", candidates)
        return candidates

    query_offsets = state.setdefault("query_offsets", {})
    for profile in PUBMED_SEARCHES:
        if len(candidates) >= max_new:
            break
        retmax = int(profile.get("retmax", 8))
        retstart = 0 if profile["mode"] == "latest" else int(query_offsets.get(profile["name"], 0))
        sort = profile.get("sort", "pub date")
        try:
            pmids = pubmed_search(
                profile["query"],
                retmax=retmax,
                retstart=retstart,
                sort=sort,
                cache_path=run_cache_dir / f"pubmed_search_{slugify(profile['name'])}_{retstart}.json",
            )
            time.sleep(0.35)
        except Exception as exc:
            LOGGER.warning("PubMed search failed for %s: %s", profile["name"], exc)
            continue
        all_findings.append(pubmed_search_finding(profile, retstart=retstart, retmax=retmax, sort=sort, pmids=pmids))
        selected, consumed_from_page = select_pubmed_candidates(
            pmids,
            processed,
            profile_name=profile["name"],
            max_candidates=max_new - len(candidates),
        )
        candidates.extend(selected)
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
                metadata_path = artifact_dir / "metadata.json"
                record = read_json_dict(metadata_path)
                if record is None:
                    raise ValueError(f"metadata JSON was unreadable: {metadata_path}")
            else:
                record = pubmed_records.get(candidate["pmid"])
                if not record:
                    LOGGER.warning("PMID %s was not returned by efetch", candidate["pmid"])
                    continue
                artifact_dir, readable_text, evidence_scope = save_pubmed_artifacts(record)

            summary = summarize_source(record, artifact_dir, readable_text, evidence_scope)
            processed[source_id] = build_processed_source_entry(
                record,
                source_id=source_id,
                artifact_dir=artifact_dir,
                summary_dir=SUMMARY_DIR,
                evidence_scope=evidence_scope,
                cache_key=source_cache_key(record),
                processed_at=iso_now(),
            )
            processed_summaries.append(summary)
            LOGGER.info("Processed %s: %s", source_id, record.get("title", "")[:120])
        except Exception as exc:
            LOGGER.exception("Failed to process %s: %s", source_id, exc)
        time.sleep(0.35)

    return processed_summaries


def retry_pending_llm_reviews(state: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """Re-upgrade degraded fallback summaries once the local LLM is healthy."""
    upgraded: list[dict[str, Any]] = []
    processed = state.get("processed_sources", {})
    for summary_path in sorted(SUMMARY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
        if len(upgraded) >= limit:
            break
        existing = read_json_dict(summary_path)
        if existing is None:
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
        record = read_json_dict(metadata_path)
        if record is None:
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
        summary = read_json_dict(path)
        if summary is not None:
            summaries.append(summary)
        if len(summaries) >= limit:
            break
    return summaries


def previous_context_text() -> str:
    if COMPRESSED_CONTEXT_PATH.exists():
        try:
            return COMPRESSED_CONTEXT_PATH.read_text(encoding="utf-8")[:12000]
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
    prompt_payload = _codex_synthesis_payload(
        mission_statement=MISSION_STATEMENT,
        smart_model_label=SMART_MODEL_LABEL,
        smart_provider=SMART_PROVIDER,
        previous_compressed_context=previous_context_text(),
        new_summaries=new_summaries,
        summaries=summaries,
    )
    prompt = _codex_synthesis_prompt(prompt_payload)
    atomic_write_json(run_cache_dir / "codex_prompt_payload.json", prompt_payload)

    try:
        from jane.automation_runner import run_automation_prompt

        response = run_automation_prompt(
            prompt,
            system_prompt=_CODEX_AUTOMATION_SYSTEM_PROMPT,
            timeout_seconds=SMART_TIMEOUT_SECONDS,
            provider=SMART_PROVIDER,
            workdir=str(Path(__file__).resolve().parents[1]),
        )
        atomic_write_text(run_cache_dir / "codex_raw_response.txt", response)
        parsed = parse_json_from_text(response)
        if parsed:
            return parsed
        LOGGER.warning("Codex synthesis returned non-JSON output")
        return _non_json_codex_result(MISSION_STATEMENT, response)
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
    codex_md = _codex_synthesis_markdown(run_id, codex_result, MISSION_STATEMENT)
    atomic_write_text(codex_path, codex_md)
    atomic_write_text(LATEST_CODEX_SYNTHESIS_PATH, codex_md)

    compressed_context = str(codex_result.get("compressed_context") or "").strip()
    if compressed_context:
        atomic_write_text(
            COMPRESSED_CONTEXT_PATH,
            _compressed_context_document(compressed_context, local_now().isoformat()),
        )
    else:
        atomic_write_text(COMPRESSED_CONTEXT_PATH, deterministic_compressed_context(load_all_summaries()))

    append_discoveries(run_id, discoveries, safety_flags, open_questions)

    scheme = _selected_codex_markdown(codex_result, "recommendation_scheme_markdown", fallback_recommendation)
    action_plan = _selected_codex_markdown(codex_result, "recommendation_plan_markdown", fallback_action_plan)
    atomic_write_text(action_plan_path, action_plan)
    atomic_write_text(ACTION_PLAN_PATH, action_plan)
    atomic_write_text(LATEST_ACTION_PLAN_PATH, action_plan)
    return scheme, action_plan, codex_path, action_plan_path


def deterministic_compressed_context(summaries: list[dict[str, Any]]) -> str:
    return _build_deterministic_compressed_context(
        summaries,
        updated_label=local_now().isoformat(),
        mission_statement=MISSION_STATEMENT,
    )


def deterministic_action_plan(summaries: list[dict[str, Any]]) -> str:
    return _build_deterministic_action_plan(
        summaries,
        updated_label=local_now().strftime("%Y-%m-%d %H:%M %Z"),
    )


def build_useful_report_markdown(
    new_summaries: list[dict[str, Any]],
    all_summaries: list[dict[str, Any]],
    codex_result: dict[str, Any] | None,
    source_count: int,
) -> str:
    return _build_useful_report_markdown(
        new_summaries,
        all_summaries,
        codex_result,
        source_count,
        recommendation_path=RECOMMENDATION_PATH,
        action_plan_path=ACTION_PLAN_PATH,
        compressed_context_path=COMPRESSED_CONTEXT_PATH,
        discoveries_path=DISCOVERIES_PATH,
    )


def write_html_report(report_path: Path, report_markdown: str, source_count: int, new_count: int) -> Path:
    report_id = report_id_from_path(report_path)
    html_path = HTML_REPORTS_DIR / f"{report_path.stem}.html"
    html_text = build_report_html(report_markdown, report_id, source_count, new_count)
    atomic_write_text(html_path, html_text)
    atomic_write_text(HTML_REPORTS_DIR / "latest.html", html_text)
    return html_path


def append_discoveries(run_id: str, discoveries: Any, safety_flags: Any, open_questions: Any) -> None:
    block = _discovery_block(
        run_id,
        local_now().strftime("%Y-%m-%d %H:%M %Z"),
        MISSION_STATEMENT,
        discoveries,
        safety_flags,
        open_questions,
    )
    if not DISCOVERIES_PATH.exists():
        atomic_write_text(DISCOVERIES_PATH, "# RA Research Discoveries\n")
    with DISCOVERIES_PATH.open("a", encoding="utf-8") as f:
        f.write(block)


def deterministic_recommendation_scheme(summaries: list[dict[str, Any]]) -> str:
    return _build_deterministic_recommendation_scheme(
        summaries,
        updated_label=local_now().strftime("%Y-%m-%d %H:%M %Z"),
    )


def build_recommendation_scheme(summaries: list[dict[str, Any]], new_summaries: list[dict[str, Any]]) -> str:
    system_prompt = _RECOMMENDATION_SYSTEM_PROMPT
    user_prompt = _recommendation_user_prompt(
        generated_at=local_now().isoformat(),
        mission_statement=MISSION_STATEMENT,
        new_summaries=new_summaries,
        summaries=summaries,
    )
    generated = ollama_chat_text(system_prompt, user_prompt)
    if not generated or len(generated) < 1000:
        return deterministic_recommendation_scheme(summaries)
    generated = _ensure_safety_note(generated)
    return generated.strip() + "\n"


def write_run_report(
    new_summaries: list[dict[str, Any]],
    all_summaries: list[dict[str, Any]],
    recommendation_text: str,
    action_plan_text: str,
    source_count: int,
    codex_result: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    ts = local_now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"ra_research_run_{ts}.md"
    report_markdown = build_run_report_markdown(
        new_summaries,
        all_summaries,
        recommendation_text,
        action_plan_text,
        source_count,
        codex_result,
        generated_label=local_now().strftime("%Y-%m-%d %H:%M %Z"),
        recommendation_path=RECOMMENDATION_PATH,
        action_plan_path=ACTION_PLAN_PATH,
        compressed_context_path=COMPRESSED_CONTEXT_PATH,
        latest_codex_synthesis_path=LATEST_CODEX_SYNTHESIS_PATH,
        discoveries_path=DISCOVERIES_PATH,
    )
    atomic_write_text(report_path, report_markdown)
    html_path = write_html_report(report_path, report_markdown, source_count, len(new_summaries))
    return report_path, html_path


def should_send_report(state: dict[str, Any], force: bool) -> bool:
    return _should_send_report(
        state,
        force,
        now=utc_now(),
        initial_report_after_runs=INITIAL_REPORT_AFTER_RUNS,
        report_interval_hours=REPORT_INTERVAL_HOURS,
        parse_iso_fn=parse_iso,
    )


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
        subject = email_report_subject(local_now().strftime("%Y-%m-%d"))
        body = build_email_report_body(
            processed_count=processed_count,
            report_path=report_path,
            recommendation_path=RECOMMENDATION_PATH,
            action_plan_path=ACTION_PLAN_PATH,
            action_plan_text=action_plan_text,
            recommendation_text=recommendation_text,
        )
        send_email(
            to=RECIPIENT_EMAIL,
            subject=subject,
            body=body,
            from_email=REPORT_FROM_EMAIL,
        )
        mark_email_report_sent(state, sent_at=iso_now(), processed_count=processed_count)
        LOGGER.info("Sent RA research report to %s from %s", RECIPIENT_EMAIL, REPORT_FROM_EMAIL)
        return True
    except Exception as exc:
        state["last_report_error"] = f"{iso_now()}: {exc}"
        LOGGER.warning("Email report failed: %s", exc)
        return False


def append_jane_announcement(payload: dict[str, Any]) -> None:
    ANNOUNCEMENTS_PATH = Path(VESSENCE_DATA_HOME) / "data" / "jane_announcements.jsonl"
    ANNOUNCEMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ANNOUNCEMENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def send_app_report_notification(
    state: dict[str, Any],
    report_path: Path,
    html_report_path: Path,
    new_count: int,
    force: bool,
) -> bool:
    if not should_send_report(state, force):
        return False

    processed_count = len(state.get("processed_sources", {}))
    report_id = report_id_from_path(report_path)
    created_at = iso_now()
    payload = build_app_report_payload(
        report_id=report_id,
        report_path=report_path,
        html_report_path=html_report_path,
        new_count=new_count,
        total_sources=processed_count,
        created_at=created_at,
    )
    append_jane_announcement(payload)
    mark_app_report_sent(
        state,
        created_at=created_at,
        total_sources=processed_count,
        html_report_path=html_report_path,
    )
    LOGGER.info("Published RA research app notification announcement %s", payload["id"])
    return True


def send_report_update(
    state: dict[str, Any],
    report_path: Path,
    html_report_path: Path,
    recommendation_text: str,
    action_plan_text: str,
    new_count: int,
    force: bool,
) -> bool:
    active_report_channel = normalize_report_channel(REPORT_CHANNEL)
    if active_report_channel == "email":
        state["last_report_channel"] = "email"
        return send_email_report(state, report_path, recommendation_text, action_plan_text, force)
    if active_report_channel == "disabled":
        state["last_report_channel"] = "disabled"
        return False
    return send_app_report_notification(state, report_path, html_report_path, new_count, force)


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
    _record_run_started(state, started_at=iso_now(), mission_statement=MISSION_STATEMENT)
    run_id = local_now().strftime("%Y%m%d_%H%M%S")
    run_cache_dir = CACHE_DIR / "runs" / run_id
    run_cache_dir.mkdir(parents=True, exist_ok=True)

    candidates = collect_candidate_sources(state, max_new_sources, run_cache_dir)
    new_summaries = process_candidates(candidates, state, run_cache_dir)
    upgraded_summaries = retry_pending_llm_reviews(state)
    if upgraded_summaries:
        new_summaries.extend(upgraded_summaries)
    new_summaries = dedupe_summaries(new_summaries)
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
    processed_total = len(state.get("processed_sources", {}))
    report_path, html_report_path = write_run_report(
        new_summaries,
        summaries,
        recommendation_text,
        action_plan_text,
        processed_total,
        codex_result,
    )

    _record_run_artifacts(
        state,
        finished_at=iso_now(),
        new_source_count=len(new_summaries),
        report_path=report_path,
        html_report_path=html_report_path,
        recommendation_path=RECOMMENDATION_PATH,
        action_plan_path=ACTION_PLAN_PATH,
        last_action_plan_path=action_plan_path,
        compressed_context_path=COMPRESSED_CONTEXT_PATH,
        discoveries_path=DISCOVERIES_PATH,
        run_cache_dir=run_cache_dir,
        codex_path=codex_path,
        smart_provider=SMART_PROVIDER,
        smart_model_label=SMART_MODEL_LABEL,
    )

    report_notification_sent = False
    if not no_email:
        report_notification_sent = send_report_update(
            state,
            report_path,
            html_report_path,
            recommendation_text,
            action_plan_text,
            len(new_summaries),
            force_report,
        )
    active_report_channel = normalize_report_channel(REPORT_CHANNEL)
    _record_delivery_result(
        state,
        report_notification_sent=report_notification_sent,
        report_channel=active_report_channel,
    )
    save_state(state)
    log_short_term(len(new_summaries), processed_total)

    return _run_result_payload(state)


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [ra_research] %(levelname)s: %(message)s",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="RA remission research cron")
    parser.add_argument("--max-new-sources", type=int, default=int(os.environ.get("RA_RESEARCH_MAX_NEW_SOURCES", "10")))
    parser.add_argument("--no-email", action="store_true", help="Do not deliver the scheduled report")
    parser.add_argument("--send-report-now", action="store_true", help="Deliver report even if the interval has not elapsed")
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
