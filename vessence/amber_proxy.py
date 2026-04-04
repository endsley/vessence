"""Compatibility alias for legacy top-level imports."""
import sys

from vault_web import amber_proxy as _amber_proxy

sys.modules[__name__] = _amber_proxy
