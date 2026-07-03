"""Known-junk classification rules for the memory janitor."""

from __future__ import annotations

from typing import Callable


KNOWN_JUNK_TOPICS = {"prompt_queue", "job_queue", "test"}
KNOWN_JUNK_PREFIXES = (
    "Prompt queue item ",
    "Job #",
    "Prompt List Item ",
)
STALE_AMBER_RUNTIME_PHRASES = (
    "amber should periodically provide brief status updates",
    "amber uses the vault to store physical files",
    "amber is a universal runtime",
    "amber is a universal app shell",
    "amber is a stateless vessel",
    "branding: amber keeps her name",
    "rent means a creator hosts amber + essence",
    "amber not migrated",
    "amber vault login page",
    "amber's vault login page",
)
STALE_AMBER_KEEP_PHRASES = (
    "amber's adk runtime is retired",
    "amber runtime is retired",
    "amber/ is absent",
    "single unified identity",
    "consolidated into a single unified identity",
    "stale docs",
    "historical",
    "retired",
)
STALE_DISCORD_PHRASES = (
    "in discord, amber should periodically",
    "keep the discord bridge running as fallback",
    "discord bridge running as fallback",
)
STALE_DOCKER_PHRASES = (
    "docker-compose.yml",
    "traefik.http.routers",
    "traefik label",
    "docker installer",
    "docker onboarding",
)
STALE_DOCKER_KEEP_PHRASES = (
    "no longer uses docker",
    "no longer uses a docker",
    "does not use docker",
)
LOW_VALUE_CLASSES_DEPLOY_TOPICS = {
    "chieh_class_v2",
    "teaching_app",
    "teaching_app_v2",
    "classes.chiehwu.com",
    "classes_chiehwu",
    "classes-site",
    "education_project",
    "projects",
}
LOW_VALUE_CLASSES_KEEP_SUBTOPICS = {
    "deploy-preferences",
    "deploy_preferences",
    "production_deploy",
    "production deploy",
    "state",
    "cloud_sql",
    "cloud sql",
}
LOW_VALUE_CLASSES_DEPLOY_PHRASES = (
    "cloud run revision",
    "deployed revision",
    "deployed to cloud run",
    "gcloud run deploy",
)


def contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def is_known_junk_phrase(text: str, topic: str) -> bool:
    low = (text or "").strip().lower()
    if low == "delete me" or low.startswith("delete me\n"):
        return True
    if "completed autonomously on" not in low:
        return False
    return (
        topic in KNOWN_JUNK_TOPICS
        or any((text or "").startswith(prefix) for prefix in KNOWN_JUNK_PREFIXES)
        or low.startswith("completed autonomously on")
    )


def meta_label(meta: dict | None, key: str) -> str:
    return str((meta or {}).get(key) or "").strip().lower()


def is_stale_amber_runtime_memory(text: str) -> bool:
    if "amber" not in text:
        return False
    if contains_any(text, STALE_AMBER_KEEP_PHRASES):
        return False
    return contains_any(text, STALE_AMBER_RUNTIME_PHRASES)


def is_stale_discord_memory(text: str) -> bool:
    if "discord" not in text:
        return False
    return contains_any(text, STALE_DISCORD_PHRASES)


def is_stale_vessence_docker_memory(
    text: str,
    topic: str,
    *,
    vessence_docker_compose_missing: Callable[[], bool],
) -> bool:
    if not contains_any(text, STALE_DOCKER_PHRASES):
        return False
    if contains_any(text, STALE_DOCKER_KEEP_PHRASES):
        return False
    if topic in LOW_VALUE_CLASSES_DEPLOY_TOPICS:
        return False
    if not (
        "vessence" in text
        or "amber" in text
        or "jane" in text
        or topic in {"vessence", "project_vessence", "project: vessence", "system"}
    ):
        return False
    return vessence_docker_compose_missing()


def is_stale_waterlily_nationalgrid_memory(
    topic: str,
    subtopic: str,
    text: str,
    *,
    codex_skill_exists: Callable[[str], bool],
) -> bool:
    if topic != "waterlily" or subtopic not in {"nationalgrid", "national_grid", "nationalgrid-bills"}:
        return False
    if "no waterlily nationalgrid bill-extraction implementation" not in text:
        return False
    return codex_skill_exists("waterlily-nationalgrid-bills")


