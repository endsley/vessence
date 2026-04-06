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
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/**
 * Streams PCM audio from the XTTS-v2 TTS server and plays it via AudioTrack.
 *
 * The server sends a 12-byte header (sample_rate, channels, bits_per_sample as
 * little-endian int32), followed by raw 16-bit PCM data in chunked transfer encoding.
 */
class ServerTtsPlayer {

    companion object {
        private const val TAG = "ServerTtsPlayer"

        /**
         * Direct URL to the TTS server. Uses local network IP since the TTS server
         * is not behind the Cloudflare tunnel. Change this if your server IP changes.
         * When we eventually route through the tunnel/relay, this becomes the jane base URL.
         */
        private const val TTS_BASE_URL = "http://192.168.86.21:8095"
        private const val TTS_PATH = "/tts/stream"
    }

    // Dedicated OkHttp client with short timeouts.
    // readTimeout = max gap between bytes. Set to 10s so cold-start (30s model load)
    // triggers fallback to Android TTS, but warm generation (~2s) works fine.
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    private val currentTrack = AtomicReference<AudioTrack?>(null)
    private val cancelled = AtomicBoolean(false)
    private val currentCall = AtomicReference<okhttp3.Call?>(null)

    /**
     * Stream TTS audio from server and play it.
     * Returns true if audio played successfully, false if server unreachable or error.
     * Timeout: 8 seconds for server response (covers model cold-start + first chunk).
     */
    suspend fun speak(text: String): Boolean = withContext(Dispatchers.IO) {
        cancelled.set(false)
        val url = "$TTS_BASE_URL$TTS_PATH"

        val jsonBody = """{"text":${escapeJson(text)}}"""
        val request = Request.Builder()
            .url(url)
            .post(jsonBody.toByteArray().toRequestBody("application/json".toMediaType()))
            .build()

        try {
            val call = httpClient.newCall(request)
            currentCall.set(call)

            // Execute with timeout covering connect + first response headers
            val response = withTimeoutOrNull(8000L) {
                withContext(Dispatchers.IO) {
                    call.execute()
                }
            }

            if (cancelled.get()) return@withContext false

            if (response == null) {
                Log.w(TAG, "Server TTS timed out waiting for response")
                call.cancel()
                return@withContext false
            }

            if (!response.isSuccessful) {
                Log.w(TAG, "Server TTS returned ${response.code}")
                response.close()
                return@withContext false
            }

            val body = response.body ?: run {
                Log.w(TAG, "Server TTS returned empty body")
                response.close()
                return@withContext false
            }

            val success = body.byteStream().use { stream ->
                playPcmStream(stream)
            }

            currentCall.set(null)
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
        // Cancel the HTTP call to stop reading from network
        currentCall.getAndSet(null)?.cancel()
        // Stop and release the AudioTrack
        currentTrack.getAndSet(null)?.let { track ->
            try {
                track.pause()
                track.flush()
                track.release()
            } catch (_: Exception) {}
        }
    }

    /**
     * Play raw PCM from input stream. Returns true if playback completed successfully.
     */
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

        if (sampleRate !in 8000..48000 || channels !in 1..2 || bitsPerSample != 16) {
            Log.e(TAG, "Invalid PCM header: rate=$sampleRate ch=$channels bits=$bitsPerSample")
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

        val readBuf = ByteArray(4096)
        var totalBytes = 0
        try {
            while (!cancelled.get()) {
                val n = stream.read(readBuf)
                if (n <= 0) break
                val written = track.write(readBuf, 0, n)
                if (written < 0) {
                    Log.e(TAG, "AudioTrack.write error: $written")
                    return false
                }
                totalBytes += written
            }
            // Wait for playback to finish
            if (!cancelled.get() && totalBytes > 0) {
                track.stop()
            }
            return totalBytes > 0 && !cancelled.get()
        } catch (e: Exception) {
            if (!cancelled.get()) {
                Log.e(TAG, "Playback error: ${e.message}")
            }
            return false
        } finally {
            // Only release if we still own it (stop() may have already released)
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
