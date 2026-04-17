package com.vessences.android.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Singleton bridge between AlwaysListeningService and the chat screen.
 * When the wake word is detected, the service signals here.
 * The chat screen picks it up and auto-activates the mic (STT).
 */
object WakeWordBridge {
    private val _activated = MutableStateFlow(false)
    val activated: StateFlow<Boolean> = _activated

    /** True while the chat screen's STT is using the mic — service must not record. */
    @Volatile
    var sttActive: Boolean = false

    /**
     * Epoch-millis when `launchStt()` was last called. Used by
     * `restoreAlwaysListening()` and `MainActivity.onResume()` as a race guard:
     * if AL is about to start within ~2s of a recent STT launch, the mic is
     * likely still being handed off by SpeechRecognizer, and starting AL
     * synchronously on the onError callback thread leaves AL's AudioRecord in
     * a zombie state (reads succeed but produce silence — see the 2026-04-16
     * jane-android-stt-dead investigation). Set by MainActivity.launchStt();
     * read by the AL-start paths. 0 = never launched in this app lifetime.
     */
    @Volatile
    var lastSttLaunchMs: Long = 0L

    fun signal() {
        _activated.value = true
    }

    fun consume() {
        _activated.value = false
    }
}
