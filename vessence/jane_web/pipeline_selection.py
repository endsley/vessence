"""Jane chat pipeline selection policy."""

from __future__ import annotations

import os
from collections.abc import Mapping


def should_use_v2_pipeline(environ: Mapping[str, str] = os.environ) -> bool:
    """Return False only for the explicit v1 rollback flag."""
    return environ.get("JANE_PIPELINE", "").strip().lower() != "v1"


def should_use_v3_pipeline(environ: Mapping[str, str] = os.environ) -> bool:
    """Return True only for the explicit v3 opt-in flag."""
    return environ.get("JANE_USE_V3_PIPELINE", "").strip() == "1"
