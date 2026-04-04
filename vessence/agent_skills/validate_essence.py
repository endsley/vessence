#!/usr/bin/env python3
"""
validate_essence.py — Validates an essence folder against the Vessence manifest schema.

Usage:
    python validate_essence.py /path/to/essence/folder

Exit codes:
    0 — valid essence
    1 — validation failed
"""

import json
import os
import sys


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

    # Check top-level required fields
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            errors.append(f"Missing required field: '{field}'")

    # Validate preferred_model sub-fields
    model = manifest.get("preferred_model")
    if isinstance(model, dict):
        for field in REQUIRED_MODEL_FIELDS:
            if field not in model:
                errors.append(f"preferred_model missing field: '{field}'")
    elif model is not None:
        errors.append("'preferred_model' must be an object")

    # Validate capabilities sub-fields
    caps = manifest.get("capabilities")
    if isinstance(caps, dict):
        for field in REQUIRED_CAPABILITIES_FIELDS:
            if field not in caps:
                errors.append(f"capabilities missing field: '{field}'")
            elif not isinstance(caps[field], list):
                errors.append(f"capabilities.{field} must be an array")
    elif caps is not None:
        errors.append("'capabilities' must be an object")

    # Validate ui sub-fields
    ui = manifest.get("ui")
    if isinstance(ui, dict):
        for field in REQUIRED_UI_FIELDS:
            if field not in ui:
                errors.append(f"ui missing field: '{field}'")
    elif ui is not None:
        errors.append("'ui' must be an object")

    # Validate permissions is a list
    perms = manifest.get("permissions")
    if perms is not None and not isinstance(perms, list):
        errors.append("'permissions' must be an array")

    # Validate shared_skills is a list
    skills = manifest.get("shared_skills")
    if skills is not None and not isinstance(skills, list):
        errors.append("'shared_skills' must be an array")

    return errors


def validate_folder_structure(essence_path: str) -> list[str]:
    """Validate that the essence folder contains required files and directories."""
    errors: list[str] = []

    if not os.path.isdir(essence_path):
        errors.append(f"Essence path is not a directory: {essence_path}")
        return errors

    manifest_path = os.path.join(essence_path, "manifest.json")
    if not os.path.isfile(manifest_path):
        errors.append("Missing manifest.json")

    for rel_path, kind in REQUIRED_PATHS:
        full = os.path.join(essence_path, rel_path)
        if kind == "file" and not os.path.isfile(full):
            errors.append(f"Missing required file: {rel_path}")
        elif kind == "dir" and not os.path.isdir(full):
            errors.append(f"Missing required directory: {rel_path}/")

    return errors


def validate_essence(essence_path: str) -> tuple[bool, list[str]]:
    """
    Full validation of an essence folder.
    Returns (is_valid, list_of_errors).
    """
    errors: list[str] = []

    # Folder structure
    errors.extend(validate_folder_structure(essence_path))

    # Manifest content
    manifest_path = os.path.join(essence_path, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"manifest.json is not valid JSON: {e}")
            return False, errors

        errors.extend(validate_manifest(manifest))

    is_valid = len(errors) == 0
    return is_valid, errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python validate_essence.py /path/to/essence/folder", file=sys.stderr)
        return 1

    essence_path = os.path.abspath(sys.argv[1])
    is_valid, errors = validate_essence(essence_path)

    if is_valid:
        print(f"OK: '{essence_path}' is a valid essence.")
        return 0
    else:
        print(f"ERRORS in '{essence_path}':")
        for err in errors:
            print(f"  - {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
