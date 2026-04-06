package com.vessences.android.voice

import android.media.MediaPlayer
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlin.coroutines.resume

/**
 * Plays TTS audio from the XTTS-v2 server using the /tts/generate endpoint (WAV)
 * and Android's MediaPlayer (proven playback path).
 *
 * Smart warm-check: queries /tts/health first. If model isn't loaded,
 * returns false immediately (caller falls back to Android TTS) and triggers
 * a background warm-up so subsequent calls are fast.
 */
class ServerTtsPlayer(private val cacheDir: File) {

    companion object {
        private const val TAG = "ServerTtsPlayer"

        /**
         * Direct URL to the TTS server. Uses local network IP since the TTS server
         * is not behind the Cloudflare tunnel. Change this if your server IP changes.
         */
        private const val TTS_BASE_URL = "http://192.168.86.21:8095"
        private const val TTS_GENERATE_PATH = "/tts/generate"
        private const val TTS_HEALTH_PATH = "/tts/health"
    }

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    private val healthClient = OkHttpClient.Builder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(2, TimeUnit.SECONDS)
        .build()

    private val cancelled = AtomicBoolean(false)
    private val currentPlayer = AtomicReference<MediaPlayer?>(null)
    private val warmingUp = AtomicBoolean(false)

    private fun isModelWarm(): Boolean {
        return try {
            val request = Request.Builder()
                .url("$TTS_BASE_URL$TTS_HEALTH_PATH")
                .get()
                .build()
            val response = healthClient.newCall(request).execute()
            if (!response.isSuccessful) {
                response.close()
                return false
            }
            val body = response.body?.string() ?: return false
            val json = JSONObject(body)
            val loaded = json.optBoolean("model_loaded", false)
            Log.d(TAG, "Health check: model_loaded=$loaded")
            loaded
        } catch (e: Exception) {
            Log.w(TAG, "Health check failed: ${e.message}")
            false
        }
    }

    private fun triggerWarmUp() {
        if (warmingUp.getAndSet(true)) return
        Thread {
            try {
                Log.d(TAG, "Triggering XTTS-v2 warm-up...")
                val request = Request.Builder()
                    .url("$TTS_BASE_URL$TTS_GENERATE_PATH")
                    .post("""{"text":"warm"}""".toByteArray()
                        .toRequestBody("application/json".toMediaType()))
                    .build()
                val warmClient = OkHttpClient.Builder()
                    .connectTimeout(5, TimeUnit.SECONDS)
                    .readTimeout(120, TimeUnit.SECONDS)
                    .build()
                val resp = warmClient.newCall(request).execute()
                resp.close()
                Log.d(TAG, "XTTS-v2 warm-up complete")
            } catch (e: Exception) {
                Log.w(TAG, "Warm-up failed: ${e.message}")
            } finally {
                warmingUp.set(false)
            }
        }.start()
    }

    /**
     * Generate TTS audio via /tts/generate (WAV), save to temp file, play with MediaPlayer.
     * Returns true if audio played successfully, false if server unreachable/cold/error.
     */
    suspend fun speak(text: String): Boolean = withContext(Dispatchers.IO) {
        cancelled.set(false)

        if (!isModelWarm()) {
            Log.d(TAG, "Model not warm, falling back to Android TTS and triggering warm-up")
            triggerWarmUp()
            return@withContext false
        }

        val url = "$TTS_BASE_URL$TTS_GENERATE_PATH"
        val jsonBody = """{"text":${escapeJson(text)}}"""
        val request = Request.Builder()
            .url(url)
            .post(jsonBody.toByteArray().toRequestBody("application/json".toMediaType()))
            .build()

        try {
            Log.d(TAG, "Requesting WAV from server (${text.take(50)}...)")
            val response = httpClient.newCall(request).execute()

            if (cancelled.get()) {
                response.close()
                return@withContext false
            }

            if (!response.isSuccessful) {
                Log.w(TAG, "Server TTS returned ${response.code}")
                response.close()
                return@withContext false
            }

            val body = response.body ?: run {
                Log.w(TAG, "Empty response body")
                response.close()
                return@withContext false
            }

            // Save WAV to temp file
            val wavFile = File(cacheDir, "tts_${System.currentTimeMillis()}.wav")
            wavFile.outputStream().use { out ->
                body.byteStream().use { input ->
                    input.copyTo(out)
                }
            }

            val fileSize = wavFile.length()
            Log.d(TAG, "WAV saved: ${wavFile.name}, ${fileSize} bytes")

            if (fileSize < 100) {
                Log.w(TAG, "WAV file too small ($fileSize bytes), likely error")
                wavFile.delete()
                return@withContext false
            }

            if (cancelled.get()) {
                wavFile.delete()
                return@withContext false
            }

            // Play with MediaPlayer
            val success = playWavFile(wavFile)
            wavFile.delete()
            return@withContext success

        } catch (e: Exception) {
            if (!cancelled.get()) {
                Log.w(TAG, "Server TTS failed: ${e.message}")
            }
            return@withContext false
        }
    }

    fun stop() {
        cancelled.set(true)
        currentPlayer.getAndSet(null)?.let { mp ->
            try {
                if (mp.isPlaying) mp.stop()
                mp.release()
            } catch (_: Exception) {}
        }
    }

    private suspend fun playWavFile(file: File): Boolean {
        if (cancelled.get()) return false

        return withContext(Dispatchers.Main) {
            suspendCancellableCoroutine { continuation ->
                val mp = MediaPlayer()
                currentPlayer.set(mp)

                try {
                    mp.setDataSource(file.absolutePath)
                    mp.setOnCompletionListener {
                        currentPlayer.set(null)
                        it.release()
                        if (continuation.isActive) continuation.resume(true)
                    }
                    mp.setOnErrorListener { _, what, extra ->
                        Log.e(TAG, "MediaPlayer error: what=$what extra=$extra")
                        currentPlayer.set(null)
                        mp.release()
                        if (continuation.isActive) continuation.resume(false)
                        true
                    }
                    mp.prepare()
                    Log.d(TAG, "Playing WAV: duration=${mp.duration}ms")
                    mp.start()

                    continuation.invokeOnCancellation {
                        currentPlayer.set(null)
                        try {
                            mp.stop()
                            mp.release()
                        } catch (_: Exception) {}
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "MediaPlayer setup failed: ${e.message}")
                    currentPlayer.set(null)
                    try { mp.release() } catch (_: Exception) {}
                    if (continuation.isActive) continuation.resume(false)
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
