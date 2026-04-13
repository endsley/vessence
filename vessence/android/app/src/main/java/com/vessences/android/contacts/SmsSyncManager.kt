package com.vessences.android.contacts

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.database.Cursor
import android.net.Uri
import android.provider.ContactsContract
import android.util.Log
import androidx.core.content.ContextCompat
import com.vessences.android.data.api.ApiClient
import com.vessences.android.notifications.NotificationSafety
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Syncs SMS messages to the Vessence server so Jane can answer questions
 * about text messages without a CLIENT_TOOL round-trip.
 *
 * Two sync modes:
 *   1. **Backfill** (first launch): uploads last 14 days of SMS
 *   2. **Push** (ongoing): called when a new SMS notification arrives,
 *      uploads just the new message(s) since last sync timestamp
 *
 * Server retains 14 days of messages and prunes older ones.
 * OTP/2FA messages are filtered before upload.
 */
object SmsSyncManager {

    private const val TAG = "SmsSyncManager"
    private const val PREFS_NAME = "sms_sync"
    private const val KEY_LAST_SYNC_TS = "last_sync_timestamp_ms"  // newest message timestamp synced
    private const val KEY_BACKFILL_DONE = "backfill_done"
    private const val DAYS_TO_SYNC = 14
    private const val MAX_MESSAGES = 1000  // safety cap for backfill

    /**
     * Initial backfill: sync last 14 days of SMS on first launch.
     * Subsequent launches skip if backfill was already done.
     * Call from MainActivity.onCreate.
     */
    suspend fun backfillIfNeeded(context: Context) {
        if (!hasPermission(context)) return
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        if (prefs.getBoolean(KEY_BACKFILL_DONE, false)) {
            Log.d(TAG, "Backfill already done, skipping")
            return
        }
        try {
            val sinceMs = System.currentTimeMillis() - DAYS_TO_SYNC * 24 * 60 * 60 * 1000L
            val messages = querySmsSince(context, sinceMs)
            if (messages.isEmpty()) {
                Log.d(TAG, "No SMS messages found for backfill")
                prefs.edit().putBoolean(KEY_BACKFILL_DONE, true).apply()
                return
            }
            uploadMessages(messages)
            // Record the newest message timestamp
            val newest = messages.maxOfOrNull { (it["timestamp_ms"] as? Long) ?: 0L } ?: 0L
            prefs.edit()
                .putBoolean(KEY_BACKFILL_DONE, true)
                .putLong(KEY_LAST_SYNC_TS, newest)
                .apply()
            Log.i(TAG, "Backfilled ${messages.size} SMS messages (14 days)")
        } catch (e: Exception) {
            Log.e(TAG, "Backfill failed", e)
        }
    }

    /**
     * Push new messages since the last sync. Called when a new SMS notification
     * arrives (from VessenceNotificationListener) or periodically.
     * Only uploads messages newer than the last synced timestamp.
     */
    suspend fun pushNewMessages(context: Context) {
        if (!hasPermission(context)) return
        try {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val lastTs = prefs.getLong(KEY_LAST_SYNC_TS, 0L)
            if (lastTs == 0L) {
                // No previous sync — do a backfill instead
                backfillIfNeeded(context)
                return
            }
            // Query messages newer than last sync (with 1-second overlap for safety)
            val messages = querySmsSince(context, lastTs - 1000)
            if (messages.isEmpty()) {
                Log.d(TAG, "No new SMS messages since last sync")
                return
            }
            uploadMessages(messages)
            val newest = messages.maxOfOrNull { (it["timestamp_ms"] as? Long) ?: 0L } ?: lastTs
            prefs.edit().putLong(KEY_LAST_SYNC_TS, newest).apply()
            Log.i(TAG, "Pushed ${messages.size} new SMS message(s) to server")
        } catch (e: Exception) {
            Log.e(TAG, "Push sync failed", e)
        }
    }

    /**
     * Force full re-sync of last 14 days.
     * Returns the number of messages found (and uploaded).
     * Throws on upload failure so the caller can report the real error.
     */
    suspend fun forceSync(context: Context): Int {
        if (!hasPermission(context)) {
            Log.w(TAG, "forceSync: READ_SMS permission not granted — aborting")
            return 0
        }
        val sinceMs = System.currentTimeMillis() - DAYS_TO_SYNC * 24 * 60 * 60 * 1000L
        Log.d(TAG, "forceSync: querying SMS since ${sinceMs} (last $DAYS_TO_SYNC days)")
        val messages = querySmsSince(context, sinceMs)
        Log.i(TAG, "forceSync: querySmsSince returned ${messages.size} message(s)")
        if (messages.isEmpty()) {
            Log.i(TAG, "forceSync: 0 messages found — nothing to upload")
            return 0
        }
        try {
            uploadMessages(messages)
        } catch (e: Exception) {
            Log.e(TAG, "forceSync: uploadMessages failed for ${messages.size} messages", e)
            throw e
        }
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val newest = messages.maxOfOrNull { (it["timestamp_ms"] as? Long) ?: 0L } ?: 0L
        prefs.edit()
            .putBoolean(KEY_BACKFILL_DONE, true)
            .putLong(KEY_LAST_SYNC_TS, newest)
            .apply()
        Log.i(TAG, "forceSync: completed — synced ${messages.size} SMS messages")
        return messages.size
    }

