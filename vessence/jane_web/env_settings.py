"""Helpers for updating Jane web environment settings files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import MutableMapping


class EnvFileSettings:
    def __init__(self, env_path: str | Path, *, environ: MutableMapping[str, str] | None = None):
        self.env_path = Path(env_path)
        self.environ = environ if environ is not None else os.environ

    def write_var(self, key: str, value: str) -> None:
        lines = self.env_path.read_text().splitlines() if self.env_path.exists() else []
        found = False
        updated = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                existing_key = stripped.split("=", 1)[0].strip()
                if existing_key == key:
                    updated.append(f"{key}={value}")
                    found = True
                    continue
            updated.append(line)
        if not found:
            updated.append(f"{key}={value}")
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text("\n".join(updated) + "\n")
        self.environ[key] = value

    def add_allowed_google_email(self, email: str) -> bool:
        normalized = (email or "").strip().lower()
        current = self._allowed_google_emails()
        if normalized in current:
            return False
        current.append(normalized)
        self.write_var("ALLOWED_GOOGLE_EMAILS", ",".join(current))
        return True

    def remove_allowed_google_email(self, email: str) -> bool:
        normalized = (email or "").strip().lower()
        current = self._allowed_google_emails()
        if normalized not in current:
            return False
        current.remove(normalized)
        self.write_var("ALLOWED_GOOGLE_EMAILS", ",".join(current))
        return True

    def _allowed_google_emails(self) -> list[str]:
        return [
            email.strip().lower()
            for email in self.environ.get("ALLOWED_GOOGLE_EMAILS", "").split(",")
            if email.strip()
        ]
