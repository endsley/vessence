"""Vessence Capabilities Registry — central swap point for all versioned systems.

Each capability can be swapped between versions by changing the version string here.
All code should import through this registry rather than directly from v1/v2.

Usage:
    from capabilities import memory, brain, router, context, tts

    # These dynamically resolve to the active version's module:
    memory.build_memory_sections(query)
    brain.get_brain_adapter(name)
    router.classify_prompt(message)
    context.build_jane_context_async(...)
"""

import os
import importlib

# ─── Version Configuration ────────────────────────────────────────────────────
# Change these to swap implementations. Set via env vars or edit directly.

MEMORY_VERSION = os.environ.get("VESSENCE_MEMORY_VERSION", "v1")
BRAIN_VERSION = os.environ.get("VESSENCE_BRAIN_VERSION", "v1")
ROUTER_VERSION = os.environ.get("VESSENCE_ROUTER_VERSION", "v1")
CONTEXT_VERSION = os.environ.get("VESSENCE_CONTEXT_VERSION", "v1")
TTS_VERSION = os.environ.get("VESSENCE_TTS_VERSION", "v1")


def _load(package: str, version: str, module: str):
    """Dynamically import a versioned module."""
    full = f"{package}.{version}.{module}"
    return importlib.import_module(full)


# ─── Lazy-loaded capability modules ──────────────────────────────────────────

class _LazyModule:
    """Proxy that imports the real module on first attribute access."""
    def __init__(self, package, version, module):
        self._package = package
        self._version = version
        self._module = module
        self._real = None

    def _ensure(self):
        if self._real is None:
            self._real = _load(self._package, self._version, self._module)

    def __getattr__(self, name):
        self._ensure()
        return getattr(self._real, name)


# Primary capability modules — import these
memory_retrieval = _LazyModule("memory", MEMORY_VERSION, "memory_retrieval")
memory_writer = _LazyModule("memory", MEMORY_VERSION, "add_fact")
brain_adapters = _LazyModule("llm_brain", BRAIN_VERSION, "brain_adapters")
standing_brain = _LazyModule("llm_brain", BRAIN_VERSION, "standing_brain")
router = _LazyModule("intent_classifier", ROUTER_VERSION, "gemma_router")
context = _LazyModule("context_builder", CONTEXT_VERSION, "context_builder")
tts_config = _LazyModule("tts_engine", TTS_VERSION, "config")


def status() -> dict:
    """Return current version configuration."""
    return {
        "memory": MEMORY_VERSION,
        "brain": BRAIN_VERSION,
        "router": ROUTER_VERSION,
        "context": CONTEXT_VERSION,
        "tts": TTS_VERSION,
    }
