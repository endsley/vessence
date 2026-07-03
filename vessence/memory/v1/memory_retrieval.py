#!/usr/bin/env python3
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from jane.sanitizers import strip_client_tool_markers as _strip_client_tool_markers
from memory.v1.low_signal_memory import (
    LOW_SIGNAL_SHARED_PREFIXES,
    LOW_SIGNAL_SHORT_TERM_META_PREFIX_PATTERNS,
    LOW_SIGNAL_SHORT_TERM_PROTOCOL_PATTERNS,
    is_low_signal_shared_memory as _is_low_signal_shared_memory,
    is_low_signal_short_term_memory as _is_low_signal_short_term_memory,
)
from memory.v1.memory_sections_cache import (
    _SECTIONS_CACHE,
    _SECTIONS_CACHE_LOCK,
    _SECTIONS_CACHE_MAX_ENTRIES,
    _SECTIONS_CACHE_TTL_S,
    sections_cache_get as _sections_cache_get,
    sections_cache_put as _sections_cache_put,
)
from memory.v1.query_intent import (
    STATIC_FILE_MARKERS as _STATIC_FILE_MARKERS,
    classify_query_intent as _classify_query_intent,
    ds3000_lecture_subtopics as _ds3000_lecture_subtopics,
    is_file_index_record as _is_file_index_record,
    is_file_query as _is_file_query,
)
from memory.v1.query_plan import build_memory_query_plan as _build_memory_query_plan
from memory.v1.query_markers import (
    STATIC_PERSONAL_MARKERS as _STATIC_PERSONAL_MARKERS,
    STATIC_PROJECT_MARKERS as _STATIC_PROJECT_MARKERS,
    get_file_markers as _get_file_markers,
    get_personal_markers as _get_personal_markers,
    get_project_markers as _get_project_markers,
    reload_dynamic_markers_if_changed as _reload_dynamic_markers_if_changed,
)
from memory.v1.memory_summary_cache import (
    MemorySummaryCacheEntry,
    _memory_summary_cache,
    cosine_similarity as _cosine_similarity,
    invalidate_memory_summary_cache,
    lookup_cached_memory_summary as _lookup_cached_memory_summary,
    normalize_query as _normalize_query,
    prune_cache_entries as _prune_cache_entries,
    store_cached_memory_summary as _store_cached_memory_summary,
)
from memory.v1.memory_text import (
    extract_content_key as _extract_content_key,
    fmt_memory as _fmt_memory,
    is_expired as _is_expired,
    is_none_content as _is_none_content,
)
from memory.v1.memory_sections import build_memory_sections_from_facts as _build_memory_sections_from_facts
from memory.v1.nearest_memory import (
    nearest_memory_candidate as _nearest_memory_candidate,
    nearest_query_terms as _nearest_query_terms,
    select_nearest_memory_lines as _select_nearest_memory_lines,
)
from memory.v1.nearest_query_specs import build_nearest_query_specs as _build_nearest_query_specs
from memory.v1.retrieved_memory_facts import (
    collect_essence_facts as _collect_essence_facts,
    collect_file_index_facts as _collect_file_index_facts,
    collect_jane_long_term_facts as _collect_jane_long_term_facts,
    collect_short_term_semantic_facts as _collect_short_term_semantic_facts,
    collect_short_term_with_recency_boost as _collect_short_term_with_recency_boost,
    collect_user_memory_facts as _collect_user_memory_facts,
    within_distance as _within_distance,
)


class silence_stderr_fd:
    def __enter__(self):
        self.py_stdout = sys.stdout
        self.py_stderr = sys.stderr
        self.null_file = open(os.devnull, "w")
        sys.stdout = self.null_file
        sys.stderr = self.null_file
        self.stdout_fd = os.dup(1)
        self.stderr_fd = os.dup(2)
        self.null_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.null_fd, 1)
        os.dup2(self.null_fd, 2)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self.stdout_fd, 1)
        os.dup2(self.stderr_fd, 2)
        os.close(self.null_fd)
        os.close(self.stdout_fd)
        os.close(self.stderr_fd)
        sys.stdout = self.py_stdout
        sys.stderr = self.py_stderr
        # Do not close null_file here: some ML loaders keep a reference to the
        # Python stream and flush asynchronously during teardown.


os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')
with silence_stderr_fd():
    import chromadb


from chromadb.utils import embedding_functions

import logging

