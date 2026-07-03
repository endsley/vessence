"""Pure manifest schema validation for Vessence essences."""

from __future__ import annotations


REQUIRED_MANIFEST_FIELDS = [
    "essence_name",
    "role_title",
    "version",
    "author",
    "description",
    "preferred_model",
    "permissions",
    "capabilities",
    "ui",
    "shared_skills",
]

REQUIRED_MODEL_FIELDS = ["model_id", "reasoning"]
REQUIRED_CAPABILITIES_FIELDS = ["provides", "consumes"]
REQUIRED_UI_FIELDS = ["type"]

REQUIRED_PATHS = [
    ("personality.md", "file"),
    ("knowledge", "dir"),
    ("functions", "dir"),
    ("ui", "dir"),
]


def validate_manifest(manifest: dict) -> list[str]:
    """Validate manifest.json content. Returns a list of error strings."""
    errors: list[str] = []

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            errors.append(f"Missing required field: '{field}'")

    model = manifest.get("preferred_model")
    if isinstance(model, dict):
        for field in REQUIRED_MODEL_FIELDS:
            if field not in model:
                errors.append(f"preferred_model missing field: '{field}'")
    elif model is not None:
        errors.append("'preferred_model' must be an object")

    caps = manifest.get("capabilities")
    if isinstance(caps, dict):
        for field in REQUIRED_CAPABILITIES_FIELDS:
            if field not in caps:
                errors.append(f"capabilities missing field: '{field}'")
            elif not isinstance(caps[field], list):
                errors.append(f"capabilities.{field} must be an array")
    elif caps is not None:
        errors.append("'capabilities' must be an object")

    ui = manifest.get("ui")
    if isinstance(ui, dict):
        for field in REQUIRED_UI_FIELDS:
            if field not in ui:
                errors.append(f"ui missing field: '{field}'")
    elif ui is not None:
        errors.append("'ui' must be an object")

    perms = manifest.get("permissions")
    if perms is not None and not isinstance(perms, list):
        errors.append("'permissions' must be an array")

    skills = manifest.get("shared_skills")
    if skills is not None and not isinstance(skills, list):
        errors.append("'shared_skills' must be an array")

    return errors
