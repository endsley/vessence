#!/usr/bin/env python3
import os
os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')

import chromadb
import uuid
import sys
import json
import logging
import datetime
import shutil
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jane.config import (
    get_chroma_client,
    ENV_FILE_PATH, VECTOR_DB_USER_MEMORIES, VECTOR_DB_SHORT_TERM,
    VECTOR_DB_LONG_TERM, VECTOR_DB_FILE_INDEX,
    CHROMA_COLLECTION_USER_MEMORIES, CHROMA_COLLECTION_SHORT_TERM,
    CHROMA_COLLECTION_LONG_TERM, CHROMA_COLLECTION_FILE_INDEX,
    FORGETTABLE_MAX_AGE_DAYS, JANITOR_REPORT, LOGS_DIR,
    JANITOR_LLM_MODEL, OPENAI_API_URL,
    FALLBACK_GEMINI_MODEL, FALLBACK_OPENAI_MODEL, VAULT_DIR,
    DYNAMIC_QUERY_MARKERS_PATH, FRONTIER_PROVIDER,
)
from memory.v1.janitor_expiry import (
    expired_ids_from_metadata,
    is_expired_value,
    old_ids_from_metadata,
)
from memory.v1.janitor_consolidation import (
    consolidated_memory_metadata,
    consolidation_prompt,
    consolidation_topic_candidates,
    group_consolidation_topics,
)
from memory.v1.janitor_code_verification import (
    code_memory_records_from_collection,
    code_memory_verification_sort_key,
    code_verification_report_markdown,
    code_verification_prompt,
    code_verification_result,
    frontier_fix_prompt,
    is_code_memory as _is_code_memory,
    split_reverification_candidates,
)
from memory.v1.janitor_duplicates import (
    duplicate_deletion_groups,
    parse_stored_utc as _parse_stored_utc,
)
from memory.v1.janitor_log_retention import (
    LOG_MAX_AGE_DAYS,
    SELF_IMPROVE_REPORT_MAX_AGE_DAYS,
    should_delete_log_file,
    should_delete_self_improve_report,
)
from memory.v1.janitor_normalization import (
    empty_normalization_result,
    long_term_normalization_candidates,
    rewrite_normalization_prompt,
    rewritten_normalized_metadata,
    split_plan_memories,
    split_normalization_prompt,
    split_normalized_metadatas,
)
from memory.v1.janitor_query_markers import (
    dynamic_query_marker_payload,
    marker_labels_from_metadatas,
)
from memory.v1.janitor_report import (
    janitor_history_entry,
    janitor_report_payload,
)
from memory.v1.janitor_rules import (
    classify_known_junk,
)
from memory.v1.janitor_theme_dedupe import (
    cross_session_theme_deletion_id,
    short_term_theme_entries,
)

load_dotenv(ENV_FILE_PATH)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory_janitor")

DB_PATH = VECTOR_DB_USER_MEMORIES
SHORT_TERM_DB_PATH = VECTOR_DB_SHORT_TERM
JANITOR_LOG = JANITOR_REPORT
VAULT_IMAGES_DIR = os.path.join(VAULT_DIR, "images")


MEMORY_JANITOR_MODEL = JANITOR_LLM_MODEL  # Uses configured frontier provider/model.
MAX_DEDUP_THEMES_PER_RUN = 150
MAX_CODE_MEMORIES_PER_RUN = 20  # Limit per night to avoid orchestrator timeout
CODE_MEMORY_REVERIFY_DAYS = 14
MAX_LONG_TERM_NORMALIZE_PER_RUN = 25
LONG_TERM_REVIEW_THRESHOLD = 500
LONG_TERM_REWRITE_THRESHOLD = 800
LONG_TERM_SPLIT_THRESHOLD = 1500
MAX_REWRITTEN_CHARS = 500
MAX_SPLIT_ITEMS = 6
JANITOR_DELETE_QUARANTINE = os.path.join(LOGS_DIR, "janitor_deleted_memories.jsonl")

# "Theme" topics — long-term entries whose whole point is to accumulate detail
# under one anchor over time. The normalizer must NOT split or compact these,
# because that would shatter the per-project (and per-identity) anchor we
# want retrieval to find. Atomic topics (Decision, Commitment, Failure Lesson,
# External Relationship) and everything else remain eligible for normalization.
THEME_TOPICS = frozenset({
    "Identity Evolution",
    "Project: vessence",
    "Project: classes.chiehwu.com",
    "Project: waterlily",
    "Architectural Milestones",
    "Collaborative Habits",
    "Aesthetic Preferences",
})

def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _codex_skill_exists(skill_name: str) -> bool:
    return (Path.home() / ".codex" / "skills" / skill_name / "SKILL.md").exists()


def _vessence_docker_compose_missing() -> bool:
    return not os.path.exists(os.path.join(_VESSENCE_HOME, "docker-compose.yml"))