from jane.config import (
    get_chroma_client,
    CHROMA_COLLECTION_FILE_INDEX,
    CHROMA_COLLECTION_LONG_TERM,
    CHROMA_COLLECTION_SHORT_TERM,
    CHROMA_COLLECTION_USER_MEMORIES,
    CHROMA_FILE_INDEX_MAX_DISTANCE,
    CHROMA_LONG_TERM_MAX_DISTANCE,
    CHROMA_LONG_TERM_LIMIT,
    CHROMA_PERMANENT_MAX_DISTANCE,
    CHROMA_SEARCH_LIMIT,
    CHROMA_SHORT_TERM_MAX_DISTANCE,
    CHROMA_SHORT_TERM_LIMIT,
    CHROMA_USER_MAX_DISTANCE,
    VECTOR_DB_LONG_TERM,
    VECTOR_DB_SHORT_TERM,
    VECTOR_DB_FILE_INDEX,
    VECTOR_DB_USER_MEMORIES,
)

logger = logging.getLogger(__name__)


_query_embedding_fn = None


def _get_query_embedding_fn():
    """Get the BGE-small-en-v1.5 embedding model (cached singleton)."""
    global _query_embedding_fn
    if _query_embedding_fn is None:
        try:
            from sentence_transformers import SentenceTransformer
            _query_embedding_fn = SentenceTransformer('BAAI/bge-small-en-v1.5')
        except Exception:
            # Fallback to ONNX MiniLM if BGE fails
            with silence_stderr_fd():
                _query_embedding_fn = embedding_functions.ONNXMiniLM_L6_V2(
                    preferred_providers=["CPUExecutionProvider"]
                )
    return _query_embedding_fn


def _embed_query_text(query: str) -> list[float] | None:
    normalized = _normalize_query(query)
    if not normalized:
        return None
    try:
        model = _get_query_embedding_fn()
        # BGE (SentenceTransformer) vs ONNX (ChromaDB embedding function)
        if hasattr(model, 'encode'):
            vectors = model.encode([normalized]).tolist()
        else:
            with silence_stderr_fd():
                vectors = model([normalized])
    except Exception:
        return None
    if not vectors:
        return None
    return [float(v) for v in vectors[0]]


def _query_collection(client_path: str, collection_name: str, query: str, limit: int, query_embedding: list[float] | None = None) -> tuple[list[str], list[dict], list[float | None]]:
    if not os.path.exists(client_path):
        return [], [], []

    try:
        with silence_stderr_fd():
            client = get_chroma_client(path=client_path)
            collection = client.get_collection(name=collection_name)
        n_results = min(limit, collection.count())
        if n_results <= 0:
            return [], [], []
        with silence_stderr_fd():
            # Use pre-computed embedding if available (200x faster than query_texts)
            if query_embedding:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
            else:
                results = collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        return docs, metas, distances
    except Exception:
        return [], [], []


def _get_ds3000_lecture_anchors(subtopics: list[str]) -> list[tuple[str, dict]]:
    if not subtopics or not os.path.exists(VECTOR_DB_USER_MEMORIES):
        return []
    try:
        with silence_stderr_fd():
            client = get_chroma_client(path=VECTOR_DB_USER_MEMORIES)
            collection = client.get_collection(name=CHROMA_COLLECTION_USER_MEMORIES)
            results = collection.get(
                where={"topic": "ds3000_lecture_notes"},
                include=["documents", "metadatas"],
            )
    except Exception:
        return []

    wanted = set(subtopics)
    anchors: list[tuple[str, dict]] = []
    for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
        meta = meta or {}
        if meta.get("subtopic") in wanted and not _is_expired(meta) and not _is_none_content(doc):
            anchors.append((doc, meta))
    return anchors


