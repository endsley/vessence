package com.vessences.android

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent

/**
 * Simple bus for STT results and listening state. MainActivity posts results here,
 * ChatViewModel reads them.
 *
 * Callbacks:
 *  - onResult       : called with the final transcript (null = cancelled/no-speech)
 *  - onListening    : true when the headless recognizer starts, false when it stops
 *  - onPartialResult: real-time partial transcript as the user speaks
 */
object SttResultBus {
    var onResult: ((String?) -> Unit)? = null
    /** true = recognizer is active/listening, false = stopped */
    var onListening: ((Boolean) -> Unit)? = null
    /** Partial (real-time) transcript while the user is speaking */
    var onPartialResult: ((String) -> Unit)? = null

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
