# Root-level services.py — loaded by ADK on startup to register custom service schemes.
# ADK looks for this file at the agents_dir root (services.py at VESSENCE_HOME).

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.adk.cli.service_registry import get_service_registry
from memory.v1.local_vector_memory import LocalVectorMemoryService


def local_vector_memory_factory(uri: str, **kwargs):
    return LocalVectorMemoryService(uri=uri, **kwargs)


get_service_registry().register_memory_service("localvector", local_vector_memory_factory)
