#!/usr/bin/env python3
import chromadb
import uuid
import os
import sys
import json
import logging
import datetime
import shutil
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import (
    ENV_FILE_PATH, VECTOR_DB_USER_MEMORIES, VECTOR_DB_SHORT_TERM,
    CHROMA_COLLECTION_USER_MEMORIES, CHROMA_COLLECTION_SHORT_TERM,
    FORGETTABLE_MAX_AGE_DAYS, JANITOR_REPORT, LOGS_DIR,
    JANITOR_LLM_MODEL, OPENAI_API_URL,
    FALLBACK_GEMINI_MODEL, FALLBACK_OPENAI_MODEL, VAULT_DIR,
)

load_dotenv(ENV_FILE_PATH)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory_janitor")

DB_PATH = VECTOR_DB_USER_MEMORIES
SHORT_TERM_DB_PATH = VECTOR_DB_SHORT_TERM
JANITOR_LOG = JANITOR_REPORT
VAULT_IMAGES_DIR = os.path.join(VAULT_DIR, "images")


MEMORY_JANITOR_MODEL = "claude-opus-4-6"  # Memory is too important for a cheap model


def _llm_json(prompt: str) -> dict:
    """Call Claude Opus via CLI for JSON output. Memory consolidation uses
    Opus 4.6 to avoid corruption from cheaper models."""
    system_msg = (
        "Return only valid JSON. You are a memory curator. "
        "Only merge facts that are truly redundant — describing the exact same knowledge. "
        "Non-redundant facts MUST be preserved as-is. When in doubt, do NOT merge."
    )

    # --- Claude CLI with Opus (primary — uses Pro/Max subscription) ---
    try:
        from agent_skills.claude_cli_llm import completion
        text = completion(
            f"{system_msg}\n\n{prompt}",
            model=MEMORY_JANITOR_MODEL,
            max_tokens=4096,
            timeout=180,
        )
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Claude Opus janitor call failed: {e}, trying Gemini fallback...")

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

    raise ValueError("Claude CLI failed and no GOOGLE_API_KEY available as fallback")


def _is_expired(expires_at) -> bool:
    """Returns True if expires_at (Unix int or ISO string) has passed."""
    if not expires_at:
        return False
    now_ts = datetime.datetime.utcnow().timestamp()
    if isinstance(expires_at, (int, float)):
        return expires_at < now_ts
    try:
        return datetime.datetime.fromisoformat(str(expires_at)).timestamp() < now_ts
    except Exception:
        return False


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
            st_client = chromadb.PersistentClient(path=SHORT_TERM_DB_PATH)
            st_collection = st_client.get_collection(name="short_term_memory")
            st_all = st_collection.get(include=["metadatas"])
            expired_ids = [
                fid for fid, meta in zip(st_all.get("ids", []), st_all.get("metadatas", []))
                if _is_expired((meta or {}).get("expires_at"))
            ]
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
        st_client = chromadb.PersistentClient(path=SHORT_TERM_DB_PATH)
        st_collection = st_client.get_collection(name="short_term_memory")
        st_all = st_collection.get(include=["metadatas"])
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=max_age_days)
        old_ids = []
        for fid, meta in zip(st_all.get("ids", []), st_all.get("metadatas", [])):
            ts = (meta or {}).get("timestamp")
            if ts:
                try:
                    if datetime.datetime.fromisoformat(str(ts)) < cutoff:
                        old_ids.append(fid)
                except Exception:
                    pass
        if old_ids:
            st_collection.delete(ids=old_ids)
            logger.info(f"Purged {len(old_ids)} forgettable memories older than {max_age_days} days.")
        return len(old_ids)
    except Exception as e:
        logger.warning(f"Could not purge old forgettable memories: {e}")
        return 0


