"""Pure theme-registry helpers for conversation archival."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any


USER_IDENTITY_SIGNALS = re.compile(
    r"\b(?:user(?:'s| is| has| was| lives| works| owns| prefers| enjoys| likes)"
    r"|(?:wife|husband|spouse|daughter|son|child|parent|family|pet|dog|cat)"
    r"|(?:professor|teacher|doctor|clinic|office|employer|workplace)"
    r"|(?:hobby|hobbies|born|birthday|age|hometown|home address)"
    r"|(?:favorite (?:food|restaurant|color|music|sport|game|movie|book))"
    r"|(?:personal preference|life event|relationship|married|wedding))\b",
    re.IGNORECASE,
)


def identity_signal_count(content: str) -> int:
    return len(USER_IDENTITY_SIGNALS.findall(content))


def normalize_theme_title(title: str) -> str:
    clean = re.sub(r"\s+", " ", str(title or "").strip())
    clean = clean.strip(" -_:;,.")
    return clean[:80]


def format_theme_registry_for_prompt(themes: list[dict[str, Any]]) -> str:
    if not themes:
        return "- (none)"
    return "\n".join(
        f"- {theme['theme_id']}: {theme['title']} — {theme.get('description') or 'No description.'}"
        for theme in themes
    )


def initial_theme_title_prompt(turn_text: str) -> str:
    return (
        "Give a short (3-8 word) theme title for this conversation turn. "
        f"Return ONLY the title, nothing else.\n\n{turn_text[:500]}"
    )


def clean_theme_title_response(title: str) -> str:
    return str(title or "").strip().strip('"').strip("'")


def theme_classification_prompt(themes: list[dict[str, Any]], turn_text: str) -> str:
    theme_list = "\n".join(
        f'{i}. "{theme["metadata"].get("theme_title", "Untitled")}" — '
        f'{theme["document"][:100]}'
        for i, theme in enumerate(themes)
    )
    return (
        f"Given these existing conversation themes:\n{theme_list}\n\n"
        f"New turn:\n{turn_text[:800]}\n\n"
        f"Does this turn add detail to an existing theme, or introduce a "
        f"genuinely new topic?\n"
        f"Prefer matching existing themes — only say NEW if this is "
        f"clearly a different subject.\n\n"
        f"Respond with EXACTLY one of:\n"
        f"- EXISTING: <number>\n"
        f"- NEW: <short theme title, 3-8 words>\n"
        f"No other text."
    )


def parse_theme_classification_response(response: str, theme_count: int) -> dict[str, Any] | None:
    clean = str(response or "").strip()
    if clean.upper().startswith("EXISTING:"):
        idx = int(clean.split(":", 1)[1].strip())
        if 0 <= idx < theme_count:
            return {"action": "existing", "theme_index": idx}
        return {"action": "existing", "theme_index": theme_count - 1}
    if clean.upper().startswith("NEW:"):
        title = clean_theme_title_response(clean.split(":", 1)[1])
        return {"action": "new", "title": title or "General discussion"}
    return None


def theme_summary_prompt(current_summary: str, turn_text: str) -> str:
    if current_summary:
        return (
            f"Here is the current summary for a conversation theme:\n"
            f"---\n{current_summary}\n---\n\n"
            f"Incorporate the key details from this new turn. "
            f"Keep it concise (3-6 sentences). Preserve all important facts, "
            f"decisions, file paths, errors, and open items. Drop filler.\n\n"
            f"New turn:\n{turn_text[:800]}\n\n"
            f"Return ONLY the updated summary."
        )
    return (
        f"Summarize this conversation turn into a concise memory note "
        f"(2-4 sentences). Keep concrete facts, decisions, file paths, "
        f"errors, and open items. Drop filler.\n\n"
        f"{turn_text[:800]}\n\n"
        f"Return ONLY the summary."
    )


def filter_short_term_theme_results(results: dict[str, Any]) -> dict[str, list[Any]]:
    filtered: dict[str, list[Any]] = {"ids": [], "documents": [], "metadatas": []}
    ids = results.get("ids", [])
    documents = results.get("documents", [])
    for index, meta in enumerate(results.get("metadatas", [])):
        if (meta or {}).get("memory_type") == "short_term_theme":
            filtered["ids"].append(ids[index])
            filtered["documents"].append(documents[index])
            filtered["metadatas"].append(meta)
    return filtered


def theme_entries_from_results(results: dict[str, Any]) -> list[dict[str, Any]]:
    themes = []
    for index, doc_id in enumerate(results.get("ids", [])):
        themes.append(
            {
                "id": doc_id,
                "document": results["documents"][index],
                "metadata": results["metadatas"][index] or {},
            }
        )
    themes.sort(key=lambda theme: theme["metadata"].get("theme_index", 0))
    return themes


def short_term_theme_metadata(
    *,
    session_id: str,
    theme_title: str,
    theme_index: int,
    now_iso: str,
    expires_iso: str,
    turn_count: int = 1,
    first_turn_at: str | None = None,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "theme_title": theme_title,
        "theme_index": theme_index,
        "turn_count": turn_count,
        "first_turn_at": first_turn_at or now_iso,
        "last_updated_at": now_iso,
        "memory_type": "short_term_theme",
        "expires_at": expires_iso,
    }


def updated_short_term_theme_metadata(
    metadata: dict[str, Any],
    *,
    now_iso: str,
    expires_iso: str,
) -> dict[str, Any]:
    return {
        **metadata,
        "turn_count": metadata.get("turn_count", 1) + 1,
        "last_updated_at": now_iso,
        "expires_at": expires_iso,
    }


def oldest_theme_by_last_update(themes: list[dict[str, Any]]) -> dict[str, Any]:
    return min(
        themes,
        key=lambda theme: theme["metadata"].get("last_updated_at", ""),
    )


def archivist_prompt(
    transcript: str,
    *,
    theme_registry_text: str,
    atomic_topics: Sequence[str],
) -> str:
    return (
        "You are The Thematic Archivist for Chieh's personal AI partner (Jane). "
        "Analyze the session transcript and extract memories that are WORTH REMEMBERING.\n\n"

        "WORTH REMEMBERING — save it if any of these apply:\n"
        "1. Facts about Chieh that aren't in code or git: preferences, life context, "
        "family, work, teaching style, what he finds satisfying or annoying.\n"
        "2. Decisions and the *why* behind them — rationale doesn't survive in commit "
        "messages reliably.\n"
        "3. Commitments and open threads — what's promised, blocked, mid-flight.\n"
        "4. Architectural shape and rationale — boundaries between components, why "
        "something is split this way (NOT impl details — those are in code).\n"
        "5. Failures and the lesson — what we tried that didn't work and why.\n"
        "6. External relationships — people, services, accounts, deadlines.\n"
        "7. Identity/values shifts — anything about how we work together as partners.\n\n"

        "DROP IT — do not save:\n"
        "- Status updates and config values that already live in code or CLAUDE.md.\n"
        "- Tool output, command results, file paths used once.\n"
        "- Intermediate debugging that succeeded — the fix is in the diff.\n"
        "- Anything re-derivable from `git log`, the repo, or config files.\n"
        "- Routine task completions.\n\n"

        "TWO HEURISTICS:\n"
        "- 'Would a new agent picking up cold make the wrong call without this?' → save.\n"
        "- 'If we deleted this in 6 months and re-encountered the situation, would we "
        "re-learn it painlessly?' → painful → save.\n\n"

        "OUTPUT SHAPE — each memory is either a THEME or an ATOMIC fact.\n"
        "For THEME memories, first decide whether it belongs to an existing registered theme "
        "or needs a new theme.\n\n"
        f"Existing registered themes:\n{theme_registry_text}\n\n"
        "THEME rules:\n"
        "- Use 'existing_theme_id' when this memory extends or updates one of the registered themes.\n"
        "- Use 'new_theme_title' only when the memory clearly introduces a recurring long-lived area "
        "that does not fit any registered theme.\n"
        "- Exactly one of 'existing_theme_id' or 'new_theme_title' must be populated for kind='theme'.\n"
        "- If a fact clearly belongs to vessence/classes.chiehwu.com/waterlily, prefer the matching "
        "'Project: <name>' theme unless it truly introduces a new recurring area.\n\n"
        "ATOMIC rules:\n"
        "- Use one of these atomic topics: Decision, Commitment, Failure Lesson, External Relationship.\n"
        f"- Valid atomic topics: {', '.join(atomic_topics)}\n\n"
        "Output a single JSON list. Each object must have:\n"
        "- 'kind':    'theme' | 'atomic'\n"
        "- 'title':   concise phrase\n"
        "- 'content': comprehensive summary including context and outcome\n"
        "- 'why_kept': one sentence — which rubric criterion this hits\n"
        "- 'existing_theme_id': registered theme id or ''\n"
        "- 'new_theme_title': new recurring theme title or ''\n"
        "- 'atomic_topic': one of the atomic topics above or ''\n\n"
        "If nothing in the transcript is worth remembering, return [].\n\n"
        f"Transcript (truncated if needed):\n{transcript[-20000:]}"
    )
