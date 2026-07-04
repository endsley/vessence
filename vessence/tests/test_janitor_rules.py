from memory.v1.janitor_rules import (
    _classify_long_term_junk,
    _classify_user_memory_junk,
    classify_known_junk,
    is_low_value_classes_deploy_snapshot,
    is_stale_vessence_docker_memory,
    meta_label,
)


USER = "user_memories"
LONG = "long_term_knowledge"


def classify(collection: str, doc: str, meta: dict | None = None, *, skill_names=(), docker_missing=False):
    return classify_known_junk(
        collection,
        doc,
        meta,
        user_collection_name=USER,
        long_term_collection_name=LONG,
        codex_skill_exists=lambda name: name in skill_names,
        vessence_docker_compose_missing=lambda: docker_missing,
    )


def test_meta_label_normalizes_missing_values():
    assert meta_label({"subtopic": " Deploy "}, "subtopic") == "deploy"
    assert meta_label({}, "subtopic") == ""


def test_classify_user_memory_known_junk_reasons():
    assert classify(USER, "anything", {"topic": "prompt_queue"}) == "Known junk topic `prompt_queue`"
    assert classify(USER, "Prompt queue item 1 completed", {"topic": "other"}) == (
        "Known queue/prompt transcript artifact"
    )
    assert classify(USER, "Completed autonomously on 2026-07-02", {"topic": "notes"}) == (
        "Known test or queue execution artifact"
    )
    assert classify(USER, "Refactor test passed", {"topic": "system"}) == "System test artifact"


def test_classify_user_memory_stale_runtime_and_superseded_skills():
    assert classify(USER, "The AI assistant's name is Amber.", {"topic": "identity"}) == (
        "Outdated Amber identity memory"
    )
    assert classify(USER, "Amber is a universal runtime.", {"topic": "system"}) == (
        "Outdated Amber-era runtime memory"
    )
    assert classify(
        USER,
        "No Waterlily NationalGrid bill-extraction implementation exists.",
        {"topic": "waterlily", "subtopic": "nationalgrid"},
        skill_names={"waterlily-nationalgrid-bills"},
    ) == "Superseded Waterlily National Grid implementation gap"
    assert classify(
        USER,
        "Future skill should choose the AcuBliss extractor.",
        {"topic": "waterlily", "subtopic": "acubliss"},
        skill_names={"waterlily-appointments-report"},
    ) == "Superseded AcuBliss extraction planning memory"


def test_user_memory_junk_helper_returns_none_for_nonmatching_memory():
    assert _classify_user_memory_junk(
        "Keep this useful fact",
        "keep this useful fact",
        "project",
        "project",
        "",
        codex_skill_exists=lambda _name: False,
        vessence_docker_compose_missing=lambda: False,
    ) is None


def test_classify_long_term_reasons():
    assert classify(LONG, "archived transcript", {}) == (
        "Untyped archived transcript fragment with no topic metadata"
    )
    assert classify(
        LONG,
        "Theme: article-sharing workflow deferred follow-up feature request",
        {"topic": "Project: vessence"},
    ) == "Deferred feature-request snapshot"


def test_long_term_junk_helper_keeps_typed_nonmatching_memory():
    assert _classify_long_term_junk(
        "keep this useful archive",
        {"topic": "project"},
        "project",
        "",
        vessence_docker_compose_missing=lambda: False,
    ) is None


def test_docker_and_classes_rules_keep_existing_guards():
    assert is_stale_vessence_docker_memory(
        "jane docker-compose.yml traefik label",
        "system",
        vessence_docker_compose_missing=lambda: True,
    )
    assert not is_stale_vessence_docker_memory(
        "classes.chiehwu.com docker-compose.yml",
        "classes.chiehwu.com",
        vessence_docker_compose_missing=lambda: True,
    )
    assert is_low_value_classes_deploy_snapshot(
        "classes.chiehwu.com",
        "",
        "deployed revision on cloud run revision abc",
    )
    assert not is_low_value_classes_deploy_snapshot(
        "classes.chiehwu.com",
        "production_deploy",
        "deployed revision on cloud run revision abc",
    )
