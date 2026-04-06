package com.vessences.android.voice

import android.content.Context
import android.util.Log

/**
 * Hybrid TTS manager: tries server-side XTTS-v2 first for higher quality,
 * falls back to Android's built-in TTS if the server is unreachable or slow.
 *
 * To revert to Android-only TTS:
 *   - Set USE_SERVER_TTS = false below, OR
 *   - Stop the tts-server systemd service (auto-fallback, no rebuild needed)
 */
class HybridTtsManager(context: Context) {

    companion object {
        private const val TAG = "HybridTtsManager"

        /**
         * Master switch for server TTS. Set to false to instantly revert
         * to Android-only TTS without any other code changes.
         */
        const val USE_SERVER_TTS = true
    }

    /** Exposed so ActionQueue can use local TTS directly for instant tool feedback. */
    val localTts = AndroidTtsManager(context)

    private val serverTts = ServerTtsPlayer(context.applicationContext.cacheDir)

    /**
     * Call early during text streaming to pre-warm the model.
     * This way the model is hot by the time speak() is called.
     */
    fun ensureWarm() {
        if (USE_SERVER_TTS) {
            serverTts.ensureWarm()
        }
    }

    suspend fun speak(text: String) {
        if (text.isBlank()) return

        if (USE_SERVER_TTS) {
            Log.d(TAG, "Attempting server TTS (${text.take(50)}...)")
            val success = try {
                serverTts.speak(text)
            } catch (e: Exception) {
                Log.w(TAG, "Server TTS exception: ${e.message}")
                false
            }
            if (success) {
                Log.d(TAG, "Server TTS succeeded")
                return
            }
            Log.d(TAG, "Server TTS failed, falling back to Android TTS")
        }

        localTts.speak(text)
    }

    fun stop() {
        serverTts.stop()
        localTts.stop()
    }

    fun shutdown() {
        serverTts.stop()
        localTts.shutdown()
    }
}
