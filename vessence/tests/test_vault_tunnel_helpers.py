from agent_skills import vault_tunnel_url
from agent_skills.vault_tunnel_helpers import (
    select_vault_url,
    trycloudflare_url_from_lines,
    vault_url_output,
)


def test_vault_tunnel_url_uses_extracted_helpers():
    assert vault_tunnel_url._select_vault_url is select_vault_url
    assert vault_tunnel_url._trycloudflare_url_from_lines is trycloudflare_url_from_lines
    assert vault_tunnel_url._vault_url_output is vault_url_output


def test_select_vault_url_prefers_env_then_fixed_domain():
    assert select_vault_url("https://env.example", "https://fixed.example") == "https://env.example"
    assert select_vault_url("", "https://fixed.example") == "https://fixed.example"
    assert select_vault_url(None, "") is None


def test_trycloudflare_url_from_lines_returns_latest_matching_url():
    lines = [
        "old https://old.trycloudflare.com\n",
        "noise\n",
        "new https://new-name.trycloudflare.com path\n",
    ]

    assert trycloudflare_url_from_lines(lines) == "https://new-name.trycloudflare.com"
    assert trycloudflare_url_from_lines(["no tunnel"]) is None


def test_vault_url_output_preserves_cli_text():
    assert vault_url_output("https://vault.example", "https://jane.example") == (
        "Vault URL: https://vault.example\n"
        "Jane URL:  https://jane.example"
    )
    assert vault_url_output(None, "https://jane.example") == (
        "Vault tunnel URL not available. Is the tunnel running?"
    )