def build_memory_sections(
    query: str,
    assistant_name: str = "Jane",
    essence_chromadb_path: str | None = None,
    user_memory_path: str | None = None,
    user_id: str | None = None,
) -> list[str]:
    cache_key = (
        query or "",
        assistant_name or "",
        essence_chromadb_path or "",
        user_memory_path or "",
        user_id or "",
    )
    cached = _sections_cache_get(cache_key)
    if cached is not None:
        return cached

    intent = _classify_query_intent(query)
    plan = _build_memory_query_plan(
        intent=intent,
        assistant_name=assistant_name,
        essence_chromadb_path=essence_chromadb_path,
        user_memory_path=user_memory_path,
    )

    # Pre-compute embedding ONCE — pass to all queries to avoid re-embedding
    with silence_stderr_fd():
        query_emb = _embed_query_text(query)

    # --- Submit all applicable queries in parallel ---
    futures: dict[str, "Future"] = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        if plan.use_user_memory or plan.use_shared:
            futures["user_memories"] = executor.submit(
                _query_collection,
                user_memory_path if plan.use_user_memory else VECTOR_DB_USER_MEMORIES,
                CHROMA_COLLECTION_USER_MEMORIES,
                query,
                CHROMA_SEARCH_LIMIT,
                query_emb,
            )
        if plan.use_jane_long_term:
            futures["jane_long_term"] = executor.submit(
                _query_collection,
                VECTOR_DB_LONG_TERM,
                CHROMA_COLLECTION_LONG_TERM,
                query,
                CHROMA_LONG_TERM_LIMIT,
                query_emb,
            )
        if plan.use_short_term:
            futures["short_term"] = executor.submit(
                _query_collection,
                VECTOR_DB_SHORT_TERM,
                CHROMA_COLLECTION_SHORT_TERM,
                query,
                CHROMA_SHORT_TERM_LIMIT,
                query_emb,
            )
        if plan.use_file_index:
            futures["file_index"] = executor.submit(
                _query_collection,
                VECTOR_DB_FILE_INDEX,
                CHROMA_COLLECTION_FILE_INDEX,
                query,
                min(8, CHROMA_SEARCH_LIMIT),
                query_emb,
            )
        if plan.use_essence:
            futures["essence"] = executor.submit(
                _query_collection,
                essence_chromadb_path,
                "essence_knowledge",
                query,
                CHROMA_SEARCH_LIMIT,
            )

    # --- Collect results, gracefully handling per-query failures ---
    def _safe_get(future_key: str) -> tuple[list[str], list[dict], list[float | None]]:
        if future_key not in futures:
            return [], [], []
        try:
            return futures[future_key].result()
        except Exception:
            return [], [], []

    # -- user_memories (shared or managed-user private Chroma) --
    permanent_facts: list[str] = []
    long_term_facts: list[str] = []
    legacy_short_term_facts: list[str] = []

    exact_ds3000_anchors = []
    if plan.use_shared:
        exact_ds3000_anchors = _get_ds3000_lecture_anchors(_ds3000_lecture_subtopics(query))
        long_term_facts.extend(_fmt_memory(doc, meta) for doc, meta in exact_ds3000_anchors)

    if plan.use_user_memory or plan.use_shared:
        docs, metas, distances = _safe_get("user_memories")
        user_facts = _collect_user_memory_facts(
            docs,
            metas,
            distances,
            exact_anchor_docs=(doc for doc, _meta in exact_ds3000_anchors),
            permanent_max_distance=CHROMA_PERMANENT_MAX_DISTANCE,
            short_term_max_distance=CHROMA_SHORT_TERM_MAX_DISTANCE,
            user_max_distance=CHROMA_USER_MAX_DISTANCE,
        )
        permanent_facts.extend(user_facts.permanent)
        long_term_facts.extend(user_facts.long_term)
        legacy_short_term_facts.extend(user_facts.legacy_short_term)

    if plan.use_shared and plan.use_short_term:
        try:
            with silence_stderr_fd():
                client = get_chroma_client(path=VECTOR_DB_USER_MEMORIES)
                collection = client.get_collection(name=CHROMA_COLLECTION_USER_MEMORIES)
                extra_results = collection.get(
                    where={"memory_type": "forgettable"},
                    include=["documents", "metadatas"],
                )
            extra_ids = extra_results.get("ids", [])
            extra_docs = extra_results.get("documents", [])
            extra_metas = extra_results.get("metadatas", [])
            for extra_id, extra_doc, extra_meta in zip(extra_ids, extra_docs, extra_metas):
                if _is_expired(extra_meta):
                    continue
                if _is_none_content(extra_doc) or _is_low_signal_short_term_memory(extra_doc, extra_meta):
                    continue
                legacy_short_term_facts.append(_fmt_memory(extra_doc, extra_meta))
        except Exception:
            pass

    # -- jane long-term --
    jane_long_term_facts: list[str] = []
    if plan.use_jane_long_term:
        jane_lt_docs, jane_lt_metas, jane_lt_distances = _safe_get("jane_long_term")
        jane_long_term_facts = _collect_jane_long_term_facts(
            jane_lt_docs,
            jane_lt_metas,
            jane_lt_distances,
            max_distance=CHROMA_LONG_TERM_MAX_DISTANCE,
        )

    # -- short-term (semantic match + recency boost) --
    short_term_facts: list[str] = []
    if plan.use_short_term:
        st_docs, st_metas, st_distances = _safe_get("short_term")
        short_term_facts = _collect_short_term_semantic_facts(
            st_docs,
            st_metas,
            st_distances,
            max_distance=CHROMA_SHORT_TERM_MAX_DISTANCE,
        )
        # Recency boost: always include the N most recent short-term entries
        # regardless of semantic similarity, so recent changes never get missed.
        try:
            _st_path = VECTOR_DB_SHORT_TERM
            if os.path.exists(_st_path):
                with silence_stderr_fd():
                    _st_client = get_chroma_client(path=_st_path)
                    _st_col = _st_client.get_collection(name=CHROMA_COLLECTION_SHORT_TERM)
                _all = _st_col.get(include=["documents", "metadatas"], limit=min(200, _st_col.count()))
                if _all["documents"]:
                    short_term_facts = _collect_short_term_with_recency_boost(
                        short_term_facts,
                        _all["documents"],
                        _all["metadatas"],
                        limit=3,
                    )
        except Exception:
            pass  # recency boost is best-effort

    # -- file index --
    file_index_facts: list[str] = []
    if plan.use_file_index:
        fi_docs, fi_metas, fi_distances = _safe_get("file_index")
        file_index_facts = _collect_file_index_facts(
            fi_docs,
            fi_metas,
            fi_distances,
            max_distance=CHROMA_FILE_INDEX_MAX_DISTANCE,
        )

    # -- essence memory --
    essence_facts: list[str] = []
    if plan.use_essence:
        ess_docs, ess_metas, ess_distances = _safe_get("essence")
        essence_facts = _collect_essence_facts(
            ess_docs,
            ess_metas,
            ess_distances,
            max_distance=CHROMA_USER_MAX_DISTANCE,
        )

    sections = _build_memory_sections_from_facts(
        permanent_facts=permanent_facts,
        long_term_facts=long_term_facts,
        jane_long_term_facts=jane_long_term_facts,
        short_term_facts=short_term_facts,
        file_index_facts=file_index_facts,
        legacy_short_term_facts=legacy_short_term_facts,
        essence_facts=essence_facts,
        use_user_memory=plan.use_user_memory,
    )
    _sections_cache_put(cache_key, sections)
    return sections


