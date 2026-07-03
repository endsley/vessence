"""Report payload builders for the memory janitor."""

from __future__ import annotations

from typing import Any


def janitor_report_payload(
    *,
    run_timestamp: str,
    total_reduced: int,
    merge_log: list[dict[str, Any]],
    expired_purged: int,
    old_forgettable_purged: int,
    permanent_count: int,
    conversation_archival: Any,
    user_topics: dict[str, Any],
    long_term_topics: dict[str, Any],
    user_collection_name: str,
    long_term_collection_name: str,
    known_junk_deleted: dict[str, Any],
    exact_duplicate_deleted: dict[str, Any],
    normalization_result: dict[str, Any],
    delete_quarantine_log: str,
    log_files_purged: int,
    self_improve_reports_purged: int,
    image_cluster_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "last_run": run_timestamp,
        "vectors_reduced": total_reduced,
        "merges_performed": len(merge_log),
        "forgettable_memories_purged": expired_purged + old_forgettable_purged,
        "forgettable_expired_by_ttl": expired_purged,
        "forgettable_expired_by_age": old_forgettable_purged,
        "permanent_memories_protected": permanent_count,
        "conversation_archival": conversation_archival,
        "topics_processed": {
            user_collection_name: list(user_topics.keys()),
            long_term_collection_name: list(long_term_topics.keys()),
        },
        "known_junk_deleted": known_junk_deleted,
        "exact_duplicate_deleted": exact_duplicate_deleted,
        "long_term_normalization": normalization_result,
        "delete_quarantine_log": delete_quarantine_log,
        "log_files_purged": log_files_purged,
        "self_improve_reports_purged": self_improve_reports_purged,
        "image_clustering": image_cluster_result,
        "merge_details": merge_log,
    }


def janitor_history_entry(
    *,
    run_timestamp: str,
    total_reduced: int,
    merge_log: list[dict[str, Any]],
    expired_purged: int,
    old_forgettable_purged: int,
    conversation_archival: Any,
    known_junk_deleted: dict[str, Any],
    exact_duplicate_deleted: dict[str, Any],
    normalization_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "timestamp": run_timestamp,
        "vectors_reduced": total_reduced,
        "merges_performed": len(merge_log),
        "forgettable_purged": expired_purged + old_forgettable_purged,
        "topics_with_merges": list({f"{merge['collection']}::{merge['topic']}" for merge in merge_log}),
        "conversation_archival": conversation_archival,
        "known_junk_deleted": known_junk_deleted,
        "exact_duplicate_deleted": exact_duplicate_deleted,
        "long_term_normalization": normalization_result,
        "merges": merge_log,
    }
