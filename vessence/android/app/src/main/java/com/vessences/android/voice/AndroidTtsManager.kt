package com.vessences.android.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.util.Locale
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import kotlin.coroutines.resume

class AndroidTtsManager(
    context: Context,
) : TextToSpeech.OnInitListener {
    private val appContext = context.applicationContext
    private val pending = ConcurrentHashMap<String, CancellableContinuation<Unit>>()
    private val initWaiters = mutableListOf<CancellableContinuation<Unit>>()
    private var isInitialized = false
    private var initError: String? = null

    private val textToSpeech = TextToSpeech(appContext, this).apply {
        setOnUtteranceProgressListener(
            object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) = Unit

                override fun onDone(utteranceId: String?) {
                    utteranceId?.let { pending.remove(it)?.resume(Unit) }
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    utteranceId?.let { pending.remove(it)?.resume(Unit) }
                }

                override fun onError(utteranceId: String?, errorCode: Int) {
                    utteranceId?.let { pending.remove(it)?.resume(Unit) }
                }

                // API 23+: fired when an utterance is INTERRUPTED (e.g., another
                // speak() with QUEUE_FLUSH replaced it). Without this handler,
                // the interrupted utterance's continuation hangs forever because
                // neither onDone nor onError fires for it.
                override fun onStop(utteranceId: String?, interrupted: Boolean) {
                    utteranceId?.let { pending.remove(it)?.resume(Unit) }
                }
            }
        )
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            textToSpeech.language = Locale.US
            isInitialized = true
        } else {
            initError = "Text-to-speech unavailable"
        }
        initWaiters.toList().forEach { it.resume(Unit) }
        initWaiters.clear()
    }

    suspend fun speak(text: String) {
        if (text.isBlank()) return
        awaitReady()
        if (!isInitialized) return

        withContext(Dispatchers.Main.immediate) {
            suspendCancellableCoroutine { continuation ->
                val utteranceId = UUID.randomUUID().toString()
                pending[utteranceId] = continuation
                continuation.invokeOnCancellation { pending.remove(utteranceId) }
                textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
            }
        }
    }

    fun stop() {
        // Resume ALL pending continuations BEFORE stopping the engine.
        // TextToSpeech.stop() cancels all queued utterances, but Android
        // only fires onError for the CURRENTLY PLAYING utterance — silently
        // dropped queued utterances get NO callback. Any coroutine suspended
        // on a dropped utterance's ID would hang forever. This caused the
        // tool-handler TTS deadlock: chat TTS called stop() mid-tool-utterance,
        // the tool's continuation never resumed, the handler never completed,
        // and PendingToolResultBuffer never received the result.
        val orphaned = pending.keys.toList()
        for (id in orphaned) {
            pending.remove(id)?.resume(Unit)
        }
        textToSpeech.stop()
    }

    fun shutdown() {
        stop()
        textToSpeech.shutdown()
        pending.values.forEach { it.resume(Unit) }
        pending.clear()
    }

    private suspend fun awaitReady() {
        if (isInitialized || initError != null) return
        withContext(Dispatchers.Main.immediate) {
            suspendCancellableCoroutine<Unit> { continuation ->
                initWaiters += continuation
            }
        }
    }
}
