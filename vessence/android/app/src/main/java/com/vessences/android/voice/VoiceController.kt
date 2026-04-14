package com.vessences.android.voice

import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import com.vessences.android.data.repository.ChatBackend
import com.vessences.android.data.repository.VoiceSettingsRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.util.Locale
import kotlin.coroutines.resume

private const val TAG = "VoiceController"

data class VoiceState(
    val alwaysListeningEnabled: Boolean = false,
    val isPreparingModel: Boolean = false,
    val isWakeListening: Boolean = false,
    val isCapturingCommand: Boolean = false,
    val transcriptPreview: String = "",
    val status: String? = null,
    val error: String? = null,
)

class VoiceController(
    context: Context,
    private val backend: ChatBackend,
    private val externalScope: CoroutineScope,
    initialAlwaysListening: Boolean,
    private val onStateChanged: (VoiceState) -> Unit,
    private val onTranscriptReady: (String) -> Unit,
) {
    private val appContext = context.applicationContext
    private val tts = HybridTtsManager(appContext)
    private val voiceSettings = VoiceSettingsRepository(appContext)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @Volatile
    private var currentState = VoiceState(alwaysListeningEnabled = initialAlwaysListening)

    @Volatile
    private var wakeDetector: OpenWakeWordDetector? = null

    @Volatile
    private var wakeThread: Thread? = null

    @Volatile
    private var isRunning = false
    private var waitingForReply = false

    fun isWaitingForReply(): Boolean = waitingForReply

    init {
        emitState(currentState)
        if (initialAlwaysListening) {
            startWakeWordListening()
        }
    }

    fun setAlwaysListeningEnabled(enabled: Boolean) {
        emitState(currentState.copy(alwaysListeningEnabled = enabled, error = null))
        if (enabled) {
            startWakeWordListening()
        } else {
            stopListening()
        }
    }

    fun setTriggerPhrase(phrase: String) {
        val normalized = phrase.lowercase(Locale.US).trim().ifBlank { "hey jane" }
        voiceSettings.setTriggerPhrase(normalized)
    }

    fun startPushToTalk() {
        scope.launch {
            waitingForReply = false
            tts.stop()
            startCommandCapture()
        }
    }

    fun stopPushToTalk() {
        // SpeechRecognizer handles its own stop
    }

    fun cancelListening() {
        stopListening()
    }

    fun startWakeWordListening() {
        scope.launch {
            if (!currentState.alwaysListeningEnabled) return@launch
            if (waitingForReply) return@launch
            tts.stop()
            startWakeDetection()
        }
    }

    var onSpeakingDone: (() -> Unit)? = null

    fun onAssistantReply(text: String, autoListen: Boolean = true) {
        if (!waitingForReply || text.isBlank()) {
            onSpeakingDone?.invoke()
            if (currentState.alwaysListeningEnabled && wakeThread == null) {
                startWakeWordListening()
            }
            return
        }

        externalScope.launch {
            tts.speak(text)
            onSpeakingDone?.invoke()
            waitingForReply = false
            if (autoListen) {
                startCommandCapture()
            } else if (currentState.alwaysListeningEnabled) {
                startWakeWordListening()
            }
        }
    }

    fun stopTts() {
        tts.stop()
    }

    fun clearError() {
        emitState(currentState.copy(error = null))
    }

    fun release() {
        stopListening()
        tts.shutdown()
        scope.coroutineContext[Job]?.cancel()
    }

    fun startListeningWithTimeout(timeoutMs: Long = 6000) {
        scope.launch {
            waitingForReply = false
            startCommandCapture()
        }
    }

    // ── Wake Word Detection (OpenWakeWord) ──────────────────────────────────

    private fun startWakeDetection() {
        stopListening()
        emitState(currentState.copy(
            isWakeListening = true, isCapturingCommand = false,
            status = "Listening for wake word", error = null,
        ))

        isRunning = true
        wakeThread = Thread({
            try {
                if (wakeDetector == null) {
                    emitState(currentState.copy(isPreparingModel = true, status = "Loading wake word model"))
                    try {
                        wakeDetector = OpenWakeWordDetector(appContext)
                    } catch (e: Throwable) {
                        Log.e(TAG, "Failed to create OpenWakeWordDetector", e)
                        emitState(currentState.copy(
                            isPreparingModel = false, isWakeListening = false,
                            error = "Voice model failed to load: ${e.message}",
                        ))
                        return@Thread
                    }
                    emitState(currentState.copy(isPreparingModel = false, status = "Listening for wake word"))
                }
                val det = wakeDetector ?: return@Thread

                val bufferSize = AudioRecord.getMinBufferSize(
                    OpenWakeWordDetector.SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                ).coerceAtLeast(OpenWakeWordDetector.CHUNK_SIZE * 2)

                val record = AudioRecord(
                    MediaRecorder.AudioSource.VOICE_RECOGNITION,
                    OpenWakeWordDetector.SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    bufferSize,
                )

                if (record.state != AudioRecord.STATE_INITIALIZED) {
                    record.release()
                    emitState(currentState.copy(
                        isWakeListening = false, error = "Microphone unavailable",
                    ))
                    return@Thread
                }

                val buffer = ShortArray(OpenWakeWordDetector.CHUNK_SIZE)
                record.startRecording()

                try {
                    while (isRunning) {
                        val read = record.read(buffer, 0, buffer.size)
                        if (read <= 0) continue
                        if (det.feedShorts(buffer, read)) {
                            Log.i(TAG, "Wake word detected!")
                            det.reset()
                            emitState(currentState.copy(
                                isWakeListening = false, status = "Wake word detected",
                            ))
                            // Play beep + capture command
                            try {
                                val toneGen = android.media.ToneGenerator(
                                    android.media.AudioManager.STREAM_NOTIFICATION, 100)
                                toneGen.startTone(android.media.ToneGenerator.TONE_PROP_BEEP, 150)
                                Thread.sleep(200)
                                toneGen.release()
                            } catch (_: Exception) {}

                            scope.launch { startCommandCapture() }
                            return@Thread
                        }
                    }
                } finally {
                    runCatching {
                        if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) record.stop()
                        record.release()
                    }
                }
            } catch (t: Throwable) {
                Log.e(TAG, "Wake detection error", t)
                emitState(currentState.copy(
                    isWakeListening = false, error = t.message ?: "Voice detection failed",
                ))
            } finally {
                wakeThread = null
            }
        }, "oww-wake").apply { start() }
    }

    // ── Command Capture (Android SpeechRecognizer) ──────────────────────────

    private suspend fun startCommandCapture() {
        emitState(currentState.copy(
            isWakeListening = false, isCapturingCommand = true,
            status = "Listening", transcriptPreview = "",
        ))

        val transcript = withContext(Dispatchers.Main) {
            suspendCancellableCoroutine { continuation ->
                if (!SpeechRecognizer.isRecognitionAvailable(appContext)) {
                    continuation.resume(null)
                    return@suspendCancellableCoroutine
                }

                val recognizer = SpeechRecognizer.createSpeechRecognizer(appContext)
                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                    putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
                    putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 6000L)
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                }

                var resumed = false
                recognizer.setRecognitionListener(object : RecognitionListener {
                    override fun onResults(results: Bundle?) {
                        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        val text = matches?.firstOrNull()?.trim()
                        recognizer.destroy()
                        if (!resumed) { resumed = true; continuation.resume(text) }
                    }
                    override fun onPartialResults(partial: Bundle?) {
                        val matches = partial?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        val preview = matches?.firstOrNull()?.trim()
                        if (!preview.isNullOrBlank()) {
                            emitState(currentState.copy(transcriptPreview = preview))
                        }
                    }
                    override fun onError(error: Int) {
                        recognizer.destroy()
                        if (!resumed) { resumed = true; continuation.resume(null) }
                    }
                    override fun onReadyForSpeech(params: Bundle?) {}
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {}
                    override fun onEvent(eventType: Int, params: Bundle?) {}
                })

                continuation.invokeOnCancellation { recognizer.destroy() }
                recognizer.startListening(intent)
            }
        }

        val cleaned = transcript?.trim() ?: ""
        emitState(currentState.copy(
            isCapturingCommand = false,
            transcriptPreview = cleaned,
            status = if (cleaned.isBlank()) null else "Sending to ${backend.displayName}",
        ))

        if (cleaned.isBlank()) {
            if (currentState.alwaysListeningEnabled) {
                startWakeDetection()
            }
        } else {
            waitingForReply = true
            onTranscriptReady(cleaned)
        }
    }

    // ── Helpers ─────────────────────────────────────────────────────────────

    private fun stopListening() {
        isRunning = false
        wakeThread = null
        emitState(currentState.copy(
            isWakeListening = false, isCapturingCommand = false,
            transcriptPreview = "", status = null,
        ))
    }

    private fun emitState(newState: VoiceState) {
        currentState = newState
        onStateChanged(newState)
    }
}