def query_nearest_memory_lines(
    query: str,
    limit: int = 2,
    max_distance: float = 0.50,
    min_lexical_overlap: float = 0.34,
    assistant_name: str = "Jane",
    essence_chromadb_path: str | None = None,
    user_memory_path: str | None = None,
) -> list[str]:
    """Return the nearest formatted memory lines below a distance threshold.

    This is intentionally narrower than build_memory_sections(): it is for
    per-turn Codex preloading, where a small high-confidence prelude is better
    than broad memory recall.
    """
    normalized = _normalize_query(query)
    if not normalized or limit <= 0:
        return []

    intent = _classify_query_intent(query)
    plan = _build_memory_query_plan(
        intent=intent,
        assistant_name=assistant_name,
        essence_chromadb_path=essence_chromadb_path,
        user_memory_path=user_memory_path,
    )

    query_emb = _embed_query_text(query)
    query_terms = _nearest_query_terms(normalized)
    candidates: list[tuple[int, float, str, str, str]] = []

    for doc, meta in _get_ds3000_lecture_anchors(_ds3000_lecture_subtopics(query)):
        candidates.append((0, 0.0, "user_memories", _extract_content_key(doc), _fmt_memory(doc, meta)))

    def _add_candidate(source: str, doc: str, meta: dict | None, distance: float | None) -> None:
        candidate = _nearest_memory_candidate(
            source,
            doc,
            meta,
            distance,
            query_terms=query_terms,
            max_distance=max_distance,
            min_lexical_overlap=min_lexical_overlap,
        )
        if candidate is not None:
            candidates.append(candidate)

    query_specs = _build_nearest_query_specs(
        plan,
        user_memory_path=user_memory_path,
        essence_chromadb_path=essence_chromadb_path,
        limit=limit,
        vector_db_user_memories=VECTOR_DB_USER_MEMORIES,
        collection_user_memories=CHROMA_COLLECTION_USER_MEMORIES,
        vector_db_long_term=VECTOR_DB_LONG_TERM,
        collection_long_term=CHROMA_COLLECTION_LONG_TERM,
        long_term_limit=CHROMA_LONG_TERM_LIMIT,
        vector_db_short_term=VECTOR_DB_SHORT_TERM,
        collection_short_term=CHROMA_COLLECTION_SHORT_TERM,
        short_term_limit=CHROMA_SHORT_TERM_LIMIT,
        vector_db_file_index=VECTOR_DB_FILE_INDEX,
        collection_file_index=CHROMA_COLLECTION_FILE_INDEX,
        chroma_search_limit=CHROMA_SEARCH_LIMIT,
    )

    # Run sequentially. The underlying Chroma/SentenceTransformer stack writes
    # to process-wide stdout/stderr during lazy loads; parallel lookups can race
    # the fd redirection and leak noise into Codex prompt preflight output.
    for source, path, collection, search_limit in query_specs:
        try:
            docs, metas, distances = _query_collection(
                path,
                collection,
                query,
                search_limit,
                query_emb,
            )
        except Exception:
            continue
        for doc, meta, distance in zip(docs, metas, distances):
            _add_candidate(source, doc, meta, distance)

    return _select_nearest_memory_lines(candidates, limit)