def is_superseded_acubliss_planning_memory(
    topic: str,
    subtopic: str,
    text: str,
    *,
    codex_skill_exists: Callable[[str], bool],
) -> bool:
    if topic != "waterlily" or subtopic not in {"acubliss-reports", "acubliss", "reports"}:
        return False
    if not codex_skill_exists("waterlily-appointments-report"):
        return False
    return contains_any(text, (
        "future skill should",
        "extractor should choose",
        "download button generates",
    ))


def is_low_value_classes_deploy_snapshot(topic: str, subtopic: str, text: str) -> bool:
    if subtopic in LOW_VALUE_CLASSES_KEEP_SUBTOPICS:
        return False
    if topic not in LOW_VALUE_CLASSES_DEPLOY_TOPICS and "classes.chiehwu.com" not in text:
        return False
    return contains_any(text, LOW_VALUE_CLASSES_DEPLOY_PHRASES)


def classify_known_junk(
    collection_name: str,
    doc: str,
    meta: dict | None,
    *,
    user_collection_name: str,
    long_term_collection_name: str,
    codex_skill_exists: Callable[[str], bool],
    vessence_docker_compose_missing: Callable[[], bool],
) -> str | None:
    """Return a deletion reason for known junk patterns, else None."""
    meta = meta or {}
    text = (doc or "").strip()
    low = text.lower()
    topic = str(meta.get("topic") or "")
    topic_low = topic.strip().lower()
    subtopic_low = meta_label(meta, "subtopic")

    if collection_name == user_collection_name:
        if topic in KNOWN_JUNK_TOPICS:
            return f"Known junk topic `{topic}`"
        if any(text.startswith(prefix) for prefix in KNOWN_JUNK_PREFIXES):
            return "Known queue/prompt transcript artifact"
        if is_known_junk_phrase(text, topic):
            return "Known test or queue execution artifact"
        if topic == "system" and (
            low.startswith("refactor test")
            or low.startswith("shim cli test")
            or low.startswith("e2e test")
        ):
            return "System test artifact"
        if "the ai assistant's name is amber" in low:
            return "Outdated Amber identity memory"
        if topic == "ds3000_lecture_notes":
            return "Superseded DS3000 lecture-note anchor; ds3000_lecture_notes_bge is canonical"
        if is_stale_amber_runtime_memory(low):
            return "Outdated Amber-era runtime memory"
        if is_stale_discord_memory(low):
            return "Outdated Discord bridge/status memory"
        if is_stale_vessence_docker_memory(
            low,
            topic_low,
            vessence_docker_compose_missing=vessence_docker_compose_missing,
        ):
            return "Outdated Vessence Docker/Traefik memory"
        if is_stale_waterlily_nationalgrid_memory(
            topic_low,
            subtopic_low,
            low,
            codex_skill_exists=codex_skill_exists,
        ):
            return "Superseded Waterlily National Grid implementation gap"
        if is_superseded_acubliss_planning_memory(
            topic_low,
            subtopic_low,
            low,
            codex_skill_exists=codex_skill_exists,
        ):
            return "Superseded AcuBliss extraction planning memory"
        if is_low_value_classes_deploy_snapshot(topic_low, subtopic_low, low):
            return "Low-value classes.chiehwu.com deploy revision snapshot"
        return None

    if collection_name == long_term_collection_name:
        if not meta.get("topic"):
            return "Untyped archived transcript fragment with no topic metadata"
        if low.startswith("theme: article-sharing workflow") and "deferred follow-up feature request" in low:
            return "Deferred feature-request snapshot"
        if is_stale_amber_runtime_memory(low):
            return "Outdated Amber-era runtime memory"
        if is_stale_discord_memory(low):
            return "Outdated Discord bridge/status memory"
        if is_stale_vessence_docker_memory(
            low,
            topic_low,
            vessence_docker_compose_missing=vessence_docker_compose_missing,
        ):
            return "Outdated Vessence Docker/Traefik memory"
        if is_low_value_classes_deploy_snapshot(topic_low, subtopic_low, low):
            return "Low-value classes.chiehwu.com deploy revision snapshot"
        return None

    return None
