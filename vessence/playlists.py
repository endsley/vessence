"""Compatibility alias for legacy top-level imports."""
import sys

from vault_web import playlists as _playlists

sys.modules[__name__] = _playlists
