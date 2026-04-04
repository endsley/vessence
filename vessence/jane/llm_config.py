# llm_config.py — Backward-compatibility shim.
# All values now live in config.py. Import from there directly in new code.
from jane.config import (
    LOCAL_LLM_MODEL,
    OLLAMA_BASE_URL      as LOCAL_LLM_BASE_URL,
    LOCAL_LLM_MODEL_LITELLM,
    LIBRARIAN_MODEL,
)
