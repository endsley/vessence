from jane import config
from jane import llm_config
from llm_brain.v1 import llm_config as v1_llm_config


def test_llm_config_shims_export_librarian_model():
    assert config.LIBRARIAN_MODEL
    assert llm_config.LIBRARIAN_MODEL == config.LIBRARIAN_MODEL
    assert v1_llm_config.LIBRARIAN_MODEL == config.LIBRARIAN_MODEL


def test_llm_config_shims_preserve_local_model_aliases():
    assert llm_config.LOCAL_LLM_MODEL == config.LOCAL_LLM_MODEL
    assert llm_config.LOCAL_LLM_BASE_URL == config.OLLAMA_BASE_URL
    assert llm_config.LOCAL_LLM_MODEL_LITELLM == config.LOCAL_LLM_MODEL_LITELLM
