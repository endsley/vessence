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

    fun signal() {
        _activated.value = true
    }

    fun consume() {
        _activated.value = false
    }
}
