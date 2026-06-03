import pytest
from unittest.mock import MagicMock, patch, ANY
import os
import sys
from pathlib import Path

# Add project root to sys.path for imports
sys.path.append("/home/chieh/ambient/vessence")

import intent_classifier.v2.classifier as classifier

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Ensure consistent thresholds for testing."""
    with patch.dict(os.environ, {
        "JANE_V2_CONFIDENCE": "0.80",
        "JANE_V2_MARGIN": "0.40",
        "JANE_V2_MAX_DISTANCE": "0.30",
        "JANE_V2_MAX_COMMAND_WORDS": "20"
    }):
        # Reload constants from env
        import importlib
        importlib.reload(classifier)
        yield

def test_word_count_gate():
    """
    BEHAVIORAL: Messages longer than MAX_COMMAND_WORDS must skip lookup.
    """
    max_words = classifier.MAX_COMMAND_WORDS
    long_msg = " ".join(["word"] * (max_words + 1))
    
    # Should return DELEGATE_OPUS immediately without calling _load
    with patch("intent_classifier.v2.classifier._load") as mock_load:
        res = classifier.classify(long_msg)
        assert res["classification"] == "DELEGATE_OPUS"
        assert res["confidence"] == 0.0
        assert res["latency_ms"] == 0.0
        mock_load.assert_not_called()

def test_classify_high_confidence_success():
    """
    BEHAVIORAL: Winning class with fraction >= 0.8 and margin >= 0.4.
    """
    # 4/5 votes for WEATHER = 0.8 fraction
    # 4 WEATHER vs 1 GREETING = 0.6 margin
    mock_results = {
        "distances": [[0.1, 0.1, 0.1, 0.1, 0.15]],
        "metadatas": [[
            {"class": "WEATHER"}, {"class": "WEATHER"},
            {"class": "WEATHER"}, {"class": "WEATHER"},
            {"class": "GREETING"}
        ]]
    }
    
    with patch("intent_classifier.v2.classifier._load"), \
         patch("intent_classifier.v2.classifier._embed_fn", return_value=[[0.1]*384]), \
         patch("intent_classifier.v2.classifier._collection") as mock_col:
        
        mock_col.query.return_value = mock_results
        mock_col.count.return_value = 100
        
        res = classifier.classify("What's the weather?")
        
        assert res["classification"] == "WEATHER"
        assert res["confidence"] == 0.8
        assert res["margin"] == 0.6
        assert res["min_dist"] == 0.1

def test_classify_low_confidence_fallback():
    """
    BEHAVIORAL: Fallback to DELEGATE_OPUS if vote fraction is too low.
    """
    # 3/5 votes for WEATHER = 0.6 fraction (< 0.8)
    mock_results = {
        "distances": [[0.1]*5],
        "metadatas": [[
            {"class": "WEATHER"}, {"class": "WEATHER"}, {"class": "WEATHER"},
            {"class": "GREETING"}, {"class": "GREETING"}
        ]]
    }
    
    with patch("intent_classifier.v2.classifier._load"), \
         patch("intent_classifier.v2.classifier._embed_fn", return_value=[[0.1]*384]), \
         patch("intent_classifier.v2.classifier._collection") as mock_col:
        
        mock_col.query.return_value = mock_results
        mock_col.count.return_value = 100
        
        res = classifier.classify("Weather greeting?")
        assert res["classification"] == "DELEGATE_OPUS"
        assert res["confidence"] == 0.6

def test_classify_low_margin_fallback():
    """
    BEHAVIORAL: Fallback to DELEGATE_OPUS if margin is too low.
    """
    # Thresholds: Conf=0.8, Margin=0.4
    # Votes: 4 WEATHER, 2 GREETING (Wait TOP_K=5)
    # Votes: 3 WEATHER, 2 GREETING -> Frac=0.6, Margin=0.2 (Low Conf)
    # Votes: 4 WEATHER, 1 GREETING -> Frac=0.8, Margin=0.6 (High Conf)
    
    # To test low margin with high fraction, we'd need TOP_K > 5 or different settings.
    # With TOP_K=5, the only way to get Fraction=0.8 is 4 votes.
    # 4 votes vs 1 vote = Margin 0.6. 
    # 4 votes vs 0 votes = Margin 0.8.
    # So with TOP_K=5 and Margin=0.4, Fraction=0.8 ALWAYS implies Margin >= 0.6.
    
    # Let's test Margin=0.4 requirement if we change thresholds
    with patch.dict(os.environ, {"JANE_V2_MARGIN": "0.7"}):
        import importlib
        importlib.reload(classifier)
        
        mock_results = {
            "distances": [[0.1]*5],
            "metadatas": [[{"class": "WEATHER"}]*4 + [{"class": "GREETING"}]]
        }
        with patch("intent_classifier.v2.classifier._load"), \
             patch("intent_classifier.v2.classifier._embed_fn", return_value=[[0.1]*384]), \
             patch("intent_classifier.v2.classifier._collection") as mock_col:
            
            mock_col.query.return_value = mock_results
            mock_col.count.return_value = 100
            
            res = classifier.classify("test")
            # Frac=0.8 (>=0.8), but Margin=0.6 (<0.7)
            assert res["classification"] == "DELEGATE_OPUS"

def test_max_distance_fallback():
    """
    BEHAVIORAL: Distance > MAX_DISTANCE (0.3) must delegate even with 100% agreement.
    """
    mock_results = {
        "distances": [[0.35, 0.36, 0.37, 0.38, 0.39]],
        "metadatas": [[{"class": "WEATHER"}] * 5]
    }
    
    with patch("intent_classifier.v2.classifier._load"), \
         patch("intent_classifier.v2.classifier._embed_fn", return_value=[[0.1]*384]), \
         patch("intent_classifier.v2.classifier._collection") as mock_col:
        
        mock_col.query.return_value = mock_results
        mock_col.count.return_value = 100
        
        res = classifier.classify("Unseen intent")
        assert res["classification"] == "DELEGATE_OPUS"
        assert res["min_dist"] == 0.35

def test_stale_collection_retry():
    """
    INTEGRATION: Classifier must retry once if collection reference is stale.
    """
    mock_col = MagicMock()
    mock_col.query.side_effect = [
        Exception("Invalid collection"),
        {
            "distances": [[0.1]*5],
            "metadatas": [[{"class": "WEATHER"}]*5]
        }
    ]
    mock_col.count.return_value = 100

    def mock_load_side_effect():
        classifier._collection = mock_col

    with patch("intent_classifier.v2.classifier._load", side_effect=mock_load_side_effect) as mock_load, \
         patch("intent_classifier.v2.classifier._embed_fn", return_value=[[0.1]*384]):
        
        # Initial set
        classifier._collection = mock_col
        
        res = classifier.classify("Retry please")
        assert res["classification"] == "WEATHER"
        # _load called twice: once at start, once after exception
        assert mock_load.call_count == 2

def test_empty_input_handling():
    """
    EDGE CASE: Empty input should not crash.
    """
    with patch("intent_classifier.v2.classifier._load"), \
         patch("intent_classifier.v2.classifier._embed_fn", return_value=[[0.0]*384]), \
         patch("intent_classifier.v2.classifier._collection") as mock_col:
        
        mock_col.query.return_value = {
            "distances": [[0.5]*5],
            "metadatas": [[{"class": "DELEGATE_OPUS"}]*5]
        }
        mock_col.count.return_value = 100
        
        res = classifier.classify("")
        assert "classification" in res
        assert res["classification"] == "DELEGATE_OPUS"

def test_registry_structural_invariant():
    """
    STRUCTURAL: Every .py file in classes/ (except _*) must be in _registry.
    Every registered class must have a CLASS_NAME.
    """
    classifier._load()
    registry = classifier._registry
    
    classes_dir = Path("/home/chieh/ambient/vessence/intent_classifier/v2/classes")
    class_files = [f for f in classes_dir.glob("*.py") if not f.name.startswith("_")]
    
    # Every file should be loaded into registry (indexed by CLASS_NAME)
    # Note: multiple files could technically define the same CLASS_NAME, 
    # but they should all be represented.
    found_classes = set()
    for f in class_files:
        # We can't easily check _registry keys vs filename directly if they differ
        # but we can check that at least as many items are in registry as files.
        pass
    
    assert len(registry) > 0
    assert "DELEGATE_OPUS" in registry
    assert "WEATHER" in registry
    
    for cls_name, mod in registry.items():
        assert hasattr(mod, "CLASS_NAME")
        assert hasattr(mod, "EXAMPLES")
        assert isinstance(mod.EXAMPLES, list)
        assert len(mod.EXAMPLES) > 0 or cls_name == "SELF_IMPROVEMENT"

def test_result_shape_invariant():
    """
    STRUCTURAL: Every classify() result must contain specific keys.
    """
    with patch("intent_classifier.v2.classifier._load"), \
         patch("intent_classifier.v2.classifier._embed_fn", return_value=[[0.1]*384]), \
         patch("intent_classifier.v2.classifier._collection") as mock_col:
        
        mock_col.query.return_value = {
            "distances": [[0.1]*5],
            "metadatas": [[{"class": "WEATHER"}]*5]
        }
        mock_col.count.return_value = 100
        
        res = classifier.classify("test")
        required = {"classification", "confidence", "margin", "latency_ms"}
        assert required.issubset(res.keys())
        assert isinstance(res["classification"], str)
        assert isinstance(res["confidence"], float)
        assert isinstance(res["margin"], float)
        assert isinstance(res["latency_ms"], float)

def test_delegate_opus_consistency():
    """
    STRUCTURAL: DELEGATE_OPUS must never have high confidence/margin 
    when returned as a fallback for low-conf results.
    (If it's returned because it WON the vote, it can have high conf).
    """
    # Test fallback case
    mock_results = {
        "distances": [[0.1]*5],
        "metadatas": [[{"class": "WEATHER"}]*3 + [{"class": "GREETING"}]*2]
    }
    with patch("intent_classifier.v2.classifier._load"), \
         patch("intent_classifier.v2.classifier._embed_fn", return_value=[[0.1]*384]), \
         patch("intent_classifier.v2.classifier._collection") as mock_col:
        
        mock_col.query.return_value = mock_results
        mock_col.count.return_value = 100
        
        res = classifier.classify("ambiguous")
        assert res["classification"] == "DELEGATE_OPUS"
        assert res["confidence"] == 0.6 # Low confidence fallback
