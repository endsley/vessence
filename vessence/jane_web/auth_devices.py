"""Trusted-device resolution helpers for auth routes."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def trusted_device_id_for_fingerprint(
    fingerprint: str,
    user_id: str,
    *,
    register_trusted_device: Callable[[str, str], str],
    get_trusted_device_by_fingerprint: Callable[[str], Mapping[str, Any] | None],
    is_device_trusted: Callable[[str], bool] | None = None,
) -> str:
    if is_device_trusted is not None and not is_device_trusted(fingerprint):
        return register_trusted_device(fingerprint, user_id)
    trusted_row = get_trusted_device_by_fingerprint(fingerprint)
    return trusted_row["id"] if trusted_row else register_trusted_device(fingerprint, user_id)
