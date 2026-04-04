package com.vessences.android

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent

/**
 * Simple bus for STT results. MainActivity posts results here,
 * ChatViewModel reads them.
 */
object SttResultBus {
    var onResult: ((String?) -> Unit)? = null

    fun postResult(resultCode: Int, data: Intent?) {
        if (resultCode == Activity.RESULT_OK) {
            val matches = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            val spoken = matches?.firstOrNull()
            onResult?.invoke(spoken)
        } else {
            onResult?.invoke(null)  // cancelled or failed
        }
    }
}
