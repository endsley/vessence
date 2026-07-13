package com.vessences.android.voice

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.os.SystemClock
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.sqrt

data class BargeInEvent(
    val source: String,
    val rms: Float,
    val threshold: Float,
    val elapsedMs: Long,
)

/**
 * Lightweight speech-energy monitor used only while Jane is speaking.
 *
 * This is not STT. It is a low-latency barge-in trigger: when user speech is
 * detected over the playback echo floor, ChatViewModel stops TTS and launches
 * the existing headless SpeechRecognizer path for the actual transcript.
 */
class BargeInMonitor(
    context: Context,
    private val scope: CoroutineScope,
    private val onBargeIn: (BargeInEvent) -> Unit,
) {
    companion object {
        private const val TAG = "BargeInMonitor"
        private const val SAMPLE_RATE = 16_000
        private const val FRAME_SAMPLES = 480 // 30 ms at 16 kHz
        private const val WARMUP_MS = 650L
        private const val MIN_RMS_THRESHOLD = 0.035f
        private const val MAX_RMS_THRESHOLD = 0.12f
        private const val MIN_PEAK_THRESHOLD = 0.16f
        private const val HOT_FRAMES_REQUIRED = 5
    }

    private val appContext = context.applicationContext
    private val running = AtomicBoolean(false)
    private val triggered = AtomicBoolean(false)
    private var monitorJob: Job? = null
    @Volatile
    private var activeSource: String? = null

    fun start(source: String) {
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            com.vessences.android.DiagnosticReporter.voiceFlow(
                "barge_in_monitor_skipped",
                mapOf("reason" to "no_record_audio_permission", "source" to source),
            )
            return
        }
        if (running.get()) {
            val previous = activeSource
            activeSource = source
            com.vessences.android.DiagnosticReporter.voiceFlow(
                "barge_in_monitor_retargeted",
                mapOf("from" to (previous ?: ""), "to" to source),
            )
            return
        }
        stop()
        activeSource = source
        running.set(true)
        triggered.set(false)
        monitorJob = scope.launch(Dispatchers.Default) {
            monitor(source)
        }
        com.vessences.android.DiagnosticReporter.voiceFlow(
            "barge_in_monitor_started",
            mapOf("source" to source),
        )
    }

    fun stop() {
        running.set(false)
        activeSource = null
        monitorJob?.cancel()
        monitorJob = null
    }

    fun stop(source: String) {
        if (activeSource == source) {
            stop()
        }
    }

    @SuppressLint("MissingPermission")
    private fun monitor(source: String) {
        val minBuffer = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuffer <= 0) {
            reportStop("bad_min_buffer", source)
            return
        }

        val bufferSize = maxOf(minBuffer, FRAME_SAMPLES * 4)
        var record: AudioRecord? = null
        var aec: AcousticEchoCanceler? = null
        var ns: NoiseSuppressor? = null
        try {
            record = AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize,
            )
            if (record.state != AudioRecord.STATE_INITIALIZED) {
                reportStop("audio_record_not_initialized", source)
                return
            }

            val sessionId = record.audioSessionId
            if (AcousticEchoCanceler.isAvailable()) {
                aec = runCatching { AcousticEchoCanceler.create(sessionId) }.getOrNull()
                runCatching { aec?.enabled = true }
            }
            if (NoiseSuppressor.isAvailable()) {
                ns = runCatching { NoiseSuppressor.create(sessionId) }.getOrNull()
                runCatching { ns?.enabled = true }
            }

            val buffer = ShortArray(FRAME_SAMPLES)
            var noiseFloor = 0.012f
            var hotFrames = 0
            val startedAt = SystemClock.elapsedRealtime()

            record.startRecording()
            while (running.get() && scope.isActive) {
                val read = record.read(buffer, 0, buffer.size)
                if (read <= 0) continue

                var sumSquares = 0.0
                var peak = 0f
                for (i in 0 until read) {
                    val sample = buffer[i].toFloat() / Short.MAX_VALUE.toFloat()
                    val abs = kotlin.math.abs(sample)
                    if (abs > peak) peak = abs
                    sumSquares += (sample * sample).toDouble()
                }
                val rms = sqrt(sumSquares / read).toFloat()
                val elapsed = SystemClock.elapsedRealtime() - startedAt

                if (elapsed < WARMUP_MS) {
                    noiseFloor = (noiseFloor * 0.88f) + (rms * 0.12f)
                    continue
                }

                val threshold = (noiseFloor * 2.6f + 0.018f)
                    .coerceIn(MIN_RMS_THRESHOLD, MAX_RMS_THRESHOLD)
                val hot = rms > threshold && peak > MIN_PEAK_THRESHOLD
                if (hot) {
                    hotFrames += 1
                } else {
                    hotFrames = maxOf(0, hotFrames - 1)
                    if (rms < threshold) {
                        noiseFloor = (noiseFloor * 0.97f) + (rms * 0.03f)
                    }
                }

                if (hotFrames >= HOT_FRAMES_REQUIRED && triggered.compareAndSet(false, true)) {
                    running.set(false)
                    val eventSource = activeSource ?: source
                    val event = BargeInEvent(
                        source = eventSource,
                        rms = rms,
                        threshold = threshold,
                        elapsedMs = elapsed,
                    )
                    Log.i(TAG, "Barge-in detected source=$eventSource rms=$rms threshold=$threshold")
                    scope.launch(Dispatchers.Main) {
                        onBargeIn(event)
                    }
                    break
                }
            }
        } catch (se: SecurityException) {
            reportStop("security_exception", source, se)
        } catch (t: Throwable) {
            reportStop("monitor_exception", source, t)
        } finally {
            running.set(false)
            if (activeSource == source) {
                activeSource = null
            }
            runCatching {
                if (record?.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    record.stop()
                }
            }
            runCatching { record?.release() }
            runCatching { aec?.release() }
            runCatching { ns?.release() }
        }
    }

    private fun reportStop(reason: String, source: String, throwable: Throwable? = null) {
        Log.w(TAG, "Barge-in monitor stopped: $reason", throwable)
        com.vessences.android.DiagnosticReporter.voiceFlow(
            "barge_in_monitor_stopped",
            mapOf(
                "reason" to reason,
                "source" to source,
                "exception_class" to (throwable?.javaClass?.name ?: ""),
                "message" to (throwable?.message ?: ""),
            ),
        )
    }
}
