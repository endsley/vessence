package com.vessences.android.voice

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/**
 * Streams PCM audio from the XTTS-v2 TTS server and plays it via AudioTrack.
 *
 * Smart warm-check: queries /tts/health first. If model isn't loaded,
 * returns false immediately (caller falls back to Android TTS) and triggers
 * a background warm-up request so subsequent calls are fast.
 */
class ServerTtsPlayer {

    companion object {
        private const val TAG = "ServerTtsPlayer"

        /**
         * Direct URL to the TTS server. Uses local network IP since the TTS server
         * is not behind the Cloudflare tunnel. Change this if your server IP changes.
         */
        private const val TTS_BASE_URL = "http://192.168.86.21:8095"
        private const val TTS_STREAM_PATH = "/tts/stream"
        private const val TTS_HEALTH_PATH = "/tts/health"
        private const val TTS_GENERATE_PATH = "/tts/generate"
    }

    // Short connect timeout, moderate read timeout for warm generation (~2s)
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    // Quick client for health checks
    private val healthClient = OkHttpClient.Builder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(2, TimeUnit.SECONDS)
        .build()

    private val currentTrack = AtomicReference<AudioTrack?>(null)
    private val cancelled = AtomicBoolean(false)
    private val currentCall = AtomicReference<okhttp3.Call?>(null)
    private val warmingUp = AtomicBoolean(false)

    /**
     * Check if the TTS model is loaded and ready.
     * If not loaded, triggers a background warm-up and returns false.
     */
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
            json.optBoolean("model_loaded", false)
        } catch (e: Exception) {
            Log.w(TAG, "Health check failed: ${e.message}")
            false
        }
    }

    /**
     * Trigger model warm-up in background (fire-and-forget).
     * Sends a tiny generate request to force model loading.
     */
    private fun triggerWarmUp() {
        if (warmingUp.getAndSet(true)) return  // already warming
        Thread {
            try {
                Log.d(TAG, "Triggering XTTS-v2 warm-up...")
                val request = Request.Builder()
                    .url("$TTS_BASE_URL$TTS_GENERATE_PATH")
                    .post("""{"text":"warm"}""".toByteArray()
                        .toRequestBody("application/json".toMediaType()))
                    .build()
                // Use a client with long timeout for cold start
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
     * Stream TTS audio from server and play it.
     * Returns true if audio played successfully, false if server unreachable/cold/error.
     *
     * If the model isn't warm, returns false immediately and starts warm-up in background.
     * Caller should fall back to Android TTS.
     */
    suspend fun speak(text: String): Boolean = withContext(Dispatchers.IO) {
        cancelled.set(false)

        // Smart warm-check: if model isn't loaded, fall back immediately and warm up
        if (!isModelWarm()) {
            Log.d(TAG, "Model not warm, falling back to Android TTS and triggering warm-up")
            triggerWarmUp()
            return@withContext false
        }

        val url = "$TTS_BASE_URL$TTS_STREAM_PATH"
        val jsonBody = """{"text":${escapeJson(text)}}"""
        val request = Request.Builder()
            .url(url)
            .post(jsonBody.toByteArray().toRequestBody("application/json".toMediaType()))
            .build()

        try {
            val call = httpClient.newCall(request)
            currentCall.set(call)

            val response = withTimeoutOrNull(10_000L) {
                withContext(Dispatchers.IO) { call.execute() }
            }

            if (cancelled.get()) return@withContext false

            if (response == null) {
                Log.w(TAG, "Server TTS timed out")
                call.cancel()
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

            // Verify content type is binary, not HTML/JSON error
            val contentType = response.header("Content-Type", "")
            if (contentType?.contains("text/html") == true || contentType?.contains("application/json") == true) {
                Log.w(TAG, "Server returned $contentType instead of audio")
                response.close()
                return@withContext false
            }

            val success = body.byteStream().use { stream ->
                playPcmStream(stream)
            }

            return@withContext success && !cancelled.get()
        } catch (e: Exception) {
            if (!cancelled.get()) {
                Log.w(TAG, "Server TTS failed: ${e.message}")
            }
            return@withContext false
        } finally {
            currentCall.set(null)
        }
    }

    fun stop() {
        cancelled.set(true)
        currentCall.getAndSet(null)?.cancel()
        currentTrack.getAndSet(null)?.let { track ->
            try {
                track.pause()
                track.flush()
                track.release()
            } catch (_: Exception) {}
        }
    }

    private fun playPcmStream(stream: InputStream): Boolean {
        // Read 12-byte header: sample_rate(4), channels(4), bits(4)
        val headerBuf = ByteArray(12)
        var read = 0
        while (read < 12) {
            val n = stream.read(headerBuf, read, 12 - read)
            if (n <= 0) {
                Log.w(TAG, "Failed to read PCM header (got $read bytes)")
                return false
            }
            read += n
        }

        val bb = ByteBuffer.wrap(headerBuf).order(ByteOrder.LITTLE_ENDIAN)
        val sampleRate = bb.getInt()
        val channels = bb.getInt()
        val bitsPerSample = bb.getInt()

        Log.d(TAG, "PCM header: rate=$sampleRate ch=$channels bits=$bitsPerSample")

        if (sampleRate !in 8000..48000 || channels !in 1..2 || bitsPerSample != 16) {
            Log.e(TAG, "Invalid PCM header — likely received error page instead of audio")
            return false
        }

        val channelConfig = if (channels == 1) AudioFormat.CHANNEL_OUT_MONO
                            else AudioFormat.CHANNEL_OUT_STEREO
        val minBufSize = AudioTrack.getMinBufferSize(sampleRate, channelConfig, AudioFormat.ENCODING_PCM_16BIT)
        if (minBufSize <= 0) {
            Log.e(TAG, "AudioTrack.getMinBufferSize returned error: $minBufSize")
            return false
        }
        val bufSize = maxOf(minBufSize * 2, 8192)

        val track = try {
            AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setSampleRate(sampleRate)
                        .setChannelMask(channelConfig)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .build()
                )
                .setBufferSizeInBytes(bufSize)
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create AudioTrack: ${e.message}")
            return false
        }

        if (track.state != AudioTrack.STATE_INITIALIZED) {
            Log.e(TAG, "AudioTrack not initialized (state=${track.state})")
            track.release()
            return false
        }

        currentTrack.set(track)
        track.play()

        // Use even-sized buffer to guarantee 16-bit sample alignment
        val readBuf = ByteArray(4096)
        var totalBytes = 0
        try {
            while (!cancelled.get()) {
                val n = stream.read(readBuf)
                if (n <= 0) break

                // Ensure we only write even number of bytes (16-bit PCM alignment)
                val writeLen = if (n % 2 != 0) n - 1 else n

                if (writeLen > 0) {
                    val written = track.write(readBuf, 0, writeLen)
                    if (written < 0) {
                        Log.e(TAG, "AudioTrack.write error: $written")
                        return false
                    }
                    totalBytes += written
                }
            }
            if (!cancelled.get() && totalBytes > 0) {
                track.stop()
            }
            Log.d(TAG, "Playback complete: $totalBytes bytes")
            return totalBytes > 0 && !cancelled.get()
        } catch (e: Exception) {
            if (!cancelled.get()) {
                Log.e(TAG, "Playback error: ${e.message}")
            }
            return false
        } finally {
            if (currentTrack.compareAndSet(track, null)) {
                try { track.release() } catch (_: Exception) {}
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
