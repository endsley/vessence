package com.vessences.android

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Simple one-shot flag: set by VessencesApp when wake word navigates to Jane,
 * consumed by JaneChatScreen to launch STT.
 * Single writer (VessencesApp), single reader (JaneChatScreen).
 */
object WakeWordPendingFlag {
    private val _pending = MutableStateFlow(false)
    val pending: StateFlow<Boolean> = _pending

    fun set() { _pending.value = true }
    fun consume() { _pending.value = false }
}
