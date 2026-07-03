"""Memory retrieval target planning helpers."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryQueryPlan:
    use_user_memory: bool
    use_shared: bool
    use_jane_long_term: bool
    use_short_term: bool
    use_file_index: bool
    use_essence: bool


def build_memory_query_plan(
    *,
    intent: str,
    assistant_name: str,
    essence_chromadb_path: str | None = None,
    user_memory_path: str | None = None,
    path_exists: Callable[[str], bool] = os.path.exists,
) -> MemoryQueryPlan:
    use_user_memory = bool(user_memory_path and path_exists(user_memory_path))
    use_shared = not use_user_memory
    use_jane_long_term = (
        not use_user_memory
        and assistant_name.strip().lower() != "amber"
        and intent in {"project_work", "general"}
    )
    use_short_term = not use_user_memory
    use_file_index = intent == "file_lookup" and not use_user_memory
    use_essence = bool(essence_chromadb_path and path_exists(essence_chromadb_path))
    return MemoryQueryPlan(
        use_user_memory=use_user_memory,
        use_shared=use_shared,
        use_jane_long_term=use_jane_long_term,
        use_short_term=use_short_term,
        use_file_index=use_file_index,
        use_essence=use_essence,
    )
