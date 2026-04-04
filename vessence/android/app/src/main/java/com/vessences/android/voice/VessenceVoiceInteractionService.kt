package com.vessences.android.voice

import android.service.voice.VoiceInteractionService
import android.util.Log

/**
 * System-level voice interaction service. When Vessence is set as the Default
 * Digital Assistant, Android grants privileged mic access (CAPTURE_AUDIO_HOTWORD)
 * which allows wake word detection even when the screen is off.
 *
 * This service is minimal — the actual wake word detection is still done by
 * AlwaysListeningService. This just registers us with the system.
 */
class VessenceVoiceInteractionService : VoiceInteractionService() {

    companion object {
        private const val TAG = "VessenceVIS"
    }

    override fun onReady() {
        super.onReady()
        Log.i(TAG, "VoiceInteractionService ready — Vessence is the default assistant")
        // Start always-listening if enabled
        val voiceSettings = com.vessences.android.data.repository.VoiceSettingsRepository(applicationContext)
        if (voiceSettings.isAlwaysListeningEnabled()) {
            AlwaysListeningService.start(applicationContext)
        }
    }

    override fun onShutdown() {
        Log.i(TAG, "VoiceInteractionService shutting down")
        AlwaysListeningService.stop(applicationContext)
        super.onShutdown()
    }
}
