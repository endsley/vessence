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
