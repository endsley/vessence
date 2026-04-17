"""LEGACY shim — re-exports `intent_classifier/v1/gemma_router.py`.

DEPRECATED. The active classifier is `intent_classifier/v2/` and the v2
pipeline runs `qwen2.5:7b`, NOT Gemma. No active code imports from this shim
(verified via grep) — kept only in case external scripts reference it.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from intent_classifier.v1.gemma_router import *  # noqa: F401,F403
