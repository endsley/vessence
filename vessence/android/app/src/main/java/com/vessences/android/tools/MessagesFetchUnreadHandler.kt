package com.vessences.android.tools

import android.content.Context
import android.util.Log
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.vessences.android.notifications.NotificationSafety
import com.vessences.android.notifications.RecentMessagesBuffer
import com.vessences.android.notifications.VessenceNotificationListener

/**
 * Handler for `messages.fetch_unread` — gather the user's currently-unread
 * messaging notifications and ship them back to Jane's mind as structured
 * data via the TOOL_RESULT feedback channel.
 *
 * "Unread" = notification is still active in the shade (`activeNotifications`
 * on the listener service). Dismissed/swiped-away notifications are not
 * returned.
 *
 * Safety filtering (OTP, placeholder bodies, lock-screen sensitivity, listener
 * access) is delegated to [NotificationSafety] — the SAME filter set
 * [MessagesReadRecentHandler] uses, so both tools agree on what is safe to
 * expose. Any change to the OTP regex lands in both handlers automatically.
 *
 * The handler does NOT speak anything itself — it returns the list and lets
 * Jane decide the response mode (summary by sender, triaged read, direct
 * quote of a specific sender). Jane's response text is spoken via the
 * existing chat TTS path.
 */
object MessagesFetchUnreadHandler : ClientToolHandler {

    override val name: String = "messages.fetch_unread"

    private const val DEFAULT_LIMIT = 20
    private const val MAX_LIMIT = 50
    private const val TAG = "MessagesFetchUnread"

    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        // Permission + service-ready gates, in order.
        if (!NotificationSafety.isListenerEnabled(ctx)) {
            queue.speak("I need notification access to read your unread messages. Open Jane's settings and turn on notification access.")
            return ToolActionStatus.NeedsUser("notification listener access not granted")
        }
        if (!VessenceNotificationListener.connected.value) {
            queue.speak("Notification access is on but the listener is still starting up. Try again in a moment.")
            return ToolActionStatus.NeedsUser("notification listener not yet connected")
        }

        val limit = (call.args.get("limit").asSafeInt() ?: DEFAULT_LIMIT).coerceIn(1, MAX_LIMIT)

        // Snapshot the LIVE active notifications set (not the ring buffer,
        // which includes dismissed entries). Read once into a local to avoid
        // TOCTOU races if the listener disconnects between checks.
        val listener = VessenceNotificationListener.liveInstance
            ?: return ToolActionStatus.Failed("notification listener instance not available")
        val active: List<RecentMessagesBuffer.Entry> = try {
            listener.snapshotActiveMessages()
        } catch (e: Exception) {
            Log.e(TAG, "snapshotActiveMessages threw", e)
            emptyList()
        }

        if (active.isEmpty()) {
            val payload = JsonObject().apply {
                add("unread", JsonArray())
                addProperty("total_count", 0)
                addProperty("filtered_count", 0)
            }
            return ToolActionStatus.CompletedWithData("no unread messaging notifications", payload)
        }

        val phoneLocked = NotificationSafety.isPhoneLocked(ctx)
        val filtered = active
            .asSequence()
            .mapNotNull { NotificationSafety.filterSafe(it, phoneLocked) }
            .take(limit)
            .toList()

        val unreadArray = JsonArray()
        for (entry in filtered) {
            val obj = JsonObject().apply {
                addProperty("sender", entry.sender)
                addProperty("body", entry.body.take(NotificationSafety.MAX_BODY_CHARS))
                addProperty("timestamp", entry.timestamp)
                addProperty("app", entry.packageName)
            }
            unreadArray.add(obj)
        }
        val payload = JsonObject().apply {
            add("unread", unreadArray)
            addProperty("total_count", active.size)
            addProperty("filtered_count", filtered.size)
            addProperty("phone_locked", phoneLocked)
        }

        Log.i(TAG, "fetch_unread returning ${filtered.size} of ${active.size} active notifications")
        return ToolActionStatus.CompletedWithData(
            "returned ${filtered.size} unread messages to Jane",
            payload,
        )
    }
}
