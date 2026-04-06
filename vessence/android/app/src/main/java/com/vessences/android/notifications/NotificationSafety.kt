package com.vessences.android.notifications

import android.app.KeyguardManager
import android.content.ComponentName
import android.content.Context
import android.provider.Settings
import android.util.Log

/**
 * Shared safety filters for notification reading (both MessagesReadRecent
 * and MessagesFetchUnread).
 *
 * Before this existed, `isListenerEnabled`, `isPhoneLocked`, the OTP regex,
 * the placeholder-body detector, and the body-length cap were each duplicated
 * in both handler files. Any change to the OTP filter had to be made in two
 * places and would drift over time.
 *
 * This file is the single source of truth for "what counts as safe to read
 * from a notification buffer."
 */
object NotificationSafety {

    /** Maximum body length fed to TTS per message. Longer bodies are truncated. */
    const val MAX_BODY_CHARS = 400

    /** Placeholder bodies that lock-screen redaction substitutes. We never
     *  read these aloud because there's no real content. */
    private val PLACEHOLDER_BODIES = setOf(
        "new message",
        "new messages",
        "1 new message",
    )

    /**
     * OTP / verification code regex. Broad by design — better to skip a
     * benign message than read a 2FA code aloud in a shared room.
     *
     * Matches:
     *   - Keyword-anchored alphanumeric codes after "verification/otp/code/passcode/
     *     one-time/2fa/two-factor/security-code/confirmation"
     *   - Letter-prefixed codes like "G-123456", "A-12345" (Google style)
     *   - Plain 6-digit codes (SMS 2FA is almost always 6 digits)
     *   - 4-8 digit codes in proximity to the word "code"
     */
    val OTP_REGEX: Regex = Regex(
        buildString {
            append("""(?:verification|otp|code|passcode|one[- ]time|2fa|two[- ]factor|security[- ]code|confirmation)""")
            append("""[^\w\n]{0,30}[A-Z0-9][- ]?[A-Z0-9]{3,10}""")
            append("""|\b[A-Z]-\d{4,8}\b""")
            append("""|\b\d{6}\b""")
            append("""|\bcode[^\w\n]{0,10}\d{4,8}\b""")
            append("""|\b\d{4,8}[^\w\n]{0,10}code\b""")
        },
        RegexOption.IGNORE_CASE,
    )

    /** True if [body] is blank, a known placeholder, or a "N new messages" pattern. */
    fun isPlaceholderBody(body: String): Boolean {
        val trimmed = body.trim()
        if (trimmed.isBlank()) return true
        val lower = trimmed.lowercase()
        if (lower in PLACEHOLDER_BODIES) return true
        return lower.matches(Regex("""\d+ new messages?"""))
    }

    /** True if [body] matches an OTP / 2FA pattern and should NEVER be read aloud. */
    fun looksLikeOtp(body: String): Boolean = OTP_REGEX.containsMatchIn(body)

    /** True if the phone is currently locked with the keyguard. */
    fun isPhoneLocked(ctx: Context): Boolean {
        return try {
            val km = ctx.getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager
            km?.isKeyguardLocked == true
        } catch (e: Exception) {
            Log.w(TAG, "keyguard check failed", e)
            false
        }
    }

    /**
     * True if the user has granted notification-listener access to
     * [VessenceNotificationListener] via system settings. This cannot be
     * granted programmatically — only the user can flip the toggle in
     * Settings → Notifications → Notification access.
     */
    fun isListenerEnabled(ctx: Context): Boolean {
        return try {
            val flat = Settings.Secure.getString(
                ctx.contentResolver,
                "enabled_notification_listeners",
            ) ?: return false
            val target = ComponentName(ctx, VessenceNotificationListener::class.java)
            flat.split(":").any {
                it == target.flattenToString() || it == target.flattenToShortString()
            }
        } catch (e: Exception) {
            Log.w(TAG, "isListenerEnabled check failed", e)
            false
        }
    }

    /**
     * Apply every safety filter in sequence to an [Entry]. Returns the entry
     * unchanged if it's safe to read, or null if it should be skipped.
     *
     * [phoneLocked] should come from a single call to [isPhoneLocked] so the
     * check is consistent across the whole filter pass.
     */
    fun filterSafe(entry: RecentMessagesBuffer.Entry, phoneLocked: Boolean): RecentMessagesBuffer.Entry? {
        val body = entry.body
        if (body.isBlank()) return null
        if (isPlaceholderBody(body)) return null
        if (looksLikeOtp(body)) return null
        if (phoneLocked && body.trim().length < 3) return null
        return entry
    }

    private const val TAG = "NotificationSafety"
}
