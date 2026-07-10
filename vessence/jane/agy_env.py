"""Headless environment for the Antigravity (`agy`) CLI.

`agy` is Google's successor to the standalone `gemini` CLI and backs Jane's
"gemini" provider. When run interactively as Jane it reads ``~/.gemini/GEMINI.md``
— the full Jane persona that makes it read identity essays and run a memory
search on every session. That is correct for interactive use but pure noise for
headless utility/automation calls (it buries the real answer under a multi-KB
``[Librarian Context]`` preamble and adds minutes of bootstrap latency).

The fix: run headless `agy` under a minimal HOME whose ``.gemini`` directory
symlinks the real auth/config but omits ``GEMINI.md`` (and the interactive
session brain). Tokens stay shared with the real profile via the symlinks, so
auth keeps working and refreshes propagate.
"""
from __future__ import annotations

import os
from pathlib import Path

# Auth/config entries symlinked from the real ~/.gemini into the headless home.
# Deliberately excludes GEMINI.md (the persona), antigravity-cli/history/tmp
# (interactive session state), so headless calls start clean.
_LINK_ENTRIES = (
    "config",
    "google_accounts.json",
    "oauth_creds.json",
    "installation_id",
    "policies",
    "settings.json",
    "state.json",
    "trustedFolders.json",
)


def _data_home() -> Path:
    return Path(os.environ.get("VESSENCE_DATA_HOME",
                               str(Path.home() / "ambient" / "vessence-data")))


def agy_headless_home() -> str:
    """Return a HOME dir whose ~/.gemini has agy auth but no persona GEMINI.md.

    Idempotent: creates the directory and (re)links auth/config entries from the
    real ~/.gemini on each call. Cheap enough to call per-invocation.
    """
    real_gemini = Path.home() / ".gemini"
    home = _data_home() / "agy_headless_home"
    gemini = home / ".gemini"
    gemini.mkdir(parents=True, exist_ok=True)

    for entry in _LINK_ENTRIES:
        src = real_gemini / entry
        if not src.exists():
            continue
        link = gemini / entry
        try:
            if link.is_symlink():
                if os.readlink(link) == str(src):
                    continue
                link.unlink()
            elif link.exists():
                # A real file/dir is squatting the slot — leave it alone.
                continue
            link.symlink_to(src)
        except OSError:
            # Non-fatal: worst case agy re-auths or that entry is absent.
            continue

    return str(home)


def agy_env(base: dict | None = None) -> dict:
    """Return an env dict for launching headless `agy` (HOME repointed)."""
    env = dict(base if base is not None else os.environ)
    env["HOME"] = agy_headless_home()
    return env
