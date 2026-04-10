package com.vessences.android.notifications

import android.app.Notification
import android.content.ComponentName
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * NotificationListenerService that captures messaging-category notifications
 * into [RecentMessagesBuffer] for Jane to read aloud via `messages.read_recent`.
 *
 * Why not READ_SMS? The SMS permission family is Play-Store-restricted to
 * default SMS apps and only sees SMS anyway. Notification listener sees SMS,
 * WhatsApp, Signal, iMessage relay, Messenger, and any messaging app
 * uniformly. User must grant it via system settings (not a runtime prompt) —
 * the deep-link intent `android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS`
 * is used by the permission flow.
 *
 * Lifecycle notes:
 *  - Wait for [onListenerConnected] before the buffer is considered authoritative.
 *  - On [onListenerDisconnected], clear the buffer and request rebind. A
 *    disconnected listener will not receive posts; stale buffer data would
 *    be misleading to read aloud.
 *  - This service can be killed by the system; it rebinds automatically when
 *    Android restores it.
 */
class VessenceNotificationListener : NotificationListenerService() {

    override fun onListenerConnected() {
        super.onListenerConnected()
        _connected.value = true
        setLive(this)
        Log.i(TAG, "notification listener connected")
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        _connected.value = false
        setLive(null)
        RecentMessagesBuffer.clear()
        Log.i(TAG, "notification listener disconnected — requesting rebind")
        try {
            requestRebind(ComponentName(this, VessenceNotificationListener::class.java))
        } catch (e: Exception) {
            Log.w(TAG, "requestRebind failed", e)
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        try {
            handlePosted(sbn)
        } catch (e: Exception) {
            Log.w(TAG, "onNotificationPosted failed", e)
        }
    }

    private fun handlePosted(sbn: StatusBarNotification) {
        val entries = extractMessages(sbn) ?: return
        for (entry in entries) {
            RecentMessagesBuffer.record(entry)
        }
        // Push new SMS to server so Jane has fresh message data.
        // Only trigger for messaging apps (SMS, WhatsApp, etc.)
        // Push new messages to server when a new SMS notification arrives
        if (entries.isNotEmpty()) {
            val scope = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO + kotlinx.coroutines.SupervisorJob())
            scope.launch {
                try {
                    com.vessences.android.contacts.SmsSyncManager.pushNewMessages(applicationContext)
                } catch (e: Exception) {
                    android.util.Log.d(TAG, "SMS push sync failed: ${e.message}")
                }
            }
        }
    }

    /**
     * Single source of truth for turning a [StatusBarNotification] into zero
     * or more [RecentMessagesBuffer.Entry] records. Used by BOTH the live
     * `onNotificationPosted` path (which records into the ring buffer) and
     * the `snapshotActiveMessages()` path (which walks the currently-active
     * set on demand). Consolidating prevents the two paths from drifting.
     *
     * Returns null if the notification should be skipped entirely (wrong
     * category, own package, no parseable content).
     */
    private fun extractMessages(sbn: StatusBarNotification): List<RecentMessagesBuffer.Entry>? {
        val n: Notification = sbn.notification
        if (n.category != Notification.CATEGORY_MESSAGE) return null
        if (sbn.packageName == packageName) return null

        val extras: Bundle = n.extras ?: return null
        val now = System.currentTimeMillis()

        // Preferred path: MessagingStyle notifications carry a typed message
        // array. Use NotificationCompat.MessagingStyle — the platform
        // Notification.MessagingStyle no longer exposes an extractor in
        // recent API levels.
        val style: NotificationCompat.MessagingStyle? = try {
            NotificationCompat.MessagingStyle.extractMessagingStyleFromNotification(n)
        } catch (e: Exception) {
            null
        }

        if (style != null) {
            val msgs = style.messages ?: emptyList()
            if (msgs.isEmpty()) return null
            val out = mutableListOf<RecentMessagesBuffer.Entry>()
            for ((idx, msg) in msgs.withIndex()) {
                val senderName: String =
                    msg.person?.name?.toString()
                        ?: extras.getString(Notification.EXTRA_TITLE)
                        ?: "Unknown"
                val bodyStr = msg.text?.toString()?.trim().orEmpty()
                if (bodyStr.isEmpty()) continue
                out.add(
                    RecentMessagesBuffer.Entry(
                        sender = senderName,
                        body = bodyStr,
                        timestamp = if (msg.timestamp > 0) msg.timestamp else now,
                        packageName = sbn.packageName,
                        sbnKey = "${sbn.key}#$idx",
                    )
                )
            }
            return if (out.isEmpty()) null else out
        }

        // Fallback for apps that don't use MessagingStyle.
        val title: String = extras.getString(Notification.EXTRA_TITLE)?.trim() ?: "Unknown"
        val textStr: String = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()?.trim().orEmpty()
        if (textStr.isEmpty()) return null
        return listOf(
            RecentMessagesBuffer.Entry(
                sender = title,
                body = textStr,
                timestamp = n.`when`.takeIf { it > 0 } ?: now,
                packageName = sbn.packageName,
                sbnKey = sbn.key,
            )
        )
    }

    /**
     * Return a snapshot of currently-active messaging notifications (the ones
     * still showing in the notification shade, i.e., "unread").
     *
     * This is the authoritative source for `messages.fetch_unread` — we do NOT
     * rely on the ring buffer for this because the buffer records every
     * notification we've ever seen, including ones the user has since dismissed.
     * Active notifications are filtered by [Notification.CATEGORY_MESSAGE] and
     * parsed via [NotificationCompat.MessagingStyle] when possible.
     *
     * Safe to call from any thread; activeNotifications is synchronous.
     */
    fun snapshotActiveMessages(): List<RecentMessagesBuffer.Entry> {
        val sbns = try {
            activeNotifications ?: return emptyList()
        } catch (e: Exception) {
            Log.w(TAG, "activeNotifications threw", e)
            return emptyList()
        }
        val out = mutableListOf<RecentMessagesBuffer.Entry>()
        for (sbn in sbns) {
            try {
                extractMessages(sbn)?.let { out.addAll(it) }
            } catch (e: Exception) {
                Log.w(TAG, "snapshotActiveMessages entry failed", e)
            }
        }
        return out.sortedByDescending { it.timestamp }
    }

    companion object {
        private const val TAG = "VessenceNotifListener"

        private val _connected = MutableStateFlow(false)
        val connected: StateFlow<Boolean> = _connected

        /** Module-level handle to the currently-bound service instance so
         *  handlers (e.g., MessagesFetchUnreadHandler) can call
         *  [snapshotActiveMessages] without needing direct access. Set by
         *  onListenerConnected / cleared by onListenerDisconnected. */
        @Volatile
        var liveInstance: VessenceNotificationListener? = null
            private set

        internal fun setLive(inst: VessenceNotificationListener?) {
            liveInstance = inst
        }
    }
}
