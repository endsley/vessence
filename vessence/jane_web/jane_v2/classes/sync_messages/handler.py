"""Stage 2 handler for SYNC_MESSAGES — triggers a phone-side SMS sync.

Fire-and-forget: emits sync.force_sms tool call to Android, returns
short text for the chat bubble. Android's SyncForceSmsHandler runs
SmsSyncManager.forceSync() to pull the latest 14 days of SMS from
the device into the server's synced_messages table.
"""


def handle(prompt: str) -> dict:
    return {
        "text": "Syncing your messages now.",
        "client_tools": [{"name": "sync.force_sms", "args": {}}],
    }
