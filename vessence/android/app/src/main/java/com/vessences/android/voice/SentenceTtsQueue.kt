package com.vessences.android.voice

import android.media.MediaPlayer
import android.util.Log
import com.vessences.android.data.api.ApiClient
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Sentence-level TTS streaming: accepts sentences one at a time,
 * generates WAV for each via the XTTS-v2 server, and plays them
 * back sequentially. Generation and playback overlap — sentence N+1
 * generates while sentence N plays.
 */
class SentenceTtsQueue(
    private val cacheDir: File,
    private val scope: CoroutineScope,
) {
    companion object {
        private const val TAG = "SentenceTtsQueue"
        private const val TTS_GENERATE_PATH = "/api/tts-server/generate"
        private const val TTS_HEALTH_PATH = "/api/tts-server/health"

        private fun getBaseUrl(): String = ApiClient.getJaneBaseUrl().trimEnd('/')
    }

    private val httpClient = ApiClient.getOkHttpClient().newBuilder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    private val healthClient = ApiClient.getOkHttpClient().newBuilder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(3, TimeUnit.SECONDS)
        .build()

    private var playbackQueue = Channel<File>(capacity = 8)
    private val cancelled = AtomicBoolean(false)
    private var playbackJob: Job? = null
    private val currentPlayer = java.util.concurrent.atomic.AtomicReference<MediaPlayer?>(null)
    private val _modelWarm = AtomicBoolean(false)

    val isModelWarm: Boolean get() = _modelWarm.get()

    /** Check model health (blocking, call from IO). */
    fun checkWarm(): Boolean {
        return try {
            val request = Request.Builder().url("${getBaseUrl()}$TTS_HEALTH_PATH").get().build()
            val response = healthClient.newCall(request).execute()
            val body = response.body?.string() ?: return false
            val loaded = JSONObject(body).optBoolean("model_loaded", false)
            _modelWarm.set(loaded)
            loaded
        } catch (_: Exception) {
            _modelWarm.set(false)
            false
        }
    }

    /** Start the playback consumer loop. Call once before feeding sentences. */
    fun startPlayback() {
        cancelled.set(false)
        playbackQueue = Channel(capacity = 8)  // fresh channel for each session
        playbackJob = scope.launch(Dispatchers.Main) {
            for (wavFile in playbackQueue) {
                if (cancelled.get()) {
                    wavFile.delete()
                    continue
                }
                try {
                    playWav(wavFile)
                } finally {
                    wavFile.delete()
                }
            }
        }
    }

    /**
     * Submit a sentence for TTS generation. Returns immediately.
     * The WAV will be queued for playback when ready.
     */
    fun submitSentence(text: String) {
        if (text.isBlank() || cancelled.get()) return
        scope.launch(Dispatchers.IO) {
            val wavFile = generateWav(text)
            if (wavFile != null && !cancelled.get()) {
                playbackQueue.send(wavFile)
            }
        }
    }

    /** Signal that no more sentences will be submitted. */
    fun finishSubmitting() {
        scope.launch {
            playbackQueue.close()
        }
    }

    /** Wait for all queued audio to finish playing. */
    suspend fun awaitCompletion() {
        playbackJob?.join()
    }

    fun stop() {
        cancelled.set(true)
        currentPlayer.getAndSet(null)?.let { mp ->
            try {
                if (mp.isPlaying) mp.stop()
                mp.release()
            } catch (_: Exception) {}
        }
        playbackQueue.close()
        playbackJob?.cancel()
    }

    private fun generateWav(text: String): File? {
        val url = "${getBaseUrl()}$TTS_GENERATE_PATH"
        val jsonBody = """{"text":${escapeJson(text)}}"""
        return try {
            Log.d(TAG, "Generating: ${text.take(60)}...")
            val request = Request.Builder()
                .url(url)
                .post(jsonBody.toByteArray().toRequestBody("application/json".toMediaType()))
                .build()
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                Log.w(TAG, "Generate failed: ${response.code}")
                response.close()
                return null
            }
            val ct = response.header("Content-Type", "") ?: ""
            if (ct.contains("text/html") || ct.contains("application/json")) {
                Log.w(TAG, "Generate returned $ct, not audio")
                response.close()
                return null
            }
            val wavFile = File(cacheDir, "tts_sent_${System.currentTimeMillis()}.wav")
            wavFile.outputStream().use { out ->
                response.body?.byteStream()?.use { it.copyTo(out) }
            }
            if (wavFile.length() < 100) {
                wavFile.delete()
                return null
            }
            Log.d(TAG, "Generated: ${wavFile.name}, ${wavFile.length()} bytes")
            wavFile
        } catch (e: Exception) {
            Log.w(TAG, "Generate error: ${e.message}")
            null
        }
    }

    private suspend fun playWav(file: File) {
        if (cancelled.get()) return
        withContext(Dispatchers.Main) {
            suspendCancellableCoroutine { cont ->
                val mp = MediaPlayer()
                currentPlayer.set(mp)
                try {
                    mp.setDataSource(file.absolutePath)
                    mp.setOnCompletionListener {
                        currentPlayer.set(null)
                        it.release()
                        if (cont.isActive) cont.resume(Unit) {}
                    }
                    mp.setOnErrorListener { _, what, extra ->
                        Log.e(TAG, "Playback error: what=$what extra=$extra")
                        currentPlayer.set(null)
                        mp.release()
                        if (cont.isActive) cont.resume(Unit) {}
                        true
                    }
                    mp.prepare()
                    mp.start()
                    cont.invokeOnCancellation {
                        currentPlayer.set(null)
                        try { mp.stop(); mp.release() } catch (_: Exception) {}
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Play setup error: ${e.message}")
                    currentPlayer.set(null)
                    try { mp.release() } catch (_: Exception) {}
                    if (cont.isActive) cont.resume(Unit) {}
                }
            }
        }
    }

    private fun escapeJson(s: String): String {
        val sb = StringBuilder("\"")
        for (c in s) {
            when (c) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                else -> sb.append(c)
            }
        }
        sb.append("\"")
        return sb.toString()
    }
}
