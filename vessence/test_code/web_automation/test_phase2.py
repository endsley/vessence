"""Phase 2 tests: profiles, secrets, perception-aware safety, fill_secret."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from agent_skills.web_automation import actions, profiles, safety, secrets
from agent_skills.web_automation import snapshot as snap_mod
from agent_skills.web_automation import skill


@pytest.fixture(autouse=True)
def _tmp_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path))
    return tmp_path


# ── profiles ──────────────────────────────────────────────────────────────────

def test_profiles_create_and_get():
    m = profiles.create("City Water", "citywater.com")
    assert m.profile_id == "city_water"
    assert m.domain == "citywater.com"
    again = profiles.get("city_water")
    assert again.display_name == "City Water"


def test_profiles_slugify_handles_weird_names():
    assert profiles.slugify("Pay Water Bill!!") == "pay_water_bill"
    assert profiles.slugify("AMAZON") == "amazon"
    assert profiles.slugify("   ") == "profile"


def test_profiles_collision_suffixes():
    profiles.create("pay", "a.com")
    m2 = profiles.create("pay", "b.com")
    assert m2.profile_id == "pay_2"


def test_profiles_list_and_delete():
    profiles.create("alpha", "a.com")
    profiles.create("beta", "b.com")
    names = {p.profile_id for p in profiles.list_profiles()}
    assert {"alpha", "beta"} <= names
    profiles.delete("alpha")
    assert "alpha" not in {p.profile_id for p in profiles.list_profiles()}


def test_profiles_bind_check_accepts_subdomain():
    profiles.create("bank", "citybank.com")
    # exact match
    profiles.bind_check("bank", "https://citybank.com/login")
    # subdomain
    profiles.bind_check("bank", "https://app.citybank.com/dashboard")


def test_profiles_bind_check_rejects_foreign_domain():
    profiles.create("bank", "citybank.com")
    with pytest.raises(profiles.ProfileDomainMismatch):
        profiles.bind_check("bank", "https://attacker.com/steal")


def test_profiles_bind_check_unknown_id_raises():
    with pytest.raises(profiles.ProfileNotFound):
        profiles.bind_check("nope", "https://x.com")


# ── secrets ────────────────────────────────────────────────────────────────────

def test_secrets_create_and_get_domain_match():
    sid = secrets.create("citywater.com", "login", "chieh", "hunter2")
    val = secrets.get(sid, expected_domain="citywater.com", caller="test")
    assert val.username == "chieh"
    assert val.password == "hunter2"


def test_secrets_subdomain_is_ok():
    sid = secrets.create("citywater.com", "login", "u", "p")
    val = secrets.get(sid, expected_domain="app.citywater.com", caller="test")
    assert val.username == "u"


def test_secrets_refuse_wrong_domain():
    sid = secrets.create("bank.com", "login", "u", "p")
    with pytest.raises(secrets.SecretDomainMismatch):
        secrets.get(sid, expected_domain="attacker.com", caller="test")


def test_secrets_delete_marks_gone():
    sid = secrets.create("x.com", "l", "u", "p")
    secrets.delete(sid)
    with pytest.raises(secrets.SecretNotFound):
        secrets.get(sid, expected_domain="x.com", caller="test")


def test_secrets_list_hides_credentials():
    sid = secrets.create("x.com", "label", "u", "p", notes="hello")
    entries = secrets.list_secrets()
    [e] = [e for e in entries if e.secret_id == sid]
    # Index only holds metadata — no username, password, or notes.
    assert not hasattr(e, "password")
    assert e.domain == "x.com"
    assert e.label == "label"


# ── perception-aware safety ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_classify_click_sees_button_name_through_snapshot():
    """click(ref=e04) where e04 is 'Delete Account' → high risk, even
    though the ref string 'e04' itself is opaque."""
    page = MagicMock()
    page.url = "https://x.com"
    page.title = AsyncMock(return_value="X")
    page.accessibility.snapshot = AsyncMock(return_value={
        "role": "WebArea",
        "children": [
            {"role": "button", "name": "Go to dashboard", "children": []},
            {"role": "button", "name": "Delete my account", "children": []},
        ],
    })
    page.eval_on_selector_all = AsyncMock(return_value=[])
    await snap_mod.take_snapshot(page)
    # Benign click still medium.
    assert safety.classify_action("click", {"ref": "e01"}, page=page) == "medium"
    # Sensitive click elevates.
    assert safety.classify_action("click", {"ref": "e02"}, page=page) in ("high", "critical")


def test_classify_url_ignores_hostname_tokens():
    # "company.com" should NOT trip the "pay" keyword (from "companly"?) — word boundary.
    assert safety.classify_action("navigate", {"url": "https://company.com/home"}) == "low"
    # But a payment path SHOULD trigger.
    assert safety.classify_action("navigate", {"url": "https://site.com/pay/now"}) == "high"


# ── fill_secret action ───────────────────────────────────────────────────────

def _frame_aware_locator(frame_url: str):
    """Build a fake Locator whose element_handle → owner_frame.url chain
    returns ``frame_url``. This is what fill_secret uses for iframe-safe
    domain binding."""
    frame = MagicMock()
    frame.url = frame_url
    handle = MagicMock()
    handle.owner_frame = AsyncMock(return_value=frame)
    loc = MagicMock()
    loc.element_handle = AsyncMock(return_value=handle)
    loc.fill = AsyncMock(return_value=None)
    return loc


@pytest.mark.asyncio
async def test_fill_secret_uses_store_and_never_surfaces_plaintext():
    sid = secrets.create("example.com", "site_login", "chieh", "s3cret!")
    page = MagicMock()
    page.url = "https://example.com/login"
    page.title = AsyncMock(return_value="Login")
    page.accessibility.snapshot = AsyncMock(return_value={
        "role": "WebArea",
        "children": [{"role": "textbox", "name": "Password", "children": []}],
    })
    page.eval_on_selector_all = AsyncMock(return_value=[])
    locator = _frame_aware_locator("https://example.com/login")
    page.get_by_role = MagicMock(return_value=locator)
    await snap_mod.take_snapshot(page)
    res = await actions.fill_secret(page, "e01", sid, field="password")
    assert res.ok, res.message
    assert "s3cret!" not in res.message
    # Fill received the actual plaintext.
    locator.fill.assert_awaited_once()
    called_with = locator.fill.call_args
    assert called_with.args[0] == "s3cret!"


@pytest.mark.asyncio
async def test_fill_secret_domain_mismatch_refuses():
    sid = secrets.create("bank.com", "login", "u", "p")
    page = MagicMock()
    page.url = "https://phishing-lookalike.com/login"
    page.title = AsyncMock(return_value="Evil")
    page.accessibility.snapshot = AsyncMock(return_value={
        "role": "WebArea",
        "children": [{"role": "textbox", "name": "Password", "children": []}],
    })
    page.eval_on_selector_all = AsyncMock(return_value=[])
    page.get_by_role = MagicMock(return_value=_frame_aware_locator("https://phishing-lookalike.com/login"))
    await snap_mod.take_snapshot(page)
    res = await actions.fill_secret(page, "e01", sid, field="password")
    assert not res.ok
    assert "refused" in res.message.lower() or "bound" in res.message.lower()


@pytest.mark.asyncio
async def test_fill_secret_refuses_cross_origin_iframe():
    """The element sits inside an iframe pointing at an attacker domain,
    even though the top-level page URL looks legitimate. The fix: check
    the element's OWN frame URL, not page.url."""
    sid = secrets.create("mybank.com", "login", "u", "hunter2")
    page = MagicMock()
    page.url = "https://mybank.com/login"  # top-level looks OK
    page.title = AsyncMock(return_value="Login")
    page.accessibility.snapshot = AsyncMock(return_value={
        "role": "WebArea",
        "children": [{"role": "textbox", "name": "Password", "children": []}],
    })
    page.eval_on_selector_all = AsyncMock(return_value=[])
    # …but the input is in an iframe on attacker.com:
    page.get_by_role = MagicMock(return_value=_frame_aware_locator("https://attacker.com/steal"))
    await snap_mod.take_snapshot(page)
    res = await actions.fill_secret(page, "e01", sid, field="password")
    assert not res.ok, "fill_secret should refuse cross-origin iframe"


# ── index corruption + path traversal ─────────────────────────────────────────

def test_profiles_get_refuses_path_traversal():
    with pytest.raises(profiles.ProfileNotFound):
        profiles.get("../../../etc/passwd")


def test_secrets_get_refuses_path_traversal():
    with pytest.raises(secrets.SecretNotFound):
        secrets.get("../evil", expected_domain="x.com")


def test_secrets_corrupt_index_halts_instead_of_wiping():
    sid = secrets.create("x.com", "l", "u", "p")
    # Corrupt the index.
    idx_path = secrets._index_path()
    idx_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(secrets.SecretIndexCorrupted):
        secrets.list_secrets()


# ── snapshot fails loud when a11y broken ─────────────────────────────────────

@pytest.mark.asyncio
async def test_snapshot_raises_on_a11y_none():
    page = MagicMock()
    page.url = "https://x.com"
    page.title = AsyncMock(return_value="X")
    page.accessibility.snapshot = AsyncMock(return_value=None)
    page.eval_on_selector_all = AsyncMock(return_value=[])
    with pytest.raises(snap_mod.SnapshotError):
        await snap_mod.take_snapshot(page)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
