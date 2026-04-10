"""Compatibility shim — moved to context_builder/v1/context_builder.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from context_builder.v1.context_builder import *  # noqa: F401,F403
# import * skips _-prefixed names; re-export them explicitly for dependents
from context_builder.v1.context_builder import (  # noqa: F401
    _classify_prompt_profile,
    _is_task_related,
    _load_code_map,
    _load_personal_facts,
    _select_user_background,
    _read_json_summary,
)
