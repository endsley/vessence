#!/usr/bin/env python3
"""Static verifier for a clean packaged install.

This checks that the Docker packaging starts from host-mounted empty state
rather than bundling seeded Jane/Amber memories into the images.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
DOCKERFILES = [
    ROOT / "docker" / "amber" / "Dockerfile",
    ROOT / "docker" / "vault" / "Dockerfile",
    ROOT / "docker" / "jane" / "Dockerfile",
    ROOT / "docker" / "onboarding" / "Dockerfile",
    ROOT / "docker" / "chromadb" / "Dockerfile",
]


def fail(msg: str) -> None:
    raise SystemExit(msg)


def assert_no_seeded_memory() -> None:
    seeded_paths = [
        ROOT / "runtime" / "vector_db",
        ROOT / "runtime" / "data",
        ROOT / "vault",
    ]
    for path in seeded_paths:
        if not path.exists():
            continue
        if path.is_file():
            fail(f"Unexpected packaged file at {path}")
        files = [p for p in path.rglob("*") if p.is_file()]
        if files:
            fail(f"Seeded install data present in repository path {path}")


def assert_compose_uses_host_mounts() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    required = [
        "${VESSENCE_DATA_HOME:-./runtime}/vector_db:/chroma/chroma",
        "${VAULT_HOME:-./vault}:/vault",
        "${VESSENCE_DATA_HOME:-./runtime}:/data",
    ]
    for needle in required:
        if needle not in text:
            fail(f"Missing expected host-mounted runtime path in compose: {needle}")


def assert_dockerfiles_do_not_copy_runtime_data() -> None:
    bad_patterns = [
        re.compile(r"^\s*COPY\s+.*\bruntime\b", re.IGNORECASE),
        re.compile(r"^\s*COPY\s+.*\bvector_db\b", re.IGNORECASE),
        re.compile(r"^\s*COPY\s+.*\bvault\b", re.IGNORECASE),
    ]
    exceptions = {"docker/onboarding/Dockerfile"}
    for dockerfile in DOCKERFILES:
        rel = dockerfile.relative_to(ROOT).as_posix()
        text = dockerfile.read_text(encoding="utf-8").splitlines()
        for line in text:
            if rel in exceptions and "COPY onboarding/" in line:
                continue
            for pattern in bad_patterns:
                if pattern.search(line):
                    fail(f"Runtime data copied into image in {rel}: {line.strip()}")


def main() -> int:
    assert_no_seeded_memory()
    assert_compose_uses_host_mounts()
    assert_dockerfiles_do_not_copy_runtime_data()
    print(json.dumps({
        "ok": True,
        "compose": str(COMPOSE),
        "checked_dockerfiles": [str(p.relative_to(ROOT)) for p in DOCKERFILES],
        "result": "Packaged install starts from host-mounted empty state; no seeded Jane/Amber memories bundled in images."
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
