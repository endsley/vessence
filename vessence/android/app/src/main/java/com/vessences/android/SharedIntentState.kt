package com.vessences.android

import android.net.Uri
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Singleton that holds URIs received via Android's Share-to intent.
 * MainActivity writes here; JaneChatScreen reads and clears after consumption.
 */
object SharedIntentState {
    private val _sharedUris = MutableStateFlow<List<Uri>>(emptyList())
    val sharedUris: StateFlow<List<Uri>> = _sharedUris

    private val _sharedText = MutableStateFlow<String?>(null)
    val sharedText: StateFlow<String?> = _sharedText

    fun setSharedUris(uris: List<Uri>) {
        _sharedUris.value = uris
    }

    fun setSharedText(text: String?) {
        _sharedText.value = text
    }

    fun clear() {
        _sharedUris.value = emptyList()
        _sharedText.value = null
    }
}
