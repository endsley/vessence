package com.vessences.android.util

import android.content.Context

/**
 * Persists per-chat settings (TTS enabled, etc.) across app restarts.
 */
class ChatPreferences(context: Context) {
    private val prefs = context.getSharedPreferences("chat_prefs", Context.MODE_PRIVATE)

    /** Shared Jane session ID — used by both ChatViewModel and AlwaysListeningService. */
    fun getJaneSessionId(): String {
        val existing = prefs.getString("jane_session_id", null)
        if (existing != null) return existing
        val newId = "jane_android_${java.util.UUID.randomUUID().toString().take(8)}"
        prefs.edit().putString("jane_session_id", newId).apply()
        return newId
    }

    fun resetJaneSessionId(): String {
        val newId = "jane_android_${java.util.UUID.randomUUID().toString().take(8)}"
        prefs.edit().putString("jane_session_id", newId).apply()
        return newId
    }

    fun isTtsEnabled(backendKey: String): Boolean =
        prefs.getBoolean("${backendKey}_tts_enabled", false)

    fun setTtsEnabled(backendKey: String, enabled: Boolean) {
        prefs.edit().putBoolean("${backendKey}_tts_enabled", enabled).apply()
    }

    fun getTtsVoice(): String =
        prefs.getString("tts_voice_name", "") ?: ""

    fun setTtsVoice(voiceName: String) {
        prefs.edit().putString("tts_voice_name", voiceName).apply()
    }

    fun isAutoListenEnabled(): Boolean =
        prefs.getBoolean("auto_listen_after_tts", true)  // default ON

    fun setAutoListenEnabled(enabled: Boolean) {
        prefs.edit().putBoolean("auto_listen_after_tts", enabled).apply()
    }
}
