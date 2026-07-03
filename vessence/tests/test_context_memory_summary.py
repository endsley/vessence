from context_builder.v1 import context_builder
from context_builder.v1.memory_summary import NO_RELEVANT_CONTEXT, normalize_memory_summary


def test_context_builder_uses_memory_summary_helper():
    assert context_builder._normalize_memory_summary is normalize_memory_summary


def test_normalize_memory_summary_prefers_real_summary_and_truncates():
    assert normalize_memory_summary("  memory text  ", "fallback", max_chars=6) == "memory"
    assert normalize_memory_summary(NO_RELEVANT_CONTEXT, "  fallback  ", max_chars=4) == "fall"
    assert normalize_memory_summary("", NO_RELEVANT_CONTEXT) == ""
    assert normalize_memory_summary(" \n ", " ") == ""
