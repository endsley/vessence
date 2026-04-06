---
Title: Auto-request permissions on first use and guided onboarding
Priority: 2
Status: pending
Created: 2026-04-06
---

## Problem
When the user asks Jane to read text messages, she says "permission is not set." The user has to manually find the notification access setting in Android system settings. This is confusing — the app should guide them there automatically.

## Goal
1. On first launch (or first time phone tools are used), request all needed permissions via Android runtime dialogs
2. For NotificationListener (required for reading messages), show a clear explanation and deep-link directly to the system settings page
3. If a tool call fails due to missing permission, show a specific "Tap to enable" action instead of a generic error

## Permissions needed
- `READ_CONTACTS` — runtime permission dialog (standard)
- `CALL_PHONE` — runtime permission dialog (standard)  
- `SEND_SMS` — runtime permission dialog (standard)
- NotificationListener — requires manual enable in system settings (deep-link via `ACTION_NOTIFICATION_LISTENER_SETTINGS`)

## Approach
1. Add a permission check on first launch or when phone tools are first enabled
2. Request standard permissions via `ActivityResultContracts.RequestMultiplePermissions`
3. For NotificationListener: show a dialog explaining why, with a button that deep-links to settings
4. When a tool returns `NeedsUser("grant X permission")`, show a snackbar with "Grant permission" action that opens the right settings page

## Files
- `android/.../MainActivity.kt` — permission request flow
- `android/.../ui/settings/` — settings screen permission status display
- `android/.../tools/ClientToolDispatcher.kt` — better error messages on permission failure
