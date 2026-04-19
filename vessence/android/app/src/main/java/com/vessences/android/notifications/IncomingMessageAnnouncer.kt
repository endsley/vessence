package com.vessences.android.notifications

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.util.Log
import com.vessences.android.util.ChatPreferences
import com.vessences.android.voice.AndroidTtsManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Event-driven SMS announcer for Android Jane.
 *
 * When [VessenceNotificationListener.handlePosted] sees a new messaging-app
 * notification, it records it into [RecentMessagesBuffer] for Jane's later
 * reasoning AND (via this object) speaks a short announcement through the
 * phone's local TTS so the user hears something within ~1 second instead of
 * waiting for a Jane chat turn.
 *
 * Design (job 073, 2026-04-18):
 *  - Process-wide singleton — notification callbacks are service-scope, not
 *    ChatViewModel-scope, so a per-ViewModel TTS won't cover this path.
 *  - Owns its own [AndroidTtsManager] instance. Reusing ChatViewModel's
 *    manager would require passing it into the notification service, which
 *    has a separate lifetime.
 *  - Applies [NotificationSafety] before speaking (OTP/placeholder/empty
 *    body already filtered there — do not duplicate the regex here).
 *  - Dedupes repeat notification updates via a short TTL LRU keyed on
 *    `sender|body|package` (SpeakThat pattern — no timestamp so updated
 *    notifications de-dupe correctly; see research notes in
 *    `configs/job_queue/073_event_driven_sms_tts.md`).
 *  - Requests `AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK` so music/podcasts duck
 *    instead of pause, abandons focus on TTS done (Voice Notify pattern).
 *  - Lock-screen policy: sender-only if phone is locked, sender+body when
 *    unlocked. v1 is hardcoded; a future job adds user-facing toggles.
 *  - Gated by [ChatPreferences.isIncomingMessageAnnounceEnabled] — default
 *    OFF so an APK update doesn't suddenly start speaking messages aloud.
 *
 * References:
 *  - https://github.com/pilot51/voicenotify (Apache-2.0 reference impl)
 *  - https://github.com/mitchib1440/SpeakThat (GPL-3.0 modern impl)
 *  - https://developer.android.com/media/optimize/audio-focus
 */
object IncomingMessageAnnouncer {

    private const val TAG = "IncomingMessageAnnouncer"

    // Dedupe cache — bounded LRU with TTL. Small by design: only catches
    // the "same SMS notification got reposted within a minute" pattern.
    // Keyed on normalized `sender|body|package`; NO timestamp so Android
    // re-posts of the same message still match.
    private const val DEDUPE_MAX_ENTRIES = 64
    private const val DEDUPE_TTL_MS = 5 * 60 * 1000L
    private val dedupe = object : LinkedHashMap<String, Long>(DEDUPE_MAX_ENTRIES, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Long>?): Boolean {
            return size > DEDUPE_MAX_ENTRIES
        }
    }
    private val dedupeLock = Any()

    // Own TTS manager — lazily created the first time we actually need to
    // speak, so "feature disabled" deployments never pay the init cost.
    // Volatile because notification callbacks can arrive on any thread.
    @Volatile
    private var tts: AndroidTtsManager? = null

    // Focus request is stateless between calls but caching it saves the
    // builder cost on every announcement.
    @Volatile
    private var focusRequest: AudioFocusRequest? = null

    // Dedicated supervisor scope so a failed TTS suspend doesn't propagate
    // into other coroutines.
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    /**
     * Called from [VessenceNotificationListener.handlePosted] after each
     * entry is recorded. Non-blocking — returns immediately; the actual
     * TTS work runs on [scope].
     */
    fun onMessagesPosted(ctx: Context, entries: List<RecentMessagesBuffer.Entry>) {
        if (entries.isEmpty()) return
        val appCtx = ctx.applicationContext
        if (!ChatPreferences(appCtx).isIncomingMessageAnnounceEnabled()) {
            Log.d(TAG, "sms_announce_skipped reason=preference_off count=${entries.size}")
            return
        }
        scope.launch {
            for (entry in entries) {
                try {
                    announce(appCtx, entry)
                } catch (e: Exception) {
                    Log.w(TAG, "announce crashed for entry", e)
                }
            }
        }
    }

    private suspend fun announce(ctx: Context, entry: RecentMessagesBuffer.Entry) {
        // ── Safety filters (OTP, placeholder, empty, own-package) ──────────
        val locked = NotificationSafety.isPhoneLocked(ctx)
        val safe = NotificationSafety.filterSafe(entry, locked)
        if (safe == null) {
            Log.d(TAG, "sms_announce_skipped reason=unsafe sender=${entry.sender.take(20)}")
            return
        }

        // ── Dedupe check — same sender+body+package within TTL ────────────
        val key = "${entry.sender.trim()}|${entry.body.trim()}|${entry.packageName}"
        val now = System.currentTimeMillis()
        synchronized(dedupeLock) {
            // Drop stale entries
            val it = dedupe.entries.iterator()
            while (it.hasNext()) {
                if (now - it.next().value > DEDUPE_TTL_MS) it.remove()
            }
            if (dedupe.containsKey(key)) {
                Log.d(TAG, "sms_announce_skipped reason=duplicate sender=${entry.sender.take(20)}")
                return
            }
            dedupe[key] = now
        }

        // ── Build the spoken line ──────────────────────────────────────────
        val sender = if (entry.sender.isBlank()) "someone" else entry.sender.trim()
        val bodyCapped = safe.body.trim().take(NotificationSafety.MAX_BODY_CHARS)
        val spoken = if (locked || bodyCapped.isEmpty()) {
            "New text from $sender."
        } else {
            "New text from $sender: $bodyCapped"
        }

        Log.i(TAG, "sms_announce_started sender=${sender.take(20)} locked=$locked len=${spoken.length}")

        // ── Audio focus: MAY_DUCK / speech content ─────────────────────────
        val audioMan = ctx.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
        val focus = audioMan?.let { requestFocus(it) } ?: false

        // ── Speak (suspends until TTS engine signals done / error) ─────────
        try {
            val engine = getOrCreateTts(ctx)
            engine.speak(spoken)
            Log.i(TAG, "sms_announce_spoken len=${spoken.length}")
        } finally {
            if (focus) audioMan?.let { releaseFocus(it) }
        }
    }

    private fun getOrCreateTts(ctx: Context): AndroidTtsManager {
        val existing = tts
        if (existing != null) return existing
        synchronized(this) {
            val again = tts
            if (again != null) return again
            val created = AndroidTtsManager(ctx.applicationContext)
            tts = created
            return created
        }
    }

    private fun buildFocusRequest(): AudioFocusRequest? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return null
        val cached = focusRequest
        if (cached != null) return cached
        synchronized(this) {
            val again = focusRequest
            if (again != null) return again
            val built = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .build()
            focusRequest = built
            return built
        }
    }

    private suspend fun requestFocus(audioMan: AudioManager): Boolean {
        return withContext(Dispatchers.Main.immediate) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val req = buildFocusRequest() ?: return@withContext false
                audioMan.requestAudioFocus(req) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            } else {
                @Suppress("DEPRECATION")
                audioMan.requestAudioFocus(
                    null,
                    AudioManager.STREAM_MUSIC,
                    AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK,
                ) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            }
        }
    }

    private suspend fun releaseFocus(audioMan: AudioManager) {
        withContext(Dispatchers.Main.immediate) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                buildFocusRequest()?.let { audioMan.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                audioMan.abandonAudioFocus(null)
            }
        }
    }
}