def _llm_json(prompt: str) -> dict:
    """Call the configured frontier provider via CLI for JSON output."""
    system_msg = (
        "Return only valid JSON. You are a memory curator. "
        "Only merge facts that are truly redundant — describing the exact same knowledge. "
        "Non-redundant facts MUST be preserved as-is. When in doubt, do NOT merge."
    )

    # --- Primary frontier CLI (JANE_BRAIN: opus/claude, codex/openai, gemini) ---
    try:
        from agent_skills.claude_cli_llm import completion_orchestrator
        text = completion_orchestrator(
            f"{system_msg}\n\n{prompt}",
            max_tokens=4096,
            timeout=180,
            cwd=_VESSENCE_HOME,
        )
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
    except Exception as e:
        logger.warning(
            "Configured frontier janitor call failed provider=%s model=%s: %s; trying Gemini fallback...",
            FRONTIER_PROVIDER,
            MEMORY_JANITOR_MODEL,
            e,
        )

    # --- Gemini (fallback) ---
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=google_key)
            model = genai.GenerativeModel(FALLBACK_GEMINI_MODEL)
            response = model.generate_content(
                f"{system_msg}\n\n{prompt}",
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            logger.warning(f"Gemini janitor call failed: {e}")

    raise ValueError("Configured frontier CLI failed and no GOOGLE_API_KEY available as fallback")


def _llm_text(prompt: str, max_chars: int | None = None) -> str:
    """Call the configured frontier provider via CLI for compact text output."""
    system_msg = (
        "Return plain text only. You are a careful memory curator. "
        "Preserve only durable facts, decisions, root causes, fixes, lessons, "
        "or reusable references. Remove transcript chatter and boilerplate."
    )

    try:
        from agent_skills.claude_cli_llm import completion_orchestrator
        text = completion_orchestrator(
            f"{system_msg}\n\n{prompt}",
            max_tokens=2048,
            timeout=180,
            cwd=_VESSENCE_HOME,
        ).strip()
        if text.startswith("```"):
            lines = [l for l in text.split("\n") if not l.startswith("```")]
            text = "\n".join(lines).strip()
        return text[:max_chars].strip() if max_chars else text
    except Exception as e:
        logger.warning(
            "Configured frontier janitor text call failed provider=%s model=%s: %s",
            FRONTIER_PROVIDER,
            MEMORY_JANITOR_MODEL,
            e,
        )
    return ""


def _append_quarantine_entries(entries: list[dict]) -> int:
    """Append deleted-memory backups to an append-only quarantine log."""
    if not entries:
        return 0
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(JANITOR_DELETE_QUARANTINE, "a") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return len(entries)
    except Exception as e:
        logger.warning("Could not append janitor quarantine log: %s", e)
        return 0


def _classify_known_junk(collection_name: str, doc: str, meta: dict | None) -> str | None:
    return classify_known_junk(
        collection_name,
        doc,
        meta,
        user_collection_name=CHROMA_COLLECTION_USER_MEMORIES,
        long_term_collection_name=CHROMA_COLLECTION_LONG_TERM,
        codex_skill_exists=_codex_skill_exists,
        vessence_docker_compose_missing=_vessence_docker_compose_missing,
    )


def _quarantine_entries_for_rows(
    collection_name: str,
    rows: list[dict],
    reason: str,
    *,
    deleted_at: str,
) -> list[dict]:
    return [
        {
            "deleted_at": deleted_at,
            "collection": collection_name,
            "reason": reason,
            "id": row["id"],
            "doc": row["doc"],
            "meta": row["meta"],
        }
        for row in rows
    ]


def _delete_rows_with_quarantine(collection, collection_name: str, rows: list[dict], reason: str) -> int:
    """Back up rows to quarantine, then delete them from Chroma."""
    if not rows:
        return 0
    now = _utcnow_iso()
    ids = [r["id"] for r in rows]
    _append_quarantine_entries(
        _quarantine_entries_for_rows(collection_name, rows, reason, deleted_at=now)
    )
    collection.delete(ids=ids)
    logger.info("Deleted %d rows from %s: %s", len(ids), collection_name, reason)
    return len(ids)


def _collect_collection_rows(collection) -> list[dict]:
    data = collection.get(include=["documents", "metadatas"])
    return [
        {"id": row_id, "doc": doc or "", "meta": meta or {}}
        for row_id, doc, meta in zip(
            data.get("ids", []),
            data.get("documents", []),
            data.get("metadatas", []),
        )
    ]


def _purge_exact_duplicate_rows(collection, collection_name: str, rows: list[dict]) -> dict:
    """Delete exact duplicate memories after quarantining the older copies."""
    deleted = 0
    duplicate_groups = 0
    for stale_rows in duplicate_deletion_groups(rows):
        duplicate_groups += 1
        deleted += _delete_rows_with_quarantine(
            collection,
            collection_name,
            stale_rows,
            "Exact duplicate long-term memory",
        )

    return {"deleted": deleted, "groups": duplicate_groups}


def _normalize_long_term_memory_rows(collection, rows: list[dict]) -> dict:
    """Rewrite or split oversized long_term_knowledge entries into compact facts."""
    candidates = long_term_normalization_candidates(
        rows,
        theme_topics=THEME_TOPICS,
        review_threshold=LONG_TERM_REVIEW_THRESHOLD,
        limit=MAX_LONG_TERM_NORMALIZE_PER_RUN,
        classify_junk=lambda row: _classify_known_junk(
            CHROMA_COLLECTION_LONG_TERM,
            row["doc"],
            row["meta"],
        ),
    )

    result = empty_normalization_result()

    for row in candidates:
        try:
            doc = row["doc"].strip()
            if not doc:
                continue
            result["reviewed"] += 1

            if len(doc) > LONG_TERM_SPLIT_THRESHOLD:
                prompt = split_normalization_prompt(row, doc)
                plan = _llm_json(prompt)
                memories = split_plan_memories(
                    plan,
                    max_chars=MAX_REWRITTEN_CHARS,
                    max_items=MAX_SPLIT_ITEMS,
                )
                if len(memories) >= 2:
                    new_ids = [str(uuid.uuid4()) for _ in memories]
                    new_metas = split_normalized_metadatas(
                        row,
                        memories,
                        now_iso=_utcnow_iso(),
                    )
                    collection.add(ids=new_ids, documents=memories, metadatas=new_metas)
                    result["split"] += 1
                    result["deleted_originals"] += _delete_rows_with_quarantine(
                        collection,
                        CHROMA_COLLECTION_LONG_TERM,
                        [row],
                        "Normalized oversized long-term memory into atomic records",
                    )
                    continue

            if len(doc) > LONG_TERM_REWRITE_THRESHOLD:
                rewritten = _llm_text(
                    rewrite_normalization_prompt(row, doc, max_chars=MAX_REWRITTEN_CHARS),
                    max_chars=MAX_REWRITTEN_CHARS,
                )
                if rewritten:
                    collection.update(
                        ids=[row["id"]],
                        documents=[rewritten],
                        metadatas=[rewritten_normalized_metadata(
                            row,
                            rewritten,
                            now_iso=_utcnow_iso(),
                        )],
                    )
                    result["rewritten"] += 1
                    continue

            result["unchanged"] += 1
        except Exception as e:
            logger.warning("Long-term normalization failed for %s: %s", row["id"][:12], e)
            result["unchanged"] += 1

    return result


def _consolidate_collection(
    collection,
    collection_name: str,
    rows: list[dict],
    max_topics: int,
) -> dict:
    """Merge truly redundant memories topic-by-topic inside one collection."""
    grouped = group_consolidation_topics(
        rows,
        collection_name=collection_name,
        user_collection_name=CHROMA_COLLECTION_USER_MEMORIES,
        classify_junk=lambda doc, meta, name: _classify_known_junk(name, doc, meta),
    )
    topic_groups = grouped.topic_groups
    permanent_count = grouped.permanent_count

    consolidate_candidates = consolidation_topic_candidates(topic_groups)
    if consolidate_candidates:
        logger.info(
            "Consolidating %d topics (out of %d needing work) in %s...",
            min(len(consolidate_candidates), max_topics),
            len(consolidate_candidates),
            collection_name,
        )
    else:
        logger.info("No topics need consolidation in %s.", collection_name)

    total_reduced = 0
    merge_log = []
    target_topics = consolidate_candidates[:max_topics]
    for topic in target_topics:
        memories = topic_groups[topic]
        logger.info("Analyzing topic '%s' with %d facts in %s...", topic, len(memories), collection_name)
        prompt = consolidation_prompt(topic, memories)
        try:
            plan = _llm_json(prompt)
            row_map = {m["id"]: m for m in memories}
            for merge in plan.get("merges", []):
                old_ids = [oid for oid in merge.get("original_ids", []) if oid in row_map]
                if len(old_ids) < 2:
                    continue
                new_text = str(merge.get("new_fact") or "").strip()
                if not new_text:
                    continue
                new_sub = str(merge.get("new_subtopic") or "").strip()
                old_rows = [row_map[oid] for oid in old_ids]
                _delete_rows_with_quarantine(
                    collection,
                    collection_name,
                    old_rows,
                    f"Consolidated redundant memories in topic `{topic}`",
                )
                base_meta = consolidated_memory_metadata(
                    collection_name=collection_name,
                    user_collection_name=CHROMA_COLLECTION_USER_MEMORIES,
                    topic=topic,
                    old_rows=old_rows,
                    new_subtopic=new_sub,
                    now_iso=_utcnow_iso(),
                    default_user_id=os.environ.get("USER_NAME", "user"),
                )
                new_id = str(uuid.uuid4())
                collection.add(documents=[new_text], ids=[new_id], metadatas=[base_meta])
                total_reduced += (len(old_ids) - 1)
                merge_log.append({
                    "collection": collection_name,
                    "topic": topic,
                    "subtopic": new_sub,
                    "originals": [row["doc"] for row in old_rows],
                    "merged_into": new_text,
                    "ids_removed": old_ids,
                    "new_id": new_id,
                })
        except Exception as e:
            logger.error("Failed to process topic '%s' in %s: %s", topic, collection_name, e)

    return {
        "topic_groups": topic_groups,
        "permanent_count": permanent_count,
        "vectors_reduced": total_reduced,
        "merge_log": merge_log,
    }


def _purge_known_junk(collection, collection_name: str, rows: list[dict]) -> dict:
    junk_rows = []
    reasons: dict[str, list[dict]] = {}
    for row in rows:
        reason = _classify_known_junk(collection_name, row["doc"], row["meta"])
        if not reason:
            continue
        junk_rows.append(row)
        reasons.setdefault(reason, []).append(row)

    deleted = 0
    deleted_by_reason = {}
    for reason, grouped_rows in reasons.items():
        count = _delete_rows_with_quarantine(collection, collection_name, grouped_rows, reason)
        deleted += count
        deleted_by_reason[reason] = count
    return {"deleted": deleted, "by_reason": deleted_by_reason}


def _is_expired(expires_at) -> bool:
    """Returns True if expires_at (Unix int or ISO string) has passed."""
    return is_expired_value(expires_at)


def purge_expired_short_term() -> int:
    """
    Delete all short-term memory entries whose expires_at has passed.
    Covers:
      1. Shared short_term_memory DB (new design)
      2. Legacy forgettable entries still in user_memories (transitional)
    Returns the total count of purged entries.
    """
    total_purged = 0

    # 1. Shared short-term DB
    if os.path.exists(SHORT_TERM_DB_PATH):
        try:
            st_client = get_chroma_client(path=SHORT_TERM_DB_PATH)
            st_collection = st_client.get_collection(name="short_term_memory")
            st_all = st_collection.get(include=["metadatas"])
            expired_ids = expired_ids_from_metadata(st_all.get("ids", []), st_all.get("metadatas", []))
            if expired_ids:
                st_collection.delete(ids=expired_ids)
                logger.info(f"Purged {len(expired_ids)} expired entries from short_term_memory.")
            total_purged += len(expired_ids)
        except Exception as e:
            logger.warning(f"Could not purge short_term_memory: {e}")

    if total_purged == 0:
        logger.info("No expired short-term memories to purge.")
    return total_purged


# Keep old name as alias for backwards compatibility with any callers
def purge_expired_forgettable(collection) -> int:
    return purge_expired_short_term()


def purge_old_forgettable_memories(max_age_days: int = 14) -> int:
    """
    Delete short-term/forgettable memories older than max_age_days by creation
    timestamp, regardless of expires_at. Enforces a hard age cap.
    """
    if not os.path.exists(SHORT_TERM_DB_PATH):
        return 0
    try:
        st_client = get_chroma_client(path=SHORT_TERM_DB_PATH)
        st_collection = st_client.get_collection(name="short_term_memory")
        st_all = st_collection.get(include=["metadatas"])
        cutoff = _utcnow() - datetime.timedelta(days=max_age_days)
        old_ids = old_ids_from_metadata(st_all.get("ids", []), st_all.get("metadatas", []), cutoff=cutoff)
        if old_ids:
            st_collection.delete(ids=old_ids)
            logger.info(f"Purged {len(old_ids)} forgettable memories older than {max_age_days} days.")
        return len(old_ids)
    except Exception as e:
        logger.warning(f"Could not purge old forgettable memories: {e}")
        return 0


def backfill_thematic_archival(max_sessions: int = 2):
    """
    Nightly backstop for long-term archival. Archival is window-based: turns
    are grouped into idle-delimited windows across ALL session_ids and each
    closed window is promoted (per-session archival broke once the runtime
    began minting a fresh session_id per request — most "sessions" hold only
    2 turns, far below any archival threshold).

    `max_sessions` is kept for signature/cron compatibility and reused as the
    per-run window cap (min 20). `run_window_archival` is watermark-tracked
    and idempotent, so this drains the backlog progressively across runs.
    """
    try:
        from jane.config import LEDGER_DB_PATH
        from memory.v1.conversation_manager import ConversationManager
    except Exception as e:
        logger.warning(f"backfill: imports failed: {e}")
        return {"status": "import-failed", "error": str(e)}
    if not os.path.exists(LEDGER_DB_PATH):
        logger.info("backfill: no ledger db at %s; skipping.", LEDGER_DB_PATH)
        return {"status": "no-ledger", "ledger": LEDGER_DB_PATH}
    try:
        cm = ConversationManager(session_id="janitor-window-archival")
        try:
            result = cm.run_window_archival(
                force=True, max_windows=max(20, int(max_sessions or 0))
            )
            logger.info("backfill: window archival result: %s", result)
            return result
        finally:
            cm.close()
    except Exception as e:
        logger.warning(f"Could not run window-archival backfill: {e}")
        return {"status": "failed", "error": str(e)}


def dedup_cross_session_themes(
    similarity_threshold: float = 0.10,
    max_themes_per_run: int = MAX_DEDUP_THEMES_PER_RUN,
):
    """Remove near-duplicate theme entries across different sessions.

    When the same topic is discussed in multiple sessions, their theme
    summaries can overlap significantly.  This function finds themes that
    are semantically very similar (low ChromaDB distance) across sessions
    and keeps only the most recently updated one.
    """
    if not os.path.exists(SHORT_TERM_DB_PATH):
        return
    try:
        st_client = get_chroma_client(path=SHORT_TERM_DB_PATH)
        st_collection = st_client.get_collection(name="short_term_memory")
        all_items = st_collection.get(include=["documents", "metadatas"])

        themes = short_term_theme_entries(all_items)

        if len(themes) < 2:
            return

        total_themes = len(themes)
        if total_themes > max_themes_per_run:
            import random as _random
            _random.shuffle(themes)
            themes = themes[:max_themes_per_run]
            logger.info(
                "Dedup scanning %d of %d cross-session themes this run.",
                len(themes), total_themes,
            )

        # For each theme, query its nearest neighbor across ALL sessions
        ids_to_delete = set()
        seen_pairs = set()
        for theme in themes:
            if theme["id"] in ids_to_delete:
                continue
            results = st_collection.query(
                query_texts=[theme["document"]],
                n_results=3,
                include=["metadatas", "distances"],
            )
            for j, neighbor_id in enumerate(results["ids"][0]):
                if neighbor_id == theme["id"] or neighbor_id in ids_to_delete:
                    continue
                pair_key = tuple(sorted([theme["id"], neighbor_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                distance = results["distances"][0][j]
                neighbor_meta = results["metadatas"][0][j] or {}

                delete_id = cross_session_theme_deletion_id(
                    theme,
                    neighbor_id=neighbor_id,
                    neighbor_meta=neighbor_meta,
                    distance=distance,
                    similarity_threshold=similarity_threshold,
                )
                if delete_id == neighbor_id:
                    ids_to_delete.add(neighbor_id)
                elif delete_id == theme["id"]:
                    ids_to_delete.add(theme["id"])
                    break  # This theme is being deleted, stop checking its neighbors

        if ids_to_delete:
            st_collection.delete(ids=list(ids_to_delete))
            logger.info(f"Deduped {len(ids_to_delete)} cross-session theme(s) in short-term memory.")
        else:
            logger.info("No cross-session theme duplicates found.")

    except Exception as e:
        logger.warning(f"Cross-session theme dedup failed: {e}")


def refresh_dynamic_query_markers() -> dict:
    """Scan all ChromaDB collections, extract unique topic/subtopic values,
    and write them to a JSON file grouped by intent category.

    Mapping:
      user_memories topics/subtopics  → personal_markers
      long_term_knowledge topics      → project_markers
      file_index_memories topics      → file_markers
      short_term_memory topics        → project_markers (recent work context)
    """
    def _extract_labels(db_path: str, collection_name: str) -> set[str]:
        """Return unique topic and subtopic values from a collection."""
        try:
            client = get_chroma_client(path=db_path)
            coll = client.get_collection(name=collection_name)
            results = coll.get(include=["metadatas"])
            return marker_labels_from_metadatas(results["metadatas"])
        except Exception as e:
            logger.warning(f"Could not scan {collection_name}: {e}")
            return set()

    markers = dynamic_query_marker_payload(
        user_labels=_extract_labels(VECTOR_DB_USER_MEMORIES, CHROMA_COLLECTION_USER_MEMORIES),
        long_term_labels=_extract_labels(VECTOR_DB_LONG_TERM, CHROMA_COLLECTION_LONG_TERM),
        short_term_labels=_extract_labels(VECTOR_DB_SHORT_TERM, CHROMA_COLLECTION_SHORT_TERM),
        file_labels=_extract_labels(VECTOR_DB_FILE_INDEX, CHROMA_COLLECTION_FILE_INDEX),
        updated_at=_utcnow_iso(),
    )

    try:
        os.makedirs(os.path.dirname(DYNAMIC_QUERY_MARKERS_PATH), exist_ok=True)
        with open(DYNAMIC_QUERY_MARKERS_PATH, "w") as f:
            json.dump(markers, f, indent=2)
        logger.info(
            "Dynamic query markers refreshed: %d personal, %d project, %d file.",
            len(markers.get("personal_markers", [])),
            len(markers.get("project_markers", [])),
            len(markers.get("file_markers", [])),
        )
    except Exception as e:
        logger.warning(f"Could not write dynamic query markers: {e}")

    return markers


def run_janitor(max_sessions: int = 2, max_topics: int = 3):
    # Load gate: wait until CPU/memory is acceptable.
    # Bypassed entirely during the night window — the gate exists to keep
    # the web/Android UI responsive while Chieh is awake. At night nobody
    # is waiting on the UI, and deferring just means the janitor (the last
    # nightly job) never runs at all.
    try:
        from agent_skills.system_load import wait_until_safe, _is_nighttime
        if _is_nighttime():
            logger.info("Nighttime — bypassing load gate, running janitor.")
        elif not wait_until_safe(max_wait_minutes=5):
            logger.info("System busy — skipping janitor this cycle.")
            return
    except Exception:
        pass

    # Step 0: Backfill closed conversation windows that missed thematic archival.
    conversation_archival = backfill_thematic_archival(max_sessions=max_sessions)

    # Step 0.25: Purge expired short-term memories once backfill candidates
    # have had a chance to archive. This lets TTL cleanup happen even if
    # later janitor stages time out.
    expired_purged = purge_expired_short_term()
    old_forgettable_purged = purge_old_forgettable_memories(
        max_age_days=FORGETTABLE_MAX_AGE_DAYS
    )

    # Step 0.5: Deduplicate themes across sessions in short-term memory
    dedup_cross_session_themes()

    # Purge old logs and set up image cluster placeholder — these run every
    # cycle regardless of whether consolidation has work to do.
    log_files_purged = purge_old_log_files()
    self_improve_reports_purged = purge_old_self_improve_reports()
    # image_cluster_result = cluster_vault_images() disabled due to cost
    image_cluster_result = {"images_moved": 0, "folders_created": [], "disabled": True}

    user_client = get_chroma_client(path=DB_PATH)
    try:
        user_collection = user_client.get_collection(name=CHROMA_COLLECTION_USER_MEMORIES)
    except Exception:
        logger.info("No user_memories collection found.")
        user_collection = None

    long_term_client = get_chroma_client(path=VECTOR_DB_LONG_TERM)
    try:
        long_term_collection = long_term_client.get_collection(name=CHROMA_COLLECTION_LONG_TERM)
    except Exception:
        logger.info("No long_term_knowledge collection found.")
        long_term_collection = None

    total_reduced = 0
    merge_log = []
    user_topics = {}
    long_term_topics = {}
    permanent_count = 0
    known_junk_deleted = {
        CHROMA_COLLECTION_USER_MEMORIES: {"deleted": 0, "by_reason": {}},
        CHROMA_COLLECTION_LONG_TERM: {"deleted": 0, "by_reason": {}},
    }
    exact_duplicate_deleted = {
        CHROMA_COLLECTION_USER_MEMORIES: {"deleted": 0, "groups": 0},
        CHROMA_COLLECTION_LONG_TERM: {"deleted": 0, "groups": 0},
    }
    normalization_result = empty_normalization_result()

    if user_collection is not None:
        user_rows = _collect_collection_rows(user_collection)
        known_junk_deleted[CHROMA_COLLECTION_USER_MEMORIES] = _purge_known_junk(
            user_collection,
            CHROMA_COLLECTION_USER_MEMORIES,
            user_rows,
        )
        user_rows = _collect_collection_rows(user_collection)
        exact_duplicate_deleted[CHROMA_COLLECTION_USER_MEMORIES] = _purge_exact_duplicate_rows(
            user_collection,
            CHROMA_COLLECTION_USER_MEMORIES,
            user_rows,
        )
        user_rows = _collect_collection_rows(user_collection)
        user_result = _consolidate_collection(
            user_collection,
            CHROMA_COLLECTION_USER_MEMORIES,
            user_rows,
            max_topics=max_topics,
        )
        user_topics = user_result["topic_groups"]
        permanent_count = user_result["permanent_count"]
        total_reduced += user_result["vectors_reduced"]
        merge_log.extend(user_result["merge_log"])

    if long_term_collection is not None:
        long_term_rows = _collect_collection_rows(long_term_collection)
        known_junk_deleted[CHROMA_COLLECTION_LONG_TERM] = _purge_known_junk(
            long_term_collection,
            CHROMA_COLLECTION_LONG_TERM,
            long_term_rows,
        )
        long_term_rows = _collect_collection_rows(long_term_collection)
        exact_duplicate_deleted[CHROMA_COLLECTION_LONG_TERM] = _purge_exact_duplicate_rows(
            long_term_collection,
            CHROMA_COLLECTION_LONG_TERM,
            long_term_rows,
        )
        long_term_rows = _collect_collection_rows(long_term_collection)
        normalization_result = _normalize_long_term_memory_rows(long_term_collection, long_term_rows)
        long_term_rows = _collect_collection_rows(long_term_collection)
        long_term_result = _consolidate_collection(
            long_term_collection,
            CHROMA_COLLECTION_LONG_TERM,
            long_term_rows,
            max_topics=max_topics,
        )
        long_term_topics = long_term_result["topic_groups"]
        total_reduced += long_term_result["vectors_reduced"]
        merge_log.extend(long_term_result["merge_log"])

    # 4. Save report
    run_timestamp = datetime.datetime.now().isoformat()
    report = janitor_report_payload(
        run_timestamp=run_timestamp,
        total_reduced=total_reduced,
        merge_log=merge_log,
        expired_purged=expired_purged,
        old_forgettable_purged=old_forgettable_purged,
        permanent_count=permanent_count,
        conversation_archival=conversation_archival,
        user_topics=user_topics,
        long_term_topics=long_term_topics,
        user_collection_name=CHROMA_COLLECTION_USER_MEMORIES,
        long_term_collection_name=CHROMA_COLLECTION_LONG_TERM,
        known_junk_deleted=known_junk_deleted,
        exact_duplicate_deleted=exact_duplicate_deleted,
        normalization_result=normalization_result,
        delete_quarantine_log=JANITOR_DELETE_QUARANTINE,
        log_files_purged=log_files_purged,
        self_improve_reports_purged=self_improve_reports_purged,
        image_cluster_result=image_cluster_result,
    )
    with open(JANITOR_LOG, "w") as f:
        json.dump(report, f, indent=2)

    # Append to consolidation history (append-only log for tracking over time)
    history_path = os.path.join(LOGS_DIR, "janitor_consolidation_history.jsonl")
    history_entry = janitor_history_entry(
        run_timestamp=run_timestamp,
        total_reduced=total_reduced,
        merge_log=merge_log,
        expired_purged=expired_purged,
        old_forgettable_purged=old_forgettable_purged,
        conversation_archival=conversation_archival,
        known_junk_deleted=known_junk_deleted,
        exact_duplicate_deleted=exact_duplicate_deleted,
        normalization_result=normalization_result,
    )
    try:
        with open(history_path, "a") as f:
            f.write(json.dumps(history_entry) + "\n")
    except Exception as e:
        logger.warning(f"Could not write consolidation history: {e}")

    # Verify code-referencing memories against the real codebase.
    # Codex audits → configured frontier provider validates + fixes stale entries.
    try:
        verify_result = verify_code_memories()
        logger.info("Memory verification: %d checked, %d stale, %d fixed",
                     verify_result.get("checked", 0),
                     verify_result.get("stale", 0),
                     verify_result.get("fixed", 0))
    except Exception as e:
        logger.warning("verify_code_memories failed: %s", e)

    # Final step: refresh dynamic query markers from all collections
    refresh_dynamic_query_markers()

    logger.info(
        "Janitor finished. Reduced %d facts (%d merges), deleted %d stale/junk rows and %d duplicate rows, normalized %d long-term rows.",
        total_reduced,
        len(merge_log),
        known_junk_deleted[CHROMA_COLLECTION_USER_MEMORIES]["deleted"]
        + known_junk_deleted[CHROMA_COLLECTION_LONG_TERM]["deleted"],
        exact_duplicate_deleted[CHROMA_COLLECTION_USER_MEMORIES]["deleted"]
        + exact_duplicate_deleted[CHROMA_COLLECTION_LONG_TERM]["deleted"],
        normalization_result["rewritten"] + normalization_result["split"],
    )

# ── Memory vs Code Verification ─────────────────────────────────────────────
#
# Memories about Vessence's own code (file paths, model names, cron schedules,
# architecture claims) drift fast because we change the code daily. This step
# loops through code-referencing memories ONE AT A TIME, sending each to Codex
# individually to keep token cost low per call. Stale findings go to the
# configured frontier provider (JANE_BRAIN: opus/codex/gemini) for validation
# before editing ChromaDB.

import subprocess as _sp
import re as _re

_CODEX_BIN = "codex"
_VESSENCE_HOME = str(Path(__file__).resolve().parents[2])


def _memory_needs_reverification(
    meta: dict | None,
    now_utc: datetime.datetime | None = None,
) -> bool:
    """Skip code memories that were already checked recently."""
    verified_at = (meta or {}).get("code_verified_at")
    verified_dt = _parse_stored_utc(verified_at)
    if verified_dt is None:
        return True
    if now_utc is None:
        now_utc = _utcnow()
    return (now_utc - verified_dt) >= datetime.timedelta(days=CODE_MEMORY_REVERIFY_DAYS)


def _stamp_code_verification(
    col,
    mem: dict,
    *,
    status: str,
    explanation: str = "",
    corrected_text: str | None = None,
) -> dict:
    """Persist verification metadata so nightly runs can skip fresh checks."""
    meta = dict(mem.get("metadata") or {})
    meta["code_verified_at"] = _utcnow_iso()
    meta["code_verification_status"] = status
    if explanation:
        meta["code_verification_note"] = explanation[:240]
    else:
        meta.pop("code_verification_note", None)
    try:
        update_kwargs = {"ids": [mem["id"]], "metadatas": [meta]}
        if corrected_text is not None:
            update_kwargs["documents"] = [corrected_text]
        col.update(**update_kwargs)
        return {"ok": True, "reason": ""}
    except Exception as e:
        return {"ok": False, "reason": f"stamp_failed: {e}"}


def _verify_one_memory(mem: dict, codex_timeout: int = 7200) -> dict:
    """Verify a single memory against the codebase via Codex.

    Returns {"verdict": "ACCURATE|STALE|PARTIAL", "explanation": ...,
             "corrected_text": ... or None}.
    On error returns {"verdict": "ERROR", "explanation": ...}.
    """
    codex_prompt = code_verification_prompt(mem)
    try:
        result = _sp.run(
            [_CODEX_BIN, "exec", "-"],
            input=codex_prompt,
            capture_output=True, text=True,
            timeout=codex_timeout,
            cwd=_VESSENCE_HOME,
        )
        raw = result.stdout.strip()
    except _sp.TimeoutExpired:
        return {"verdict": "ERROR", "explanation": "codex_timeout"}
    except FileNotFoundError:
        return {"verdict": "ERROR", "explanation": "codex_not_found"}

    json_match = _re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        return {"verdict": "ERROR", "explanation": f"parse_fail: {raw[:200]}"}
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        return {"verdict": "ERROR", "explanation": f"json_decode: {raw[:200]}"}


def _apply_fix_via_frontier(mem: dict, codex_finding: dict, col,
                            frontier_timeout: int = 7200) -> dict:
    """Send one Codex finding to the frontier provider and apply confirmed fixes.

    Returns {"action": "updated|deleted|kept|error", "reason": ...}.
    """
    frontier_prompt = frontier_fix_prompt(mem, codex_finding)
    try:
        from agent_skills.claude_cli_llm import completion_orchestrator
        raw = completion_orchestrator(
            frontier_prompt,
            max_tokens=4096,
            timeout=frontier_timeout,
            cwd=_VESSENCE_HOME,
        ).strip()
    except TimeoutError:
        return {"action": "error", "reason": "frontier_timeout"}
    except Exception as e:
        return {"action": "error", "reason": f"frontier_failed: {e}"}

    json_match = _re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        return {"action": "error", "reason": f"parse_fail: {raw[:200]}"}
    try:
        action = json.loads(json_match.group())
    except json.JSONDecodeError:
        return {"action": "error", "reason": f"json_decode: {raw[:200]}"}

    act = action.get("action", "keep").lower()
    reason = action.get("reason", "")
    corrected = action.get("corrected_text")
    mem_id = mem["id"]

    if act == "update" and corrected:
        stamp = _stamp_code_verification(
            col,
            mem,
            status="updated",
            explanation=reason,
            corrected_text=corrected,
        )
        if stamp["ok"]:
            logger.info("verify_code_memories: UPDATED %s — %s", mem_id[:12], reason[:80])
            return {"action": "updated", "reason": reason}
        return {"action": "error", "reason": stamp["reason"]}

    elif act == "delete":
        try:
            _append_quarantine_entries([{
                "deleted_at": _utcnow_iso(),
                "collection": CHROMA_COLLECTION_USER_MEMORIES,
                "reason": f"verify_code_memories: {reason}",
                "id": mem_id,
                "doc": mem.get("text", ""),
                "meta": {
                    "topic": mem.get("topic", ""),
                    "subtopic": mem.get("subtopic", ""),
                },
            }])
            col.delete(ids=[mem_id])
            logger.info("verify_code_memories: DELETED %s — %s", mem_id[:12], reason[:80])
            return {"action": "deleted", "reason": reason}
        except Exception as e:
            return {"action": "error", "reason": f"delete_failed: {e}"}

    else:
        stamp = _stamp_code_verification(
            col,
            mem,
            status="kept",
            explanation=reason,
        )
        if stamp["ok"]:
            logger.info("verify_code_memories: KEPT %s — %s", mem_id[:12], reason[:80])
            return {"action": "kept", "reason": reason}
        return {"action": "error", "reason": stamp["reason"]}


def verify_code_memories(
    codex_timeout: int = 7200,
    frontier_timeout: int = 7200,
    max_memories_per_run: int | None = MAX_CODE_MEMORIES_PER_RUN,
) -> dict:
    """Verify code-referencing memories one at a time against the real codebase.

    Loops through ALL code-referencing memories in user_memories, verifying
    each individually via Codex. Only memories flagged STALE or PARTIAL get
    sent to the configured frontier provider for validation and correction.
    This keeps per-call token cost low while achieving full coverage.
    """
    chroma_client = get_chroma_client(path=DB_PATH)
    try:
        col = chroma_client.get_collection(name="user_memories")
    except Exception:
        logger.info("verify_code_memories: no user_memories collection")
        return {"checked": 0, "stale": 0, "fixed": 0}

    all_data = col.get(include=["documents", "metadatas"])
    code_mems = code_memory_records_from_collection(all_data, is_code_memory_fn=_is_code_memory)
    if not code_mems:
        logger.info("verify_code_memories: no code-referencing memories found")
        return {"checked": 0, "stale": 0, "fixed": 0, "skipped_recent": 0}

    now_utc = _utcnow()
    code_mems, skipped_recent = split_reverification_candidates(
        code_mems,
        needs_reverification_fn=lambda meta: _memory_needs_reverification(
            meta,
            now_utc=now_utc,
        ),
    )
    if skipped_recent:
        logger.info(
            "verify_code_memories: skipped %d recently verified memories (%d-day window)",
            skipped_recent,
            CODE_MEMORY_REVERIFY_DAYS,
        )
    if not code_mems:
        logger.info("verify_code_memories: all code memories were recently verified")
        return {
            "checked": 0,
            "stale": 0,
            "fixed": 0,
            "deleted": 0,
            "errors": 0,
            "skipped_recent": skipped_recent,
            "details": [],
        }

    # Sort by verification date (oldest first). Memories never verified
    # (None) come before those with a timestamp.
    code_mems.sort(key=code_memory_verification_sort_key)

    total_candidates = len(code_mems)
    if max_memories_per_run is not None and total_candidates > max_memories_per_run:
        code_mems = code_mems[:max_memories_per_run]
        logger.info(
            "verify_code_memories: checking %d of %d code memories (oldest first)",
            len(code_mems), total_candidates,
        )

    logger.info("verify_code_memories: checking %d memories one at a time", len(code_mems))

    checked = 0
    stale_count = 0
    fixed = 0
    deleted = 0
    errors = 0
    details = []

    for i, mem in enumerate(code_mems):
        checked += 1
        logger.info("verify_code_memories: [%d/%d] %s — %s",
                     i + 1, len(code_mems), mem["id"][:12], mem["text"][:60])

        finding = _verify_one_memory(mem, codex_timeout=codex_timeout)
        verdict = finding.get("verdict", "ERROR").upper()

        if verdict == "ERROR":
            errors += 1
            logger.warning("verify_code_memories: [%d/%d] error: %s",
                           i + 1, len(code_mems), finding.get("explanation", "?")[:100])
            continue

        if verdict == "ACCURATE":
            stamp = _stamp_code_verification(
                col,
                mem,
                status="accurate",
                explanation=finding.get("explanation", ""),
            )
            if not stamp["ok"]:
                errors += 1
                details.append({"id": mem["id"], "action": "error", "reason": stamp["reason"]})
                continue
            details.append({"id": mem["id"], "action": "accurate", "reason": finding.get("explanation", "")})
            continue

        stale_count += 1
        logger.info(
            "verify_code_memories: [%d/%d] Codex says %s — sending to frontier provider %s",
            i + 1,
            len(code_mems),
            verdict,
            FRONTIER_PROVIDER,
        )

        result = _apply_fix_via_frontier(mem, finding, col, frontier_timeout=frontier_timeout)
        act = result.get("action", "error")
        if act == "updated":
            fixed += 1
        elif act == "deleted":
            deleted += 1
        elif act == "error":
            errors += 1
        details.append({"id": mem["id"], "action": act, "reason": result.get("reason", "")})

    # Log vocal summary
    try:
        sys.path.insert(0, _VESSENCE_HOME)
        from agent_skills.self_improve_log import log_vocal_summary
        total_fixed = fixed + deleted
        if total_fixed > 0:
            log_vocal_summary(
                job="Memory Verification",
                what_was_wrong=(
                    f"Found {stale_count} stale memories out of {checked} checked"
                ),
                why_it_mattered=(
                    "Stale memories make Jane give wrong answers about her "
                    "own architecture and capabilities"
                ),
                what_was_done=(
                    f"Updated {fixed}, deleted {deleted} after verifying "
                    f"each one against the actual code"
                ),
                severity="medium",
            )
        else:
            log_vocal_summary(
                job="Memory Verification",
                summary=(
                    f"Verified {checked} code-related memories one at a time. "
                    f"Skipped {skipped_recent} recently verified entries. "
                    f"All checked out — no stale entries."
                ),
                severity="info",
            )
    except Exception as e:
        logger.warning("verify_code_memories: vocal summary failed: %s", e)

    result = code_verification_result(
        checked=checked,
        stale=stale_count,
        fixed=fixed,
        deleted=deleted,
        errors=errors,
        skipped_recent=skipped_recent,
        details=details,
    )

    report_path = os.path.join(_VESSENCE_HOME, "configs", "memory_verification_report.md")
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(report_path, "w") as f:
            f.write(code_verification_report_markdown(timestamp=ts, result=result))
    except Exception as e:
        logger.warning("verify_code_memories: report write failed: %s", e)

    return result


def purge_old_log_files(max_age_days: int = LOG_MAX_AGE_DAYS) -> int:
    """
    Recursively scan LOGS_DIR and delete .log files older than max_age_days.
    Protected logs (audit trails, history) are kept for 90 days instead.
    Returns the count of deleted files.
    """
    if not os.path.isdir(LOGS_DIR):
        logger.info(f"Logs directory does not exist: {LOGS_DIR}")
        return 0

    now_ts = _utcnow().timestamp()
    deleted = 0

    for dirpath, _dirnames, filenames in os.walk(LOGS_DIR):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                if should_delete_log_file(
                    fname,
                    os.path.getmtime(fpath),
                    now_ts=now_ts,
                    max_age_days=max_age_days,
                ):
                    os.remove(fpath)
                    logger.info(f"Deleted old log file: {fpath}")
                    deleted += 1
            except Exception as e:
                logger.warning(f"Could not delete {fpath}: {e}")

    if deleted:
        logger.info(f"Purged {deleted} log files older than {max_age_days} days.")
    else:
        logger.info("No old log files to purge.")
    return deleted


def purge_old_self_improve_reports(
    max_age_days: int = SELF_IMPROVE_REPORT_MAX_AGE_DAYS,
) -> int:
    """Drop archived nightly self-improvement reports older than the cutoff.

    The orchestrator writes a timestamped .md to
    $VESSENCE_DATA_HOME/reports/self_improvement/ every night. These build up
    indefinitely because purge_old_log_files() only touches .log/.jsonl.
    """
    data_home = os.environ.get("VESSENCE_DATA_HOME")
    if not data_home:
        return 0
    reports_dir = os.path.join(data_home, "reports", "self_improvement")
    if not os.path.isdir(reports_dir):
        return 0

    now_ts = _utcnow().timestamp()
    deleted = 0
    for fname in os.listdir(reports_dir):
        fpath = os.path.join(reports_dir, fname)
        try:
            if should_delete_self_improve_report(
                fname,
                os.path.getmtime(fpath),
                now_ts=now_ts,
                max_age_days=max_age_days,
            ):
                os.remove(fpath)
                logger.info(f"Deleted old self-improve report: {fpath}")
                deleted += 1
        except Exception as e:
            logger.warning(f"Could not delete {fpath}: {e}")

    if deleted:
        logger.info(f"Purged {deleted} self-improve reports older than {max_age_days} days.")
    return deleted


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.heic'}


def cluster_vault_images() -> dict:
    """
    Clusters images in vault/images into sensible subfolders based on their
    ChromaDB descriptions. Moves files and updates all ChromaDB references.
    Returns a summary dict.
    """
    if not os.path.exists(VAULT_IMAGES_DIR):
        logger.info("No vault/images directory found, skipping image clustering.")
        return {"images_moved": 0, "folders_created": []}

    # 1. Collect all image files (only from the root images/ dir — already-clustered
    #    subfolders are left alone unless they contain new flat files dropped in root)
    flat_images = []
    for fname in os.listdir(VAULT_IMAGES_DIR):
        fpath = os.path.join(VAULT_IMAGES_DIR, fname)
        if os.path.isfile(fpath) and os.path.splitext(fname)[1].lower() in IMAGE_EXTENSIONS:
            flat_images.append(fname)

    if not flat_images:
        logger.info("No flat images in vault/images root to cluster.")
        return {"images_moved": 0, "folders_created": []}

    logger.info(f"Found {len(flat_images)} flat images to cluster: {flat_images}")

    # 2. Query ChromaDB for descriptions of each image
    chroma_client = get_chroma_client(path=VECTOR_DB_USER_MEMORIES)
    try:
        col = chroma_client.get_collection(name=CHROMA_COLLECTION_USER_MEMORIES)
    except Exception:
        logger.warning("user_memories collection not found, skipping image clustering.")
        return {"images_moved": 0, "folders_created": []}

    all_entries = col.get(include=["documents", "metadatas"])
    all_docs = all_entries.get("documents", [])
    all_metas = all_entries.get("metadatas", [])
    all_ids = all_entries.get("ids", [])

    # Build manifest: {filename -> {description, chroma_ids_referencing, file_path_meta_ids}}
    manifest = {}
    for fname in flat_images:
        basename = os.path.splitext(fname)[0]
        refs = []
        file_path_ids = []
        for doc, meta, eid in zip(all_docs, all_metas, all_ids):
            # Match by filename anywhere in doc or file_path metadata
            fp = (meta or {}).get("file_path", "")
            if fname in doc or basename in doc or (fp and fname in fp):
                refs.append({"id": eid, "doc": doc, "meta": meta or {}})
                if fp and fname in fp:
                    file_path_ids.append(eid)
        description = " | ".join(r["doc"] for r in refs) if refs else f"Image file: {fname}"
        manifest[fname] = {
            "description": description[:500],
            "refs": refs,
            "file_path_ids": file_path_ids,
        }

    # 3. Ask DeepSeek to propose a folder hierarchy
    manifest_for_llm = {k: v["description"] for k, v in manifest.items()}
    prompt = f"""
You are organizing a personal photo/image archive into a clean folder hierarchy.
Below is a list of image filenames and their descriptions from memory.

Propose a subfolder structure under vault/images/ that groups them sensibly.
Use 2-3 levels max (e.g., people/spouse, agents, family/child, clinic).
Keep folder names lowercase, no spaces (use underscores).
Every image must be assigned to exactly one folder.

Return ONLY valid JSON:
{{
  "assignments": {{
    "filename.jpg": "subfolder/path",
    ...
  }},
  "reasoning": "brief explanation"
}}

IMAGES:
{json.dumps(manifest_for_llm, indent=2)}
"""
    try:
        plan = _llm_json(prompt)
    except Exception as e:
        logger.error(f"LLM clustering failed: {e}")
        return {"images_moved": 0, "folders_created": [], "error": str(e)}

    assignments = plan.get("assignments", {})
    logger.info(f"LLM cluster plan: {json.dumps(assignments)}")
    logger.info(f"Reasoning: {plan.get('reasoning', '')}")

    # 4. Move files and update ChromaDB
    images_moved = 0
    folders_created = set()

    for fname, subfolder in assignments.items():
        old_path = os.path.join(VAULT_IMAGES_DIR, fname)
        if not os.path.isfile(old_path):
            logger.warning(f"File not found, skipping: {old_path}")
            continue

        # Normalise subfolder path
        subfolder = subfolder.strip("/").replace("..", "")
        new_dir = os.path.join(VAULT_IMAGES_DIR, subfolder)
        new_path = os.path.join(new_dir, fname)

        if old_path == new_path:
            logger.info(f"Already in place: {fname}")
            continue

        os.makedirs(new_dir, exist_ok=True)
        folders_created.add(subfolder)

        # Handle filename collision
        if os.path.exists(new_path):
            base, ext = os.path.splitext(fname)
            new_path = os.path.join(new_dir, f"{base}_{uuid.uuid4().hex[:6]}{ext}")
            fname_final = os.path.basename(new_path)
        else:
            fname_final = fname

        shutil.move(old_path, new_path)
        images_moved += 1
        logger.info(f"Moved: {fname} → {subfolder}/{fname_final}")

        # 5. Update ChromaDB: patch all entries referencing this file
        old_rel = f"images/{fname}"
        new_rel = f"images/{subfolder}/{fname_final}"
        old_abs = old_path
        new_abs = new_path

        refs = manifest.get(fname, {}).get("refs", [])
        for ref in refs:
            eid = ref["id"]
            old_doc = ref["doc"]
            old_meta = dict(ref["meta"])

            # Update document text (replace old path/filename references)
            new_doc = old_doc
            for old_str, new_str in [
                (old_abs, new_abs),
                (old_rel, new_rel),
                (fname, fname_final),
            ]:
                new_doc = new_doc.replace(old_str, new_str)

            # Update file_path metadata if present
            if old_meta.get("file_path") and fname in old_meta["file_path"]:
                old_meta["file_path"] = old_meta["file_path"].replace(old_abs, new_abs).replace(old_rel, new_rel)

            # Re-upsert (ChromaDB doesn't support in-place update of documents)
            try:
                col.update(ids=[eid], documents=[new_doc], metadatas=[old_meta])
            except Exception as e:
                logger.warning(f"ChromaDB update failed for {eid}: {e}")

    result = {
        "images_moved": images_moved,
        "folders_created": sorted(folders_created),
        "reasoning": plan.get("reasoning", ""),
    }
    logger.info(f"Image clustering complete: {images_moved} moved, folders: {folders_created}")
    return result


if __name__ == "__main__":
    run_janitor()
