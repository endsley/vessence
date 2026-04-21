package com.vessences.android.tools

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Telephony
import android.util.Log
import androidx.core.content.ContextCompat
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.vessences.android.notifications.NotificationSafety
import com.vessences.android.notifications.VessenceNotificationListener
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Handler for `messages.dismiss` — delete SMS messages and dismiss their
 * notifications by phone number.
 *
 * Two-phase approach:
 *  1. Delete the actual SMS thread(s) from the phone's SMS database via
 *     ContentResolver. This requires the app to hold READ_SMS and to have
 *     write access (default SMS app on Android 4.4+). If write access is
 *     denied, phase 1 is skipped and the result reports it.
 *  2. Dismiss any matching notifications from the shade via the
 *     NotificationListenerService.
 *
 * Args:
 *   addresses: JsonArray of phone number strings to delete.
 *              Matches against the SMS "address" column.
 *   senders:   (fallback) JsonArray of sender name patterns — used only
 *              for notification dismissal when phone numbers aren't known.
 *
 * Example:
 *   [[CLIENT_TOOL:messages.dismiss:{"addresses":["+16173134568","+14405975375","898287"]}]]
 */
object MessagesDismissHandler : ClientToolHandler {

    override val name: String = "messages.dismiss"

    private const val TAG = "MessagesDismiss"
    private val SMS_URI: Uri = Telephony.Sms.CONTENT_URI

    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        val addressesEl = call.args.get("addresses")
        val addresses: List<String> = if (addressesEl != null && addressesEl.isJsonArray) {
            addressesEl.asJsonArray.mapNotNull { it.asSafeString()?.trim() }
                .filter { it.isNotEmpty() }
        } else {
            val single = call.args.requireString("address")
            if (single != null) listOf(single) else emptyList()
        }

        val sendersEl = call.args.get("senders")
        val senderPatterns: List<String> = if (sendersEl != null && sendersEl.isJsonArray) {
            sendersEl.asJsonArray.mapNotNull { it.asSafeString()?.lowercase()?.trim() }
                .filter { it.isNotEmpty() }
        } else {
            val single = call.args.requireString("sender")
            if (single != null) listOf(single.lowercase()) else emptyList()
        }

        if (addresses.isEmpty() && senderPatterns.isEmpty()) {
            return ToolActionStatus.Failed("must provide 'addresses' (phone numbers) or 'senders' (name patterns)")
        }

        // Phase 1: Delete SMS from the phone's database
        val smsResult = if (addresses.isNotEmpty()) {
            deleteSmsMessages(ctx, addresses)
        } else {
            SmsDeleteResult(0, false, "no addresses provided — skipped SMS deletion")
        }

        // Phase 2: Dismiss notifications from the shade
        val notifResult = dismissNotifications(ctx, addresses, senderPatterns)

        val payload = JsonObject().apply {
            addProperty("sms_deleted", smsResult.deletedCount)
            addProperty("sms_access", !smsResult.accessDenied)
            if (smsResult.accessDenied) {
                addProperty("sms_error", smsResult.message)
            }
            addProperty("notifications_dismissed", notifResult.dismissedCount)
            add("affected_senders", JsonArray().apply {
                notifResult.senders.forEach { add(it) }
            })
        }

        val parts = mutableListOf<String>()
        if (smsResult.deletedCount > 0) {
            parts.add("deleted ${smsResult.deletedCount} SMS messages")
        }
        if (notifResult.dismissedCount > 0) {
            parts.add("dismissed ${notifResult.dismissedCount} notifications")
        }
        if (smsResult.accessDenied) {
            parts.add("SMS write access denied — app must be set as default messaging app to delete SMS")
        }
        if (parts.isEmpty()) {
            parts.add("no matching messages or notifications found")
        }

        val summary = parts.joinToString("; ")
        Log.i(TAG, summary)
        return ToolActionStatus.CompletedWithData(summary, payload)
    }

    private data class SmsDeleteResult(
        val deletedCount: Int,
        val accessDenied: Boolean,
        val message: String,
    )

    private suspend fun deleteSmsMessages(ctx: Context, addresses: List<String>): SmsDeleteResult =
        withContext(Dispatchers.IO) {
            if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_SMS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                return@withContext SmsDeleteResult(0, true, "READ_SMS permission not granted")
            }

            var totalDeleted = 0
            var accessDenied = false
            val resolver = ctx.contentResolver

            for (address in addresses) {
                val normalized = normalizeNumber(address)
                try {
                    // Match SMS where address contains the number (handles format variations)
                    val deleted = resolver.delete(
                        SMS_URI,
                        "address LIKE ?",
                        arrayOf("%$normalized%"),
                    )
                    totalDeleted += deleted
                    Log.d(TAG, "deleted $deleted SMS from address matching $normalized")
                } catch (e: SecurityException) {
                    Log.w(TAG, "SMS delete denied for $normalized — not default SMS app", e)
                    accessDenied = true
                } catch (e: Exception) {
                    Log.w(TAG, "SMS delete failed for $normalized", e)
                }
            }

            SmsDeleteResult(
                totalDeleted,
                accessDenied,
                if (accessDenied) "not default SMS app — cannot delete SMS" else "ok",
            )
        }

    private fun normalizeNumber(address: String): String {
        return address.replace(Regex("[^0-9+]"), "")
            .removePrefix("+1")
            .takeLast(10)
    }

    private data class NotifDismissResult(
        val dismissedCount: Int,
        val senders: Set<String>,
    )

    private fun dismissNotifications(
        ctx: Context,
        addresses: List<String>,
        senderPatterns: List<String>,
    ): NotifDismissResult {
        if (!NotificationSafety.isListenerEnabled(ctx) ||
            !VessenceNotificationListener.connected.value
        ) {
            return NotifDismissResult(0, emptySet())
        }
        val listener = VessenceNotificationListener.liveInstance
            ?: return NotifDismissResult(0, emptySet())

        val active = try {
            listener.snapshotActiveMessages()
        } catch (e: Exception) {
            Log.e(TAG, "snapshotActiveMessages threw", e)
            return NotifDismissResult(0, emptySet())
        }

        val normalizedAddresses = addresses.map { normalizeNumber(it) }
        val allPatterns = senderPatterns + addresses.map { it.lowercase() }

        val matched = active.filter { entry ->
            val senderLower = entry.sender.lowercase()
            val bodyLower = entry.body.lowercase()
            val matchesPattern = allPatterns.any { p ->
                senderLower.contains(p) || bodyLower.contains(p)
            }
            val matchesNumber = normalizedAddresses.any { num ->
                normalizeNumber(entry.sender).endsWith(num) ||
                    senderLower.contains(num)
            }
            matchesPattern || matchesNumber
        }

        if (matched.isEmpty()) return NotifDismissResult(0, emptySet())

        val cancelledKeys = mutableSetOf<String>()
        val dismissedSenders = mutableSetOf<String>()
        for (entry in matched) {
            val realKey = entry.sbnKey.substringBefore("#")
            if (realKey !in cancelledKeys) {
                try {
                    listener.cancelNotification(realKey)
                    cancelledKeys.add(realKey)
                } catch (e: Exception) {
                    Log.w(TAG, "cancelNotification failed for key=$realKey", e)
                }
            }
            dismissedSenders.add(entry.sender)
        }

        return NotifDismissResult(matched.size, dismissedSenders)
    }
}
