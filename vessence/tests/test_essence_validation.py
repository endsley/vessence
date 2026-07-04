from agent_skills import validate_essence
from agent_skills.essence_validation import (
    REQUIRED_CAPABILITIES_FIELDS,
    REQUIRED_MANIFEST_FIELDS,
    REQUIRED_MODEL_FIELDS,
    REQUIRED_PATHS,
    REQUIRED_UI_FIELDS,
    missing_nested_field_errors,
    validate_manifest,
)


def minimal_manifest() -> dict:
    return {
        "essence_name": "demo",
        "role_title": "Demo",
        "version": "1.0",
        "author": "Jane",
        "description": "Demo essence",
        "preferred_model": {"model_id": "gpt", "reasoning": "low"},
        "permissions": [],
        "capabilities": {"provides": [], "consumes": []},
        "ui": {"type": "none"},
        "shared_skills": [],
    }


def test_validate_essence_reexports_schema_constants_and_validator():
    assert validate_essence.REQUIRED_MANIFEST_FIELDS is REQUIRED_MANIFEST_FIELDS
    assert validate_essence.REQUIRED_MODEL_FIELDS is REQUIRED_MODEL_FIELDS
    assert validate_essence.REQUIRED_CAPABILITIES_FIELDS is REQUIRED_CAPABILITIES_FIELDS
    assert validate_essence.REQUIRED_UI_FIELDS is REQUIRED_UI_FIELDS
    assert validate_essence.REQUIRED_PATHS is REQUIRED_PATHS
    assert validate_essence.validate_manifest is validate_manifest


def test_validate_manifest_accepts_minimal_valid_manifest():
    assert validate_manifest(minimal_manifest()) == []


def test_missing_nested_field_errors_preserves_message_shape_and_order():
    assert missing_nested_field_errors("preferred_model", {"model_id": "gpt"}, ["model_id", "reasoning"]) == [
        "preferred_model missing field: 'reasoning'",
    ]


def test_validate_manifest_reports_missing_top_level_fields_in_order():
    assert validate_manifest({}) == [
        "Missing required field: 'essence_name'",
        "Missing required field: 'role_title'",
        "Missing required field: 'version'",
        "Missing required field: 'author'",
        "Missing required field: 'description'",
        "Missing required field: 'preferred_model'",
        "Missing required field: 'permissions'",
        "Missing required field: 'capabilities'",
        "Missing required field: 'ui'",
        "Missing required field: 'shared_skills'",
    ]


def test_validate_manifest_reports_nested_missing_fields_and_type_errors():
    manifest = minimal_manifest()
    manifest["preferred_model"] = {"model_id": "gpt"}
    manifest["capabilities"] = {"provides": "tools"}
    manifest["ui"] = {}
    manifest["permissions"] = "all"
    manifest["shared_skills"] = "memory"

    assert validate_manifest(manifest) == [
        "preferred_model missing field: 'reasoning'",
        "capabilities.provides must be an array",
        "capabilities missing field: 'consumes'",
        "ui missing field: 'type'",
        "'permissions' must be an array",
        "'shared_skills' must be an array",
    ]


def test_validate_manifest_reports_object_type_errors_without_nested_checks():
    manifest = minimal_manifest()
    manifest["preferred_model"] = "gpt"
    manifest["capabilities"] = []
    manifest["ui"] = "card"

    assert validate_manifest(manifest) == [
        "'preferred_model' must be an object",
        "'capabilities' must be an object",
        "'ui' must be an object",
    ]
