"""Compatibility alias for legacy top-level imports."""
import sys

from vault_web import share as _share

sys.modules[__name__] = _share
