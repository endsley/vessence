"""Compatibility alias for legacy top-level imports."""
import sys

from vault_web import oauth as _oauth

sys.modules[__name__] = _oauth
