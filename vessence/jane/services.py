from google.adk.cli.service_registry import get_service_registry
from memory.v1.local_vector_memory import LocalVectorMemoryService

def local_vector_memory_factory(uri: str, **kwargs):
    return LocalVectorMemoryService(uri=uri, **kwargs)

# Register the custom memory service
get_service_registry().register_memory_service("localvector", local_vector_memory_factory)
