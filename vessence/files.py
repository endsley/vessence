"""Compatibility alias for legacy top-level imports."""
import sys

from vault_web import files as _files

sys.modules[__name__] = _files
