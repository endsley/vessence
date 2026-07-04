from agent_skills.web_automation.safety import (
    action_text_blob,
    classify_action,
    domain_of,
    is_blocked,
    keyword_risk,
    requires_confirmation,
)


def test_domain_and_blocked_domain_helpers_preserve_host_policy():
    assert domain_of("https://Example.COM:443/path") == "example.com"
    assert domain_of("not a url") == ""

    assert is_blocked("https://phishing.example/login")
    assert is_blocked("https://sub.malware.example/path")
    assert not is_blocked("https://safe.example/path")


def test_keyword_risk_uses_word_boundaries_and_critical_before_high():
    assert keyword_risk("company profile") is None
    assert keyword_risk("open payment settings") == "high"
    assert keyword_risk("wire transfer now") == "critical"
    assert keyword_risk("delete account button") == "critical"


def test_classify_action_preserves_low_navigation_and_form_risk_tiers():
    assert classify_action("snapshot", {}) == "low"
    assert classify_action("extract", {}) == "low"
    assert classify_action("navigate", {"url": "https://example.test/company"}) == "low"
    assert classify_action("navigate", {"url": "https://example.test/pay"}) == "high"
    assert classify_action("navigate", {"url": "https://example.test/pay/all"}) == "critical"

    assert action_text_blob(
        {"text": "Confirm", "value": "Transfer"},
        resolved_name="Send money",
        resolved_role="button",
    ) == "confirm transfer  send money button"
    assert classify_action("click", {"text": "Confirm transfer"}) == "high"
    assert classify_action("press", {"key": "Escape"}) == "medium"


def test_requires_confirmation_preserves_high_and_critical_gate():
    assert not requires_confirmation("low")
    assert not requires_confirmation("medium")
    assert requires_confirmation("high")
    assert requires_confirmation("critical")
