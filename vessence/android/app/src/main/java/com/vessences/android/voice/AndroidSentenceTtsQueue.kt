package com.vessences.android.voice

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Sequential sentence playback for local Android TTS.
 *
 * AndroidTtsManager.speak() uses QUEUE_FLUSH internally so external callers can
 * interrupt speech immediately. This queue keeps streaming reply sentences from
 * interrupting each other by waiting for each speak() call to finish before
 * starting the next sentence.
 */
class AndroidSentenceTtsQueue(
    private val tts: AndroidTtsManager,
    private val scope: CoroutineScope,
) {
    companion object {
        private const val TAG = "AndroidSentenceTtsQueue"
    }

    private var sentenceQueue = Channel<String>(capacity = Channel.UNLIMITED)
    private val cancelled = AtomicBoolean(false)
    private var playbackJob: Job? = null

    fun startPlayback() {
        cancelled.set(false)
        sentenceQueue = Channel(capacity = Channel.UNLIMITED)
        playbackJob = scope.launch {
            for (sentence in sentenceQueue) {
                if (cancelled.get()) continue
                try {
                    Log.i("ttsdbg", "sentence_tts_local_start chars=${sentence.length}")
                    tts.speak(sentence)
                    Log.i("ttsdbg", "sentence_tts_local_done chars=${sentence.length}")
                } catch (e: Exception) {
                    Log.w(TAG, "Sentence playback failed: ${e.message}")
                }
            }
        }
    }

    fun submitSentence(text: String) {
        val sentence = text.trim()
        if (sentence.isBlank() || cancelled.get()) return
        val result = sentenceQueue.trySend(sentence)
        if (result.isFailure) {
            Log.w(TAG, "Dropped sentence because queue is closed")
        } else {
            Log.i("ttsdbg", "sentence_tts_local_queued chars=${sentence.length}")
        }
    }

    fun finishSubmitting() {
        sentenceQueue.close()
    }

    suspend fun awaitCompletion() {
        playbackJob?.join()
    }

    fun stop() {
        cancelled.set(true)
        sentenceQueue.close()
        playbackJob?.cancel()
        playbackJob = null
        tts.stop()
    }
}
