# Job: Docker Build Validation Before Packaging

Status: completed
Priority: 1
Model: sonnet
Created: 2026-03-25

## Objective
Before building installer zips, run a validation step that catches Docker errors early — so we don't ship broken packages.

## What to validate
1. `docker compose config` — validates the compose file syntax and variable resolution
2. `docker compose build --dry-run` (if available) or at least verify all Dockerfile COPY sources exist
3. Verify all healthcheck commands are available in their target images (e.g., don't use curl in images that don't have it)
4. Verify all env_file paths have defaults or required: false
5. Verify all volume mount source paths exist or will be created by the installer

## Implementation
Add a `validate()` function to `build_docker_bundle.py` that runs before `build_all()`. If validation fails, abort the build and print what's wrong.

## Files Involved
- `startup_code/build_docker_bundle.py`
