"""Vessence Memory System — pluggable backend.

Set MEMORY_BACKEND to "v1" or "v2" to swap implementations.
v1 = original ChromaDB-based system (production)
v2 = redesigned system with separated collections (in development)
"""

import os

MEMORY_BACKEND = os.environ.get("MEMORY_BACKEND", "v1")
