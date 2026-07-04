"""User identity normalization helpers for Jane web."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from vault_web.auth import default_user_id as auth_default_user_id
from vault_web.auth import user_id_from_email


def env_csv_values(environ: Mapping[str, str], name: str) -> list[str]:
    return [value.strip() for value in environ.get(name, "").split(",") if value.strip()]


def default_user_id(environ: Mapping[str, str] = os.environ) -> str:
    allowed = env_csv_values(environ, "ALLOWED_GOOGLE_EMAILS")
    if allowed:
        return allowed[0]
    user_name = environ.get("USER_NAME", "").strip().lower()
    return "_".join(user_name.split()) if user_name else "user"


def identity_variants(
    identifier: str | None,
    *,
    user_id_from_email_fn: Callable[[str], str] = user_id_from_email,
) -> set[str]:
    value = (identifier or "").strip().lower()
    if not value:
        return set()
    variants = {value, "_".join(value.replace("@", "_at_").replace(".", "_").split())}
    if "@" in value:
        variants.add(user_id_from_email_fn(value))
    return variants


def configured_admin_variants(
    environ: Mapping[str, str] = os.environ,
    *,
    auth_default_user_id_fn: Callable[[], str] = auth_default_user_id,
    user_id_from_email_fn: Callable[[str], str] = user_id_from_email,
) -> set[str]:
    configured = []
    for env_name in ("VESSENCE_ADMIN_USERS", "ADMIN_EMAILS"):
        configured.extend(env_csv_values(environ, env_name))
    allowed = env_csv_values(environ, "ALLOWED_GOOGLE_EMAILS")
    if not configured and allowed:
        configured.append(allowed[0])
    if not configured:
        configured.append(auth_default_user_id_fn())

    variants: set[str] = set()
    for item in configured:
        variants.update(identity_variants(item, user_id_from_email_fn=user_id_from_email_fn))
    return variants
