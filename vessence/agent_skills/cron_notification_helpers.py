"""Pure helpers for cron notification utilities."""

from __future__ import annotations

from collections.abc import Mapping


def discord_webhook_payload(message: str, *, max_chars: int = 2000) -> dict:
    return {"content": message[:max_chars]}


def strip_work_log_notification_markup(message: str) -> str:
    return message.replace("**", "").replace("```", "").strip()


def work_log_notification_text(message: str, *, max_chars: int = 300) -> str:
    return strip_work_log_notification_markup(message)[:max_chars]


def cron_env_payload(
    env: Mapping[str, str],
    *,
    vessence_home: str,
    vessence_data_home: str,
    logs_dir: str,
) -> dict:
    return {
        "DISCORD_TOKEN": env.get("DISCORD_TOKEN", ""),
        "DISCORD_CHANNEL_ID": env.get("DISCORD_CHANNEL_ID", ""),
        "VESSENCE_HOME": vessence_home,
        "VESSENCE_DATA_HOME": vessence_data_home,
        "LOGS_DIR": logs_dir,
    }
