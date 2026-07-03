from agent_skills import confirmation, end_phrase
from agent_skills.phrase_matcher import PUNCT_RE, normalize_phrase, phrase_in_set


def test_confirmation_and_end_phrase_use_shared_matcher():
    assert confirmation._PUNCT_RE is PUNCT_RE
    assert confirmation._normalize is normalize_phrase
    assert confirmation._phrase_in_set is phrase_in_set
    assert end_phrase._PUNCT_RE is PUNCT_RE
    assert end_phrase._normalize is normalize_phrase
    assert end_phrase._phrase_in_set is phrase_in_set


def test_normalize_phrase_preserves_apostrophes_and_strips_other_punctuation():
    assert normalize_phrase("  YES, please! ") == "yes please"
    assert normalize_phrase("No, I'm good.") == "no i'm good"


def test_phrase_in_set_handles_empty_text_and_normalized_membership():
    phrases = {"yes please"}

    assert phrase_in_set("Yes, please!", phrases)
    assert not phrase_in_set("", phrases)
    assert not phrase_in_set(None, phrases)


def test_confirmation_yes_no_and_end_phrase_ambiguity_contract():
    assert confirmation.is_yes("Sure!")
    assert confirmation.is_no("No.")
    assert end_phrase.is_end("No.")
    assert end_phrase.is_end("cancel")
    assert not confirmation.is_no("cancel")
