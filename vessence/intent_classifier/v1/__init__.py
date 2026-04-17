"""Intent Classifier v1 — LEGACY.

DEPRECATED. Active classifier is `intent_classifier/v2/` (and the
`jane_web/jane_v2/` pipeline). The "gemma_*" filenames in this package are
historical — the running model is now `qwen2.5:7b` (see
`vessence-data/.env: JANE_STAGE2_MODEL`). v1 is only kept because
`jane_web/jane_proxy.py` still imports from it for a fallback code path.
Do not infer the active model from these filenames.
"""