def run_janitor():
    # Load gate: wait until CPU/memory is acceptable
    try:
        from agent_skills.system_load import wait_until_safe
        if not wait_until_safe(max_wait_minutes=15):
            logger.info("System busy — skipping janitor this cycle.")
            return
    except Exception:
        pass

    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        collection = client.get_collection(name="user_memories")
    except Exception:
        logger.info("No user_memories collection found.")
        return

    # Step 0: Purge expired short-term memories + enforce 2-week hard cap
    expired_purged = purge_expired_short_term()
    old_forgettable_purged = purge_old_forgettable_memories(max_age_days=FORGETTABLE_MAX_AGE_DAYS)

    # 1. Fetch all memories with metadata
    all_mems = collection.get(include=["documents", "metadatas"])
    
    if not all_mems['documents']:
        return

    # 2. Group by Topic (Exclude Permanent)
    topic_groups = {} # topic -> list of {id, text, subtopic}
    permanent_count = 0

    for i, (doc, meta, id) in enumerate(zip(all_mems['documents'], all_mems['metadatas'], all_mems['ids'])):
        is_permanent = (
            meta.get("memory_type") == "permanent" or
            meta.get("memory_type") in ("forgettable", "short_term") or  # expire naturally, don't merge
            "Saved file '" in doc or
            "Location: " in doc or
            meta.get("file_path") is not None
        )
        
        if is_permanent:
            permanent_count += 1
            continue
        
        topic = meta.get("topic", "General")
        subtopic = meta.get("subtopic", "General")
        
        if topic not in topic_groups:
            topic_groups[topic] = []
        
        topic_groups[topic].append({"id": id, "text": doc, "subtopic": subtopic})

    if not topic_groups:
        logger.info(f"No long-term memories to consolidate. (Skipped {permanent_count} permanent memories)")
        return

    # 3a. Purge old log files (older than 3 weeks)
    log_files_purged = purge_old_log_files()

    # 3b. Cluster vault images into subfolders
    image_cluster_result = cluster_vault_images()

    total_reduced = 0
    merge_log = []  # Track every merge: originals, result, topic

    for topic, memories in topic_groups.items():
        if len(memories) < 5:
            continue

        logger.info(f"Analyzing topic '{topic}' with {len(memories)} facts...")

        prompt = f"""
You are a careful Memory Curator for a personal AI system. Below is a list of facts for the topic: '{topic}'.

YOUR RULES:
1. ONLY merge facts that are truly redundant — they describe the EXACT SAME knowledge, just worded differently.
2. If two facts share a topic but describe DIFFERENT things, they are NOT redundant. Leave them alone.
3. When merging, preserve ALL specific details from both facts. Do not lose any information.
4. Preserve the 'subtopic' field. If merged facts have different subtopics, keep the most specific one.
5. When in doubt, do NOT merge. It is far better to keep a slight duplicate than to lose a unique fact.
6. Facts that are the ONLY one about their specific subject must NEVER appear in a merge.

Return your response as a JSON object. The "merges" array should ONLY contain groups of truly redundant facts.
If no facts are redundant, return {{"merges": []}}.

{{
  "merges": [
    {{
      "original_ids": ["id1", "id2"],
      "new_fact": "Comprehensive merged fact preserving all details",
      "new_subtopic": "Most specific subtopic"
    }}
  ]
}}

FACTS FOR TOPIC '{topic}':
{json.dumps(memories, indent=2)}
"""

        try:
            plan = _llm_json(prompt)
            
            for merge in plan.get("merges", []):
                old_ids = merge["original_ids"]
                new_text = merge["new_fact"]
                new_sub = merge.get("new_subtopic", "General")

                # Capture original texts before deletion
                original_texts = []
                for oid in old_ids:
                    for m in memories:
                        if m["id"] == oid:
                            original_texts.append(m["text"])
                            break

                # Delete old
                collection.delete(ids=old_ids)
                # Add new
                new_id = str(uuid.uuid4())
                collection.add(
                    documents=[new_text],
                    ids=[new_id],
                    metadatas=[{"author": "janitor", "status": "compressed", "topic": topic, "subtopic": new_sub}]
                )
                total_reduced += (len(old_ids) - 1)

                # Log the merge details
                merge_log.append({
                    "topic": topic,
                    "subtopic": new_sub,
                    "originals": original_texts,
                    "merged_into": new_text,
                    "ids_removed": old_ids,
                    "new_id": new_id,
                })
        except Exception as e:
            logger.error(f"Failed to process topic '{topic}': {e}")

    # 4. Save report
    run_timestamp = datetime.datetime.now().isoformat()
    report = {
        "last_run": run_timestamp,
        "vectors_reduced": total_reduced,
        "merges_performed": len(merge_log),
        "forgettable_memories_purged": expired_purged + old_forgettable_purged,
        "forgettable_expired_by_ttl": expired_purged,
        "forgettable_expired_by_age": old_forgettable_purged,
        "permanent_memories_protected": permanent_count,
        "topics_processed": list(topic_groups.keys()),
        "log_files_purged": log_files_purged,
        "image_clustering": image_cluster_result,
        "merge_details": merge_log,
    }
    with open(JANITOR_LOG, "w") as f:
        json.dump(report, f, indent=2)

    # Append to consolidation history (append-only log for tracking over time)
    history_path = os.path.join(LOGS_DIR, "janitor_consolidation_history.jsonl")
    history_entry = {
        "timestamp": run_timestamp,
        "vectors_reduced": total_reduced,
        "merges_performed": len(merge_log),
        "forgettable_purged": expired_purged + old_forgettable_purged,
        "topics_with_merges": list({m["topic"] for m in merge_log}),
        "merges": merge_log,
    }
    try:
        with open(history_path, "a") as f:
            f.write(json.dumps(history_entry) + "\n")
    except Exception as e:
        logger.warning(f"Could not write consolidation history: {e}")

    logger.info(f"Janitor finished. Reduced {total_reduced} facts ({len(merge_log)} merges) across {len(topic_groups)} topics.")

LOG_MAX_AGE_DAYS = 21  # 3 weeks


def purge_old_log_files(max_age_days: int = LOG_MAX_AGE_DAYS) -> int:
    """
    Recursively scan LOGS_DIR and delete .log files older than max_age_days.
    Returns the count of deleted files.
    """
    if not os.path.isdir(LOGS_DIR):
        logger.info(f"Logs directory does not exist: {LOGS_DIR}")
        return 0

    cutoff_ts = datetime.datetime.utcnow().timestamp() - (max_age_days * 86400)
    deleted = 0

    for dirpath, _dirnames, filenames in os.walk(LOGS_DIR):
        for fname in filenames:
            if not fname.endswith(".log"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                if os.path.getmtime(fpath) < cutoff_ts:
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
    chroma_client = chromadb.PersistentClient(path=VECTOR_DB_USER_MEMORIES)
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
