package com.vessences.android.voice

import android.os.Bundle
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import android.util.Log

/**
 * Creates voice interaction sessions when the system assistant is activated
 * (e.g., long-press home button). Launches the Jane chat screen.
 */
class VessenceVoiceInteractionSessionService : VoiceInteractionSessionService() {

    override fun onNewSession(args: Bundle?): VoiceInteractionSession {
        Log.i("VessenceVISS", "New voice interaction session")
        return VessenceVoiceInteractionSession(this)
    }
}

/**
 * Individual voice interaction session. When triggered (long-press home, etc.),
 * opens the Jane chat screen with wake word STT activated.
 */
class VessenceVoiceInteractionSession(context: android.content.Context) :
    VoiceInteractionSession(context) {

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        // Signal wake word bridge so chat screen auto-launches STT
        WakeWordBridge.signal()
        com.vessences.android.NotificationNavigationState.pendingChatTarget = "jane"

        // Use startVoiceActivity for proper assistant launch (avoids background-launch restrictions)
        val intent = android.content.Intent(context, com.vessences.android.MainActivity::class.java).apply {
            putExtra("open_chat", "jane")
            putExtra("wake_word", true)
        }
        startVoiceActivity(intent)
        finish()
    }
}
