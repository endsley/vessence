from jane_web.tts_chunks import split_tts_chunks


def test_split_tts_chunks_combines_short_sentences_within_limit():
    assert split_tts_chunks("Hello. World!", max_chars=20) == ["Hello. World!"]


def test_split_tts_chunks_splits_sentences_over_limit():
    assert split_tts_chunks("Hello. World!", max_chars=10) == ["Hello.", "World!"]


def test_split_tts_chunks_splits_long_sentence_on_commas():
    text = "alpha, beta, gamma"

    assert split_tts_chunks(text, max_chars=12) == ["alpha, beta", "gamma"]


def test_split_tts_chunks_preserves_blank_text_fallback():
    assert split_tts_chunks("   ", max_chars=2) == ["  "]
