"""Manifest assembly for the essence builder interview."""
from __future__ import annotations

from agent_skills.essence_builder_parsing import (
    credentials_from_answer,
    extract_list_from_answer,
    extract_model_id,
    extract_quoted_strings,
    extract_role_title,
    select_permissions,
    select_shared_skills,
    select_ui_type,
    trigger_list_from_answer,
)


def manifest_from_answers(essence_name: str, answers: dict[str, str]) -> dict:
    skills_answer = answers.get("shared_skills", "")
    ui_answer = answers.get("ui_paradigm", "")
    perms_answer = answers.get("permissions_credentials", "").lower()
    caps_answer = answers.get("capabilities_declaration", "")
    model_answer = answers.get("preferred_model", "")
    interaction_answer = answers.get("interaction_patterns", "")
    triggers_answer = answers.get("triggers_automations", "")
    creds_answer = answers.get("permissions_credentials", "")
    identity_answer = answers.get("identity_personality", "")
    description = answers.get("knowledge_base", essence_name)

    return {
        "essence_name": essence_name,
        "role_title": extract_role_title(identity_answer),
        "version": "1.0",
        "author": "user",
        "description": description[:200] if len(description) > 200 else description,
        "preferred_model": {
            "model_id": extract_model_id(model_answer),
            "reasoning": model_answer[:300] if len(model_answer) > 300 else model_answer,
        },
        "permissions": select_permissions(perms_answer),
        "external_credentials": credentials_from_answer(creds_answer),
        "capabilities": {
            "provides": extract_list_from_answer(caps_answer, "provide"),
            "consumes": extract_list_from_answer(caps_answer, "consume"),
        },
        "ui": {
            "type": select_ui_type(ui_answer),
            "entry_layout": "ui/layout.json",
        },
        "shared_skills": select_shared_skills(skills_answer),
        "interaction_patterns": {
            "conversation_starters": extract_quoted_strings(interaction_answer),
            "proactive_triggers": trigger_list_from_answer(triggers_answer),
        },
    }
