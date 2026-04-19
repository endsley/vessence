"""Module-level Stage 0 singleton — loaded once, reused across requests."""

from pathlib import Path
from intent_classifier.v2.stage0 import Stage0ExactMatch

_LOOKUP = Path(__file__).parent.parent / "intent_classifier/v2/stage0_lookup.json"

stage0 = Stage0ExactMatch(_LOOKUP)
