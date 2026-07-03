from agent_skills import ra_research_cron
from agent_skills.ra_research_discoveries import discovery_block


def test_ra_research_cron_uses_discovery_block_helper():
    assert ra_research_cron._discovery_block is discovery_block


def test_discovery_block_preserves_markdown_shape():
    assert discovery_block(
        "run1",
        "2026-07-02 12:00 EDT",
        "Mission",
        ["Discovery"],
        ["Flag"],
        ["Question"],
    ) == (
        "\n"
        "## Run run1 — 2026-07-02 12:00 EDT\n"
        "\n"
        "Mission: Mission\n"
        "\n"
        "### Discoveries\n"
        "- Discovery\n"
        "\n"
        "### Safety Flags\n"
        "- Flag\n"
        "\n"
        "### Open Questions\n"
        "- Question\n"
    )
