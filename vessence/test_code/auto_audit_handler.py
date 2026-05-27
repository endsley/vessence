import pytest
import logging
from jane_web.jane_v2.classes.read_messages.handler import handle, _ARCH_WORDS, _META_PHRASES

@pytest.mark.asyncio
async def test_behavioral_escalation_by_design():
    """
    Verify documented behavior: Reading messages is complex and should 
    always escalate to Stage 3 (Opus) by returning None.
    """
    prompt = "Show me the last 5 messages from Alice"
    result = await handle(prompt)
    assert result is None

@pytest.mark.asyncio
async def test_behavioral_arch_word_blocking():
    """
    Verify that architectural keywords trigger a 'wrong_class' return
    to prevent misclassification of system queries as 'read_messages'.
    """
    for word in _ARCH_WORDS:
        prompt = f"How does the {word} work?"
        result = await handle(prompt)
        assert result == {"wrong_class": True}

@pytest.mark.asyncio
async def test_behavioral_meta_phrase_blocking():
    """
    Verify that meta-commentary about previous replies triggers 'wrong_class'.
    """
    for phrase in _META_PHRASES:
        prompt = f"I think {phrase} was a bit too short"
        result = await handle(prompt)
        assert result == {"wrong_class": True}

@pytest.mark.asyncio
async def test_edge_case_empty_input():
    """Empty input should default to escalation (None)."""
    result = await handle("")
    assert result is None

@pytest.mark.asyncio
async def test_edge_case_none_input():
    """If prompt is None (malformed), it should raise AttributeError or be handled gracefully.
    The implementation calls .lower() on prompt, so it will raise. 
    This test documents that behavior.
    """
    with pytest.raises(AttributeError):
        await handle(None) # type: ignore

@pytest.mark.asyncio
async def test_edge_case_case_insensitivity():
    """Verify that blocking words are matched regardless of case."""
    result = await handle("Tell me about the ARCHITECTURE")
    assert result == {"wrong_class": True}

@pytest.mark.asyncio
async def test_edge_case_very_long_input():
    """Very long input should still escalate if no keywords are present."""
    long_prompt = "read " * 2000
    result = await handle(long_prompt)
    assert result is None

@pytest.mark.asyncio
async def test_integration_params_and_context_ignored():
    """
    Verify that extra context and params are accepted but do not 
    alter the escalation behavior.
    """
    context = "User is in a hurry"
    params = {"priority": "high"}
    result = await handle("read mail", context=context, params=params)
    assert result is None

def test_structural_invariant_keyword_lists():
    """
    CRITICAL: Ensure the guard lists are populated and contain strings.
    If these are emptied, the guard fails silently.
    """
    assert len(_ARCH_WORDS) > 0
    assert len(_META_PHRASES) > 0
    assert all(isinstance(w, str) for w in _ARCH_WORDS)
    assert all(isinstance(p, str) for p in _META_PHRASES)

@pytest.mark.asyncio
async def test_structural_invariant_return_values():
    """
    CRITICAL: Every path must return either None (escalate) 
    or a dict with 'wrong_class' key. 
    A handler in this system must not return an empty dict or a dict without 'text'
    UNLESS it is flagging a misclassification.
    """
    # Sample various inputs to check return types
    prompts = [
        "standard request",
        "architecture query",
        "your last message was slow",
        "",
        "read messages"
    ]
    
    for p in prompts:
        result = await handle(p)
        if result is not None:
            assert isinstance(result, dict)
            # If it returns a dict, it must be the wrong_class flag for this specific handler
            assert result.get("wrong_class") is True
            # For this specific 'always escalate' handler, it should NEVER return 'text' 
            # because local handling is explicitly disabled in the spec.
            assert "text" not in result

def test_structural_invariant_reachability():
    """
    Verify that both exit conditions (None and wrong_class) are reachable.
    """
    import asyncio
    
    # Path 1: Escalation
    r1 = asyncio.run(handle("read my inbox"))
    assert r1 is None
    
    # Path 2: Guard block
    r2 = asyncio.run(handle("explain the pipeline"))
    assert r2 == {"wrong_class": True}
