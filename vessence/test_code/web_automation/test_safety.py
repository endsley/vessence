"""Unit tests for agent_skills.web_automation.safety."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from agent_skills.web_automation import safety


def test_domain_of_basic():
    assert safety.domain_of("https://citywater.com/billing") == "citywater.com"
    assert safety.domain_of("http://sub.example.com:8080/x") == "sub.example.com"
    assert safety.domain_of("not a url") == ""
    assert safety.domain_of("") == ""


def test_is_blocked_direct_match():
    safety.BLOCKED_DOMAINS.add("bad.test")
    try:
        assert safety.is_blocked("https://bad.test/page") is True
        assert safety.is_blocked("https://sub.bad.test/page") is True  # subdomain
        assert safety.is_blocked("https://good.test/page") is False
    finally:
        safety.BLOCKED_DOMAINS.discard("bad.test")


def test_classify_read_only_is_low():
    for a in ("snapshot", "status", "wait", "screenshot", "extract"):
        assert safety.classify_action(a, {}) == "low"


def test_classify_navigation_by_path_keywords():
    assert safety.classify_action("navigate", {"url": "https://shop.example/checkout"}) == "high"
    assert safety.classify_action("navigate", {"url": "https://bank.example/transfer-all"}) == "critical"
    assert safety.classify_action("navigate", {"url": "https://site.example/about"}) == "low"


def test_classify_interaction_inherits_from_args():
    # Clicking/typing near a high-risk keyword promotes the classification.
    r = safety.classify_action("click", {"ref": "e04", "text": "Pay Now"})
    assert r == "high"  # "pay" matches _HIGH_RISK_KEYWORDS
    r = safety.classify_action("fill", {"ref": "e02", "text": "submit this"})
    assert r == "high"
    r = safety.classify_action("press", {"key": "Enter"})
    assert r == "medium"


def test_classify_fill_plain_text_is_medium():
    r = safety.classify_action("fill", {"ref": "e02", "text": "hello world"})
    assert r == "medium"


def test_requires_confirmation_only_high_critical():
    assert not safety.requires_confirmation("low")
    assert not safety.requires_confirmation("medium")
    assert safety.requires_confirmation("high")
    assert safety.requires_confirmation("critical")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
