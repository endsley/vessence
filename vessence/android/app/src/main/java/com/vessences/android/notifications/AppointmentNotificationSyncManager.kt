package com.vessences.android.notifications

import android.content.Context
import android.util.Log
import com.vessences.android.data.api.ApiClient

/**
 * Uploads appointment-looking message notifications into the existing
 * synced_messages server table.
 *
 * This covers Google Messages RCS/business chats that are visible on the phone
 * but never appear in Android's legacy content://sms provider.
 */
object AppointmentNotificationSyncManager {
    private const val TAG = "AppointmentNotifSync"

    private val appointmentSignals = listOf(
        "appointment",
        "appt",
        "upcoming visit",
        "scheduled",
        "confirmed",
        "confirmation",
        "reminder",
        "procedure",
        "arrive by",
        "please arrive",
        "check in",
    )

    private val medicalContexts = listOf(
        "doctor",
        "dr.",
        "dental",
        "dentist",
        "orthodont",
        "clinic",
        "hospital",
        "medical",
        "medicine",
        "tufts",
        "mychart",
        "mytuftsmed",
        "quest",
        "quest diagnostics",
        "diagnostic",
        "diagnostics",
        "lab",
        "laboratory",
        "blood",
        "specimen",
        "endoscopy",
        "procedure",
        "labcorp",
    )

    suspend fun uploadAppointmentCandidates(
        context: Context,
        entries: List<RecentMessagesBuffer.Entry>,
    ) {
        val candidates = entries
            .asSequence()
            .filter { looksLikeAppointmentCandidate(it) }
            .distinctBy { "${it.sender}|${it.timestamp}|${it.body}" }
            .map {
                mapOf(
                    "sender" to it.sender,
                    "body" to it.body.take(NotificationSafety.MAX_BODY_CHARS),
                    "timestamp_ms" to it.timestamp,
                    "is_read" to false,
                    "is_contact" to false,
                )
            }
            .toList()

        if (candidates.isEmpty()) return

        try {
            val api = try {
                ApiClient.janeApi
            } catch (_: UninitializedPropertyAccessException) {
                ApiClient.init(context.applicationContext)
                ApiClient.janeApi
            }
            val response = api.syncMessages(candidates)
            if (response.isSuccessful) {
                Log.i(TAG, "uploaded ${candidates.size} appointment notification candidate(s)")
            } else {
                Log.w(TAG, "upload failed: HTTP ${response.code()}")
            }
        } catch (e: Exception) {
            Log.w(TAG, "upload failed", e)
        }
    }

    private fun looksLikeAppointmentCandidate(entry: RecentMessagesBuffer.Entry): Boolean {
        if (entry.isReaction) return false
        val body = entry.body.trim()
        if (body.isEmpty()) return false
        if (NotificationSafety.looksLikeOtp(body)) return false
        if (NotificationSafety.isPlaceholderBody(body)) return false

        val haystack = "${entry.sender} $body".lowercase()
        val hasAppointmentSignal = appointmentSignals.any { haystack.contains(it) }
        val hasMedicalContext = medicalContexts.any { haystack.contains(it) }
        if (!hasAppointmentSignal || !hasMedicalContext) return false

        if ("rx" in haystack || "pharmacy" in haystack || "refill" in haystack) {
            return "appointment" in haystack || "visit" in haystack
        }
        return true
    }
}