    /**
     * Query both content://sms/inbox AND content://sms/sent for messages since [sinceMs].
     * Inbox = received messages, Sent = messages the user sent.
     */
    private suspend fun querySmsSince(context: Context, sinceMs: Long): List<Map<String, Any?>> =
        withContext(Dispatchers.IO) {
            val numberToName = buildNumberToNameCache(context)
            val messages = mutableListOf<Map<String, Any?>>()

            // Query both inbox and sent
            for ((uriStr, msgType) in listOf("content://sms/inbox" to "received", "content://sms/sent" to "sent")) {
                val uri = Uri.parse(uriStr)
                val projection = arrayOf("address", "body", "date", "read")

                val cursor: Cursor? = context.contentResolver.query(
                    uri, projection, "date > ?", arrayOf(sinceMs.toString()),
                    "date DESC LIMIT $MAX_MESSAGES",
                )

                cursor?.use { c ->
                    val addrIdx = c.getColumnIndexOrThrow("address")
                    val bodyIdx = c.getColumnIndexOrThrow("body")
                    val dateIdx = c.getColumnIndexOrThrow("date")
                    val readIdx = c.getColumnIndexOrThrow("read")

                    while (c.moveToNext()) {
                        val address = c.getString(addrIdx) ?: continue
                        val body = c.getString(bodyIdx) ?: continue
                        if (NotificationSafety.looksLikeOtp(body)) continue
                        if (NotificationSafety.isPlaceholderBody(body)) continue

                        val resolved = numberToName[normalizeNumber(address)]
                            ?: numberToName[address]
                        val senderName = if (msgType == "sent") "Me → ${resolved ?: address}" else (resolved ?: address)
                        val isContact = resolved != null

                        messages.add(mapOf(
                            "sender" to senderName,
                            "body" to body.take(NotificationSafety.MAX_BODY_CHARS),
                            "timestamp_ms" to c.getLong(dateIdx),
                            "is_read" to (c.getInt(readIdx) == 1),
                            "is_contact" to isContact,
                        ))
                    }
                }
            }
            // Sort by timestamp descending and cap
            messages.sortByDescending { (it["timestamp_ms"] as? Long) ?: 0L }
            if (messages.size > MAX_MESSAGES) messages.subList(0, MAX_MESSAGES) else messages
        }

    private fun buildNumberToNameCache(ctx: Context): Map<String, String> {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_CONTACTS)
            != PackageManager.PERMISSION_GRANTED) return emptyMap()
        val map = mutableMapOf<String, String>()
        try {
            ctx.contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME),
                null, null, null,
            )?.use { cursor ->
                val numIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER)
                val nameIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                while (cursor.moveToNext()) {
                    val number = cursor.getString(numIdx)?.trim() ?: continue
                    val name = cursor.getString(nameIdx) ?: continue
                    map[normalizeNumber(number)] = name
                    map[number] = name
                }
            }
        } catch (e: Exception) { Log.w(TAG, "buildNumberToNameCache failed", e) }
        return map
    }

    private suspend fun uploadMessages(messages: List<Map<String, Any?>>) {
        withContext(Dispatchers.IO) {
            Log.d(TAG, "uploadMessages: uploading ${messages.size} message(s) to server")
            val response = ApiClient.janeApi.syncMessages(messages)
            if (response.isSuccessful) {
                Log.i(TAG, "uploadMessages: success (${response.code()}) — body: ${response.body()}")
            } else {
                val errorBody = response.errorBody()?.string() ?: "(no body)"
                Log.e(TAG, "uploadMessages: failed with HTTP ${response.code()} — $errorBody")
                throw RuntimeException("SMS upload failed: HTTP ${response.code()} — $errorBody")
            }
        }
    }

    private fun normalizeNumber(number: String): String =
        number.replace(Regex("[^0-9+]"), "").let {
            if (it.startsWith("+1") && it.length == 12) it.substring(2) else it
        }

    // ── Periodic sync ──────────────────────────────────────────────────────────

    private const val PERIODIC_SYNC_INTERVAL_MS = 5 * 60 * 1000L  // 5 minutes
    @Volatile private var periodicRunning = false

    /**
     * Start a background coroutine that syncs new messages every 5 minutes.
     * Catches sent messages (no notification for those) and fills gaps if
     * the notification listener was killed by the system.
     * Safe to call multiple times — only one loop runs at a time.
     */
    fun startPeriodicSync(context: Context) {
        if (periodicRunning) return
        periodicRunning = true
        val scope = kotlinx.coroutines.CoroutineScope(
            Dispatchers.IO + SupervisorJob()
        )
        scope.launch {
            Log.i(TAG, "Periodic SMS sync started (every ${PERIODIC_SYNC_INTERVAL_MS / 1000}s)")
            while (true) {
                delay(PERIODIC_SYNC_INTERVAL_MS)
                try {
                    pushNewMessages(context)
                } catch (e: Exception) {
                    Log.d(TAG, "Periodic sync failed: ${e.message}")
                }
            }
        }
    }

    private fun hasPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) ==
            PackageManager.PERMISSION_GRANTED
}
