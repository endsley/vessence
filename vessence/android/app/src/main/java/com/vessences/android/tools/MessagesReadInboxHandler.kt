package com.vessences.android.tools

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.database.Cursor
import android.net.Uri
import android.provider.ContactsContract
import android.util.Log
import androidx.core.content.ContextCompat
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.vessences.android.notifications.NotificationSafety
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Handler for `messages.read_inbox` — query the device's SMS content provider
 * (`content://sms/inbox`) to read ALL text messages, not just active notifications.
 *
 * This enables:
 *   - "read my texts" — fetch recent inbox messages regardless of notification state
 *   - "what did my wife text me?" — filter by sender contact name
 *   - "read messages from today" — time-based filtering
 *
 * Unlike [MessagesFetchUnreadHandler] (which reads active notifications),
 * this handler reads from the SMS database directly and can see already-read
 * and dismissed messages.
 *
 * Safety: OTP/2FA messages are filtered using the same [NotificationSafety]
 * regex. Sender phone numbers are resolved to contact names on-device via
 * the Contacts content provider — no phone numbers are sent to the server.
 */
object MessagesReadInboxHandler : ClientToolHandler {

    override val name: String = "messages.read_inbox"

    private const val DEFAULT_LIMIT = 20
    private const val MAX_LIMIT = 50
    private const val TAG = "MessagesReadInbox"

    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        // Permission gate: READ_SMS is required
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return ToolActionStatus.NeedsUser("READ_SMS permission not granted")
        }

        val limit = (call.args.get("limit").asSafeInt() ?: DEFAULT_LIMIT).coerceIn(1, MAX_LIMIT)
        val senderFilter = call.args.get("sender").asSafeString()?.trim()?.takeIf { it.isNotEmpty() }
        val sinceMs = call.args.get("since_ms").asSafeString()?.toLongOrNull()

        return withContext(Dispatchers.IO) {
            try {
                val messages = queryInbox(ctx, limit, senderFilter, sinceMs)
                val messagesArray = JsonArray()
                for (msg in messages) {
                    val obj = JsonObject().apply {
                        addProperty("sender", msg.senderName)
                        addProperty("body", msg.body.take(NotificationSafety.MAX_BODY_CHARS))
                        addProperty("timestamp", msg.timestamp)
                        addProperty("read", msg.read)
                    }
                    messagesArray.add(obj)
                }

                val payload = JsonObject().apply {
                    add("messages", messagesArray)
                    addProperty("count", messages.size)
                    addProperty("limit", limit)
                    if (senderFilter != null) addProperty("sender_filter", senderFilter)
                }

                Log.i(TAG, "read_inbox returning ${messages.size} messages" +
                    (if (senderFilter != null) " (filtered by '$senderFilter')" else ""))

                if (messages.isEmpty()) {
                    ToolActionStatus.CompletedWithData(
                        "no SMS messages found" +
                            (if (senderFilter != null) " from '$senderFilter'" else ""),
                        payload,
                    )
                } else {
                    ToolActionStatus.CompletedWithData(
                        "returned ${messages.size} SMS messages",
                        payload,
                    )
                }
            } catch (e: Exception) {
                Log.e(TAG, "queryInbox failed", e)
                ToolActionStatus.Failed("SMS inbox query failed: ${e.message}")
            }
        }
    }

    private data class SmsMessage(
        val senderName: String,
        val body: String,
        val timestamp: Long,
        val read: Boolean,
    )

    /**
     * Query content://sms/inbox for recent messages.
     *
     * If [senderFilter] is provided, resolve the contact name to phone numbers
     * first, then filter the query by those numbers. If the name doesn't match
     * any contact, fall back to a body-text scan of the results.
     *
     * If [sinceMs] is provided, only return messages newer than that epoch timestamp.
     */
    private fun queryInbox(
        ctx: Context,
        limit: Int,
        senderFilter: String?,
        sinceMs: Long?,
    ): List<SmsMessage> {
        // Build phone-number lookup cache for sender name resolution
        val numberToName = buildNumberToNameCache(ctx)

        // If filtering by sender, resolve to phone numbers first
        val filterNumbers: Set<String>? = if (senderFilter != null) {
            resolveContactNumbers(ctx, senderFilter)
        } else null

        val uri = Uri.parse("content://sms/inbox")
        val projection = arrayOf("address", "body", "date", "read")

        // Build selection clause
        val selectionParts = mutableListOf<String>()
        val selectionArgs = mutableListOf<String>()

        if (sinceMs != null) {
            selectionParts.add("date > ?")
            selectionArgs.add(sinceMs.toString())
        }

        // If we have specific numbers to filter by, add them to the query
        if (filterNumbers != null && filterNumbers.isNotEmpty()) {
            val placeholders = filterNumbers.joinToString(",") { "?" }
            selectionParts.add("address IN ($placeholders)")
            selectionArgs.addAll(filterNumbers)
        }

        val selection = if (selectionParts.isNotEmpty()) selectionParts.joinToString(" AND ") else null
        val args = if (selectionArgs.isNotEmpty()) selectionArgs.toTypedArray() else null

        // Query with a generous over-fetch to account for OTP filtering
        val overFetchLimit = (limit * 2).coerceAtMost(100)

        val cursor: Cursor? = ctx.contentResolver.query(
            uri, projection, selection, args,
            "date DESC LIMIT $overFetchLimit",
        )

        val results = mutableListOf<SmsMessage>()
        cursor?.use { c ->
            val addrIdx = c.getColumnIndexOrThrow("address")
            val bodyIdx = c.getColumnIndexOrThrow("body")
            val dateIdx = c.getColumnIndexOrThrow("date")
            val readIdx = c.getColumnIndexOrThrow("read")

            while (c.moveToNext() && results.size < limit) {
                val address = c.getString(addrIdx) ?: continue
                val body = c.getString(bodyIdx) ?: continue

                // Safety: skip OTP/2FA messages
                if (NotificationSafety.looksLikeOtp(body)) continue
                // Skip placeholder bodies
                if (NotificationSafety.isPlaceholderBody(body)) continue

                val timestamp = c.getLong(dateIdx)
                val isRead = c.getInt(readIdx) == 1

                // Resolve sender name from contacts, fall back to phone number
                val senderName = numberToName[normalizeNumber(address)]
                    ?: numberToName[address]
                    ?: address

                // If filtering by sender name but couldn't resolve to numbers,
                // do a name-based post-filter
                if (senderFilter != null && filterNumbers.isNullOrEmpty()) {
                    if (!senderName.contains(senderFilter, ignoreCase = true)) continue
                }

                results.add(SmsMessage(senderName, body, timestamp, isRead))
            }
        }

        return results
    }

    /**
     * Build a map of normalized phone number -> contact display name.
     * Uses READ_CONTACTS permission. If not available, returns empty map
     * (phone numbers will be shown as-is).
     */
    private fun buildNumberToNameCache(ctx: Context): Map<String, String> {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return emptyMap()
        }

        val map = mutableMapOf<String, String>()
        try {
            val uri = ContactsContract.CommonDataKinds.Phone.CONTENT_URI
            val projection = arrayOf(
                ContactsContract.CommonDataKinds.Phone.NUMBER,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            )
            ctx.contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
                val numIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER)
                val nameIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                while (cursor.moveToNext()) {
                    val number = cursor.getString(numIdx)?.trim() ?: continue
                    val name = cursor.getString(nameIdx) ?: continue
                    map[normalizeNumber(number)] = name
                    map[number] = name  // also store raw format
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "buildNumberToNameCache failed", e)
        }
        return map
    }

    /**
     * Resolve a contact name to a set of phone numbers using ContactsResolver's
     * existing tiered matching. Returns null if no matches found.
     */
    private fun resolveContactNumbers(ctx: Context, name: String): Set<String>? {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return null
        }

        try {
            val filterUri = Uri.withAppendedPath(
                ContactsContract.CommonDataKinds.Phone.CONTENT_FILTER_URI,
                Uri.encode(name.trim()),
            )
            val projection = arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER)
            val numbers = mutableSetOf<String>()
            ctx.contentResolver.query(filterUri, projection, null, null, null)?.use { cursor ->
                val numIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER)
                while (cursor.moveToNext()) {
                    val number = cursor.getString(numIdx)?.trim() ?: continue
                    numbers.add(normalizeNumber(number))
                    numbers.add(number)  // also add raw format for matching
                }
            }
            return numbers.takeIf { it.isNotEmpty() }
        } catch (e: Exception) {
            Log.w(TAG, "resolveContactNumbers failed for '$name'", e)
            return null
        }
    }

    /**
     * Strip non-digit characters for phone number matching.
     * "+1 (555) 123-4567" -> "15551234567"
     */
    private fun normalizeNumber(number: String): String =
        number.replace(Regex("[^0-9+]"), "").let {
            // Remove leading +1 for US numbers to match both formats
            if (it.startsWith("+1") && it.length == 12) it.substring(2) else it
        }
}
