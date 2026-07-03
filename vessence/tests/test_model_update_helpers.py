from agent_skills import check_for_updates, notify_updates
from agent_skills.model_update_helpers import (
    MODEL_UPDATE_SEARCH_QUERY,
    discord_bot_headers,
    discord_channel_messages_url,
    model_update_notification_message,
    model_update_prompt,
    should_persist_model_update,
)


def test_update_scripts_expose_helpers():
    assert check_for_updates.MODEL_UPDATE_SEARCH_QUERY == MODEL_UPDATE_SEARCH_QUERY
    assert check_for_updates._model_update_prompt is model_update_prompt
    assert check_for_updates._should_persist_model_update is should_persist_model_update
    assert notify_updates._discord_bot_headers is discord_bot_headers
    assert notify_updates._discord_channel_messages_url is discord_channel_messages_url
    assert notify_updates._model_update_notification_message is model_update_notification_message


def test_model_update_prompt_includes_current_model_and_required_schema():
    prompt = model_update_prompt("gemini-current")
    assert "gemini-current" in prompt
    assert '"new_model_found": true/false' in prompt
    assert '"source_url": "link to news"' in prompt


def test_should_persist_model_update_preserves_truthy_flag_policy():
    assert should_persist_model_update({"new_model_found": True})
    assert should_persist_model_update({"new_model_found": "yes"})
    assert not should_persist_model_update({"new_model_found": False})
    assert not should_persist_model_update({})


def test_notification_message_and_discord_request_helpers_preserve_shapes():
    data = {
        "model_name": "Gemini X",
        "key_improvements": "- better coding",
        "source_url": "https://example.com",
    }
    assert model_update_notification_message(data) == (
        "🚀 **New Model Upgrade Detected!**\n\n"
        "**Model:** Gemini X\n"
        "**Improvements:**\n- better coding\n\n"
        "**Source:** https://example.com\n\n"
        "Should we discuss upgrading our brains to this new model?"
    )
    assert discord_channel_messages_url("123") == "https://discord.com/api/v10/channels/123/messages"
    assert discord_bot_headers("token") == {
        "Authorization": "Bot token",
        "Content-Type": "application/json",
    }
