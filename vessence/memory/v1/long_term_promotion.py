"""Pure helpers for promoting archivist memories to long-term stores."""

from __future__ import annotations

from typing import Any


def merge_candidates_from_query_result(existing: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not existing:
        return []
    documents = existing.get("documents") or []
    if not documents or not documents[0]:
        return []

    ids = existing.get("ids") or [[]]
    distances = existing.get("distances") or []
    matches: list[dict[str, Any]] = []
    for index, doc in enumerate(documents[0]):
        matches.append(
            {
                "id": ids[0][index],
                "doc": doc,
                "dist": (
                    distances[0][index]
                    if distances and distances[0] and index < len(distances[0])
                    else 1.0
                ),
            }
        )
    return matches


def memory_merge_prompt(category: str, content: str, matches: list[dict[str, Any]]) -> str:
    prompt = (
        "You are a Memory Architect. I want to add a new memory arc to the long-term knowledge base.\n\n"
        f"New Memory Category: {category}\n"
        f"New Memory Content: {content}\n\n"
        "Here are the most similar existing memories in this category:\n"
    )
    for index, match in enumerate(matches):
        prompt += (
            f"Match {index + 1} (ID: {match['id']}, Distance: {match['dist']:.4f}):\n"
            f"{match['doc']}\n\n"
        )

    prompt += (
        "Decision Criteria:\n"
        "- MERGE: If the new memory is a continuation, update, or near-duplicate of an existing one. "
        "Provide a single comprehensive summary that includes ALL unique still-current details from both. "
        "If the new memory supersedes, reverses, or narrows older details, make the corrected current "
        "state explicit and keep the old state only as brief historical rationale when useful.\n"
        "- NEW: If the new memory represents a distinct event, different architectural component, or unrelated fact.\n\n"
        "Respond ONLY with a JSON object:\n"
        "{ \"decision\": \"MERGE\" | \"NEW\", \"target_id\": \"id_to_overwrite\", \"merged_content\": \"new_summary_if_merge\" }"
    )
    return prompt


def archivist_memory_metadata(
    *,
    session_id: str,
    category: str,
    timestamp: str,
    is_user_memory: bool,
    user_name: str,
    status: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source": "conversation_archivist",
        "session_id": session_id,
        "topic": category,
        "timestamp": timestamp,
    }
    if status:
        metadata["status"] = status
    if is_user_memory:
        metadata["user_id"] = user_name
        metadata["memory_type"] = "long_term"
        metadata["author"] = "archivist"
    return metadata
