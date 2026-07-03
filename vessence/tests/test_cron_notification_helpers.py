from agent_skills import cron_utils
from agent_skills.cron_notification_helpers import (
    cron_env_payload,
    discord_webhook_payload,
    work_log_notification_text,
)


def test_cron_utils_uses_extracted_notification_helpers():
    assert cron_utils._discord_webhook_payload is discord_webhook_payload
    assert cron_utils._work_log_notification_text is work_log_notification_text
    assert cron_utils._cron_env_payload is cron_env_payload


def test_discord_webhook_payload_truncates_content_to_discord_limit():
    assert discord_webhook_payload("hello") == {"content": "hello"}
    assert discord_webhook_payload("x" * 2001)["content"] == "x" * 2000


def test_work_log_notification_text_strips_markdown_fences_and_truncates():
    assert work_log_notification_text(" **hello** ```code``` ") == "hello code"
    assert work_log_notification_text("x" * 301) == "x" * 300


def test_cron_env_payload_preserves_defaults_and_config_values():
    assert cron_env_payload(
        {"DISCORD_TOKEN": "token"},
        vessence_home="/repo",
        vessence_data_home="/data",
        logs_dir="/logs",
    ) == {
        "DISCORD_TOKEN": "token",
        "DISCORD_CHANNEL_ID": "",
        "VESSENCE_HOME": "/repo",
        "VESSENCE_DATA_HOME": "/data",
        "LOGS_DIR": "/logs",
    }
