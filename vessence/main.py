"""Compatibility alias for legacy top-level imports."""
import sys

from vault_web import main as _main

sys.modules[__name__] = _main
