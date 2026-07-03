"""Pure Docker safety helpers for host volume mounts."""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence


def allowed_mount_bases(environ: Mapping[str, str] | None = None) -> list[str]:
    env = environ if environ is not None else os.environ
    return [
        os.path.realpath(env.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence"))),
        os.path.realpath(env.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))),
        os.path.realpath(env.get("VAULT_HOME", os.path.expanduser("~/ambient/vault"))),
    ]


def is_safe_mount(host_path: str, allowed_bases: Sequence[str]) -> bool:
    """Return True when host_path is equal to or inside an allowed base."""
    real = os.path.realpath(host_path)
    return any(
        real == base or real.startswith(base + os.sep)
        for base in allowed_bases
    )
