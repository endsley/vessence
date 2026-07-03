from agent_skills.marketplace import harvester
from agent_skills.marketplace.listing_rules import (
    BAD_TITLE_KEYWORDS,
    CURRENT_YEAR,
    MILES_PATTERNS,
    is_suspicious,
    parse_miles,
    parse_year,
    slugify,
    title_filter_result,
)


def test_harvester_uses_extracted_listing_rules() -> None:
    assert harvester.CURRENT_YEAR == CURRENT_YEAR
    assert harvester._MILES_PATTERNS is MILES_PATTERNS
    assert harvester._BAD_TITLE_KEYWORDS is BAD_TITLE_KEYWORDS
    assert harvester._slugify is slugify
    assert harvester._parse_year is parse_year
    assert harvester._parse_miles is parse_miles
    assert harvester._is_suspicious is is_suspicious
    assert harvester._title_filter_result is title_filter_result


def test_slugify_and_parse_year() -> None:
    assert slugify("Honda Fit / Clean Title!") == "honda_fit_clean_title"
    assert slugify("!!!") == "query"
    assert parse_year("2012 Honda Fit") == 2012
    assert parse_year("1899 antique") is None
    assert parse_year("2030 future car") is None
    assert parse_year(None) is None


def test_parse_miles_handles_common_marketplace_text_patterns() -> None:
    assert parse_miles("123,456 miles") == 123456
    assert parse_miles("85k mi.") == 85000
    assert parse_miles("Driven 99000 miles") == 99000
    assert parse_miles("Mileage: 101,000") == 101000
    assert parse_miles("50 miles") is None
    assert parse_miles("999999 miles") is None
    assert parse_miles(None) is None


def test_is_suspicious_flags_implausibly_low_mileage_for_older_cars() -> None:
    assert is_suspicious(None, 10000) == (False, "")
    assert is_suspicious(2024, 1000) == (False, "")
    assert is_suspicious(2010, 100000) == (False, "")

    suspicious, reason = is_suspicious(2010, 20000)
    assert suspicious
    assert reason == "implausibly low miles: 20000mi / 16yr = 1250/yr"


def test_title_filter_result_matches_clean_and_bad_title_policy() -> None:
    assert title_filter_result("Clean title, no accidents") == (True, True, False)
    assert title_filter_result("Clean title but rebuilt title") == (False, True, True)
    assert title_filter_result("No title language") == (False, False, False)
    assert title_filter_result("No title language", require_clean_title=False) == (True, False, False)
    assert title_filter_result("salvage title", require_clean_title=False) == (False, False, True)
