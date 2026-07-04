"""Pure helpers for Gemini model update notifications."""
from __future__ import annotations


MODEL_UPDATE_SEARCH_QUERY = "latest Google Gemini model announcement news for developers coding"


def model_update_prompt(current_model: str) -> str:
    return f"""
    Search the internet for the latest Google Gemini AI models. 
    Our current highest-tier model is {current_model}.
    
    Is there a newer or more capable version available (e.g., Gemini 3.0, or a new ultra/pro variant with better coding capabilities)?
    
    Return a JSON object:
    {{
      "new_model_found": true/false,
      "model_name": "name of the new model",
      "key_improvements": "bullet points of key features",
      "source_url": "link to news"
    }}
    
    Only set new_model_found to true if the model is genuinely newer or significantly upgraded compared to {current_model}.
    """


def should_persist_model_update(data: dict) -> bool:
    return bool(data.get("new_model_found"))


def model_update_notification_message(data: dict) -> str:
    return (
        f"🚀 **New Model Upgrade Detected!**\n\n"
        f"**Model:** {data['model_name']}\n"
        f"**Improvements:**\n{data['key_improvements']}\n\n"
        f"**Source:** {data['source_url']}\n\n"
        f"Should we discuss upgrading our brains to this new model?"
    )


def discord_channel_messages_url(channel_id: str) -> str:
    return f"https://discord.com/api/v10/channels/{channel_id}/messages"


def discord_bot_headers(discord_token: str) -> dict:
    return {
        "Authorization": f"Bot {discord_token}",
        "Content-Type": "application/json",
    }


def discord_message_payload(message: str) -> dict:
    return {"content": message}
