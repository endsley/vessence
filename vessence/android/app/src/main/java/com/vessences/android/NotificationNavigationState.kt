package com.vessences.android

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Observable state holder for notification/wake-word triggered navigation.
 * When a chat notification is tapped or wake word fires, the service sets
 * pendingChatTarget and VessencesApp navigates reactively.
 */
object NotificationNavigationState {
    private val _pendingTarget = MutableStateFlow<String?>(null)
    val pendingTarget: StateFlow<String?> = _pendingTarget

    var pendingChatTarget: String?
        get() = _pendingTarget.value
        set(value) { _pendingTarget.value = value }

    fun consumeTarget(): String? {
        val target = _pendingTarget.value
        _pendingTarget.value = null
        return target
    }
}
