package com.vessences.android.tools

import android.content.Context
import android.util.Log
import com.vessences.android.notifications.NotificationSafety
import com.vessences.android.notifications.RecentMessagesBuffer
import com.vessences.android.notifications.VessenceNotificationListener

/**
 * Legacy handler for `messages.read_recent` — reads the last N notifications
 * from the [RecentMessagesBuffer] directly via Android TTS without routing
 * through Jane's mind.
 *
 * Prefer [MessagesFetchUnreadHandler] for most use cases — it returns
 * structured data to Jane so she can triage, summarize, or quote specific
 * senders. This handler exists for the rare "just read them all dumbly"
 * request.
 *
 * All safety filtering (OTP, placeholder bodies, lock-screen sensitivity,
 * listener access) is delegated to [NotificationSafety] so this handler
 * and [MessagesFetchUnreadHandler] share the SAME filter behavior — any
 * change to the OTP regex lands in both tools automatically.
 */
object MessagesReadRecentHandler : ClientToolHandler {

    override val name: String = "messages.read_recent"

    private const val DEFAULT_LIMIT = 5
    private const val MAX_LIMIT = 20
    private const val TAG = "MessagesReadRecent"

    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        if (!NotificationSafety.isListenerEnabled(ctx)) {
            queue.speak("I need notification access to read your messages. Opening the settings now.")
            try {
                val intent = android.content.Intent(android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
                intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                ctx.startActivity(intent)
            } catch (e: Exception) {
                queue.speak("Please open Settings, then Notifications, then Notification access, and enable Jane.")
            }
            return ToolActionStatus.NeedsUser("notification listener access not granted — settings opened")
        }
        if (!VessenceNotificationListener.connected.value) {
            queue.speak("Notification access is on but the listener is still starting up. Give it a moment and try again.")
            return ToolActionStatus.NeedsUser("notification listener not yet connected")
        }

        val requestedLimit = call.args.get("limit").asSafeInt() ?: DEFAULT_LIMIT
        val limit = requestedLimit.coerceIn(1, MAX_LIMIT)

        val raw = RecentMessagesBuffer.snapshot(limit * 3)  // over-fetch so filters have headroom
        val phoneLocked = NotificationSafety.isPhoneLocked(ctx)

        val filtered = raw.mapNotNull { NotificationSafety.filterSafe(it, phoneLocked) }.take(limit)

        if (filtered.isEmpty()) {
            queue.speak("No recent messages to read.")
            return ToolActionStatus.Completed("no messages after safety filter")
        }

        queue.speak("Reading your ${filtered.size} most recent messaging notifications.")
        for (entry in filtered) {
            val body = entry.body.take(NotificationSafety.MAX_BODY_CHARS)
            queue.speak("From ${entry.sender}: $body")
        }
        Log.i(TAG, "read ${filtered.size} messages (from ${raw.size} raw)")
        return ToolActionStatus.Completed("read ${filtered.size} messages")
    }
}
