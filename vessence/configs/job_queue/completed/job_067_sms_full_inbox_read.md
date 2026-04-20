# Job: Full SMS Inbox Access for Jane

Status: completed
Priority: 1
Model: opus
Created: 2026-04-09

## Objective
Give Jane the ability to read ALL text messages (read and unread) from the phone's SMS inbox, not just active notifications. This enables triage ("which messages are important?"), sender-specific queries ("what did my wife text me?"), and reading recent history regardless of notification state.

## Design
1. **Android: Add READ_SMS permission**
   - Add `<uses-permission android:name="android.permission.READ_SMS" />` to AndroidManifest.xml
   - Add to the startup permission request in MainActivity.kt
   - Since we're sideloading, Play Store restrictions don't apply

2. **Android: New tool handler `messages.read_inbox`**
   - Query `content://sms/inbox` for recent messages (default last 20, configurable via `limit` arg)
   - Optional `sender` arg to filter by contact name (resolve via ContactsResolver)
   - Optional `since` arg for time-based filtering (e.g., last 24 hours)
   - Return structured data: sender name (resolved from contacts), body, timestamp, read/unread status
   - Register in ClientToolDispatcher

3. **Server: Add tool to PHONE_TOOLS_PROTOCOL**
   - Document `messages.read_inbox` in context_builder's PHONE_TOOLS_PROTOCOL
   - Jane decides response mode based on user intent:
     - "read my texts" → fetch recent, triage important vs spam
     - "what did my wife say" → filter by sender
     - "read messages from today" → time-based filter
   - Jane sees read/unread status and can prioritize unread

4. **Keep existing `messages.fetch_unread` as-is**
   - It's still useful for quick "any new notifications?" checks
   - `read_inbox` is the deeper, more comprehensive tool

## Files Involved
- `android/app/src/main/AndroidManifest.xml` — add READ_SMS permission
- `android/app/src/main/java/com/vessences/android/MainActivity.kt` — add to permission request
- `android/app/src/main/java/com/vessences/android/tools/MessagesReadInboxHandler.kt` — new handler
- `android/app/src/main/java/com/vessences/android/tools/ClientToolDispatcher.kt` — register handler
- `context_builder/v1/context_builder.py` — add to PHONE_TOOLS_PROTOCOL
- `intent_classifier/v1/gemma_router.py` — update READ_MESSAGES classification if needed

## Notes
- READ_SMS is Play Store restricted but fine for sideloading
- Content provider query is fast and doesn't need notification listener
- Sender phone numbers should be resolved to contact names via ContactsResolver
- OTP/verification codes should still be filtered out (same safety rules as fetch_unread)
