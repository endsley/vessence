# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

from google.adk.cli.service_registry import get_service_registry
from .local_vector_memory import LocalVectorMemoryService

def local_vector_memory_factory(uri: str, **kwargs):
    return LocalVectorMemoryService(uri=uri, **kwargs)

# Register the custom memory service
get_service_registry().register_memory_service("localvector", local_vector_memory_factory)
