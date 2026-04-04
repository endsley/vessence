"""Compatibility alias for legacy top-level imports."""
import sys

from vault_web import database as _database

sys.modules[__name__] = _database
