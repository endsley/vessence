"""Plan nearest-memory Chroma query specs without executing them."""
from __future__ import annotations

from typing import Any


NearestQuerySpec = tuple[str, str, str, int]


def build_nearest_query_specs(
    plan: Any,
    *,
    user_memory_path: str | None,
    essence_chromadb_path: str | None,
    limit: int,
    vector_db_user_memories: str,
    collection_user_memories: str,
    vector_db_long_term: str,
    collection_long_term: str,
    long_term_limit: int,
    vector_db_short_term: str,
    collection_short_term: str,
    short_term_limit: int,
    vector_db_file_index: str,
    collection_file_index: str,
    chroma_search_limit: int,
) -> list[NearestQuerySpec]:
    query_specs: list[NearestQuerySpec] = []
    if plan.use_user_memory or plan.use_shared:
        query_specs.append((
            "user_memories",
            user_memory_path if plan.use_user_memory else vector_db_user_memories,
            collection_user_memories,
            max(chroma_search_limit, limit * 4),
        ))
    if plan.use_jane_long_term:
        query_specs.append((
            "jane_long_term",
            vector_db_long_term,
            collection_long_term,
            max(long_term_limit, limit * 4),
        ))
    if plan.use_short_term:
        query_specs.append((
            "short_term",
            vector_db_short_term,
            collection_short_term,
            max(short_term_limit, limit * 4),
        ))
    if plan.use_file_index:
        query_specs.append((
            "file_index",
            vector_db_file_index,
            collection_file_index,
            max(8, limit * 4),
        ))
    if plan.use_essence:
        query_specs.append((
            "essence",
            essence_chromadb_path or "",
            "essence_knowledge",
            max(chroma_search_limit, limit * 4),
        ))
    return query_specs
