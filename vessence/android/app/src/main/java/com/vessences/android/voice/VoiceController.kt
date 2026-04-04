package com.vessences.android.voice

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import com.vessences.android.data.repository.ChatBackend
import com.vessences.android.data.repository.VoiceSettingsRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import java.util.Locale
import kotlin.math.abs
import kotlin.math.min

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
    private val modelManager = VoskModelManager(appContext)
    private val tts = AndroidTtsManager(appContext)
    private val voiceSettings = VoiceSettingsRepository(appContext)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @Volatile
    private var currentState = VoiceState(alwaysListeningEnabled = initialAlwaysListening)

    @Volatile
    private var session: ListeningSession? = null
    private var waitingForReply = false

    @Volatile
    private var customTriggerPhrase: String? = null

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
        customTriggerPhrase = phrase.lowercase(Locale.US).trim()
        voiceSettings.setTriggerPhrase(customTriggerPhrase!!)
        // Restart wake listening if active to pick up the new phrase
        if (currentState.alwaysListeningEnabled && currentState.isWakeListening) {
            startWakeWordListening()
        }
    }

    fun startPushToTalk() {
        scope.launch {
            waitingForReply = false
            tts.stop()
            startCommandListening(acknowledge = false)
        }
    }

    fun stopPushToTalk() {
        session?.stop(finalizeTranscript = true)
    }

    fun startWakeWordListening() {
        scope.launch {
            if (!currentState.alwaysListeningEnabled) return@launch
            if (waitingForReply) return@launch
            tts.stop()
            val model = prepareModel() ?: return@launch
            startSession(
                ListeningMode.WAKE,
                model = model,
                grammarPhrases = wakePhrasesForBackend(backend),
            )
        }
    }

    fun onAssistantReply(text: String) {
        if (!waitingForReply || text.isBlank()) {
            if (currentState.alwaysListeningEnabled && session == null) {
                startWakeWordListening()
            }
            return
        }

        externalScope.launch {
            tts.speak(text)
            waitingForReply = false
            if (currentState.alwaysListeningEnabled) {
                startWakeWordListening()
            }
        }
    }

    fun clearError() {
        emitState(currentState.copy(error = null))
    }

    fun release() {
        stopListening()
        tts.shutdown()
        scope.coroutineContext[Job]?.cancel()
    }

    /**
     * Start listening with a silence timeout. Used by auto-listen after TTS.
     * Stops automatically after [timeoutMs] of silence.
     */
    fun startListeningWithTimeout(timeoutMs: Long = 6000) {
        scope.launch {
            waitingForReply = false
            startCommandListening(acknowledge = false)
            // Auto-stop after timeout if still listening
            kotlinx.coroutines.delay(timeoutMs)
            if (currentState.isCapturingCommand) {
                session?.stop(finalizeTranscript = true)
            }
        }
    }

    private suspend fun startCommandListening(acknowledge: Boolean) {
        stopListening()
        val model = prepareModel() ?: return
        if (acknowledge) {
            tts.speak(acknowledgementForBackend(backend))
        }
        startSession(ListeningMode.COMMAND, model = model)
    }

    private suspend fun prepareModel(): Model? {
        emitState(currentState.copy(isPreparingModel = true, status = "Preparing offline voice", error = null))
        return try {
            modelManager.ensureModel { status ->
                emitState(currentState.copy(isPreparingModel = true, status = status, error = null))
            }.also {
                emitState(currentState.copy(isPreparingModel = false, status = null, error = null))
            }
        } catch (e: Exception) {
            emitState(
                currentState.copy(
                    isPreparingModel = false,
                    isWakeListening = false,
                    isCapturingCommand = false,
                    status = null,
                    error = e.message ?: "Voice model setup failed",
                )
            )
            null
        }
    }

    private fun startSession(
        mode: ListeningMode,
        model: Model,
        grammarPhrases: List<String>? = null,
    ) {
        stopListening()
        emitState(
            currentState.copy(
                isWakeListening = mode == ListeningMode.WAKE,
                isCapturingCommand = mode == ListeningMode.COMMAND,
                transcriptPreview = "",
                status = statusForMode(mode),
                error = null,
            )
        )
        val triggerPhrases = if (mode == ListeningMode.WAKE) {
            grammarPhrases.orEmpty()
        } else {
            emptyList()
        }
        val newSession = ListeningSession(
            model = model,
            mode = mode,
            grammarPhrases = grammarPhrases,
            triggerPhrases = triggerPhrases,
            fuzzyThreshold = FUZZY_MATCH_THRESHOLD,
            onPreview = { preview ->
                emitState(
                    currentState.copy(
                        isWakeListening = mode == ListeningMode.WAKE,
                        isCapturingCommand = mode == ListeningMode.COMMAND,
                        transcriptPreview = preview,
                        status = statusForMode(mode),
                        error = null,
                    )
                )
            },
            onWakeDetected = {
                emitState(
                    currentState.copy(
                        isWakeListening = false,
                        isCapturingCommand = false,
                        transcriptPreview = "",
                        status = "Wake word detected",
                        error = null,
                    )
                )
                scope.launch { startCommandListening(acknowledge = true) }
            },
            onCommandDetected = { transcript ->
                val cleaned = transcript.trim()
                emitState(
                    currentState.copy(
                        isWakeListening = false,
                        isCapturingCommand = false,
                        transcriptPreview = cleaned,
                        status = if (cleaned.isBlank()) null else "Sending to ${backend.displayName}",
                        error = null,
                    )
                )
                if (cleaned.isBlank()) {
                    if (currentState.alwaysListeningEnabled) {
                        startWakeWordListening()
                    }
                } else {
                    waitingForReply = true
                    onTranscriptReady(cleaned)
                }
            },
            onStopped = {
                session = null
                if (!waitingForReply) {
                    emitState(
                        currentState.copy(
                            isWakeListening = false,
                            isCapturingCommand = false,
                            status = null,
                        )
                    )
                }
            },
            onError = { message ->
                session = null
                emitState(
                    currentState.copy(
                        isWakeListening = false,
                        isCapturingCommand = false,
                        status = null,
                        error = message,
                    )
                )
            },
        )
        session = newSession
        newSession.start()
    }

    private fun stopListening() {
        session?.stop(finalizeTranscript = false)
        session = null
        emitState(
            currentState.copy(
                isWakeListening = false,
                isCapturingCommand = false,
                transcriptPreview = "",
                status = null,
            )
        )
    }

    private fun emitState(newState: VoiceState) {
        currentState = newState
        onStateChanged(newState)
    }

    private fun acknowledgementForBackend(backend: ChatBackend): String =
        when (backend) {
            ChatBackend.JANE -> "Yes, Jane listening."
            ChatBackend.VAULT -> "Yes, Amber listening."
        }

    private fun wakePhrasesForBackend(backend: ChatBackend): List<String> {
        val custom = customTriggerPhrase ?: voiceSettings.getTriggerPhrase()
        return when (backend) {
            ChatBackend.JANE -> {
                val phrases = mutableListOf(custom)
                if (custom != "hey jane") phrases.add("hey jane")
                phrases
            }
            ChatBackend.VAULT -> listOf("hey amber", "amberlee", "amber lee")
        }
    }

    private fun statusForMode(mode: ListeningMode): String =
        when (mode) {
            ListeningMode.WAKE -> "Listening for wake word"
            ListeningMode.COMMAND -> "Listening"
        }

    companion object {
        private const val FUZZY_MATCH_THRESHOLD = 0.7
    }
}

internal enum class ListeningMode {
    WAKE,
    COMMAND,
}

internal class ListeningSession(
    private val model: Model,
    private val mode: ListeningMode,
    private val grammarPhrases: List<String>? = null,
    private val triggerPhrases: List<String> = emptyList(),
    private val fuzzyThreshold: Double = 0.7,
    private val onPreview: (String) -> Unit,
    private val onWakeDetected: () -> Unit,
    private val onCommandDetected: (String) -> Unit,
    private val onStopped: () -> Unit,
    private val onError: (String) -> Unit,
) {
    @Volatile
    private var isRunning = false

    @Volatile
    private var finalizeTranscript = false
    private var completionDelivered = false

    private var thread: Thread? = null
    private var audioRecord: AudioRecord? = null
    private var recognizer: Recognizer? = null

    fun start() {
        if (isRunning) return
        isRunning = true
        thread = Thread(::runLoop, "voice-listening-${mode.name.lowercase(Locale.US)}").apply { start() }
    }

    fun stop(finalizeTranscript: Boolean) {
        this.finalizeTranscript = finalizeTranscript
        isRunning = false
        audioRecord?.stopSafely()
    }

    private fun runLoop() {
        try {
            val bufferSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            ).coerceAtLeast(SAMPLE_RATE)
            val record = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize,
            )
            if (record.state != AudioRecord.STATE_INITIALIZED) {
                throw IllegalStateException("Microphone is unavailable")
            }

            val recognizerInstance = if (grammarPhrases.isNullOrEmpty()) {
                Recognizer(model, SAMPLE_RATE.toFloat())
            } else {
                val grammar = JSONObject().put("phrases", grammarPhrases + "[unk]").getJSONArray("phrases").toString()
                Recognizer(model, SAMPLE_RATE.toFloat(), grammar)
            }

            audioRecord = record
            recognizer = recognizerInstance
            record.startRecording()

            val buffer = ByteArray(bufferSize)
            var transcript = ""
            var sawSpeech = false
            val startAt = System.currentTimeMillis()
            var lastSpeechAt = startAt

            while (isRunning) {
                val read = record.read(buffer, 0, buffer.size)
                if (read <= 0) continue

                val energy = rmsLevel(buffer, read)
                val partialJson = recognizerInstance.partialResult
                val partialText = extractText(partialJson, "partial")

                if (partialText.isNotBlank()) {
                    transcript = partialText
                    lastSpeechAt = System.currentTimeMillis()
                    sawSpeech = true
                    onPreview(partialText)
                    if (mode == ListeningMode.WAKE && containsWakePhrase(partialText, triggerPhrases)) {
                        isRunning = false
                        completionDelivered = true
                        onWakeDetected()
                        return
                    }
                } else if (energy >= SPEECH_RMS_THRESHOLD) {
                    lastSpeechAt = System.currentTimeMillis()
                    sawSpeech = true
                }

                if (recognizerInstance.acceptWaveForm(buffer, read)) {
                    val resultText = extractText(recognizerInstance.result, "text")
                    if (resultText.isNotBlank()) {
                        transcript = resultText
                        onPreview(resultText)
                        lastSpeechAt = System.currentTimeMillis()
                        sawSpeech = true
                        if (mode == ListeningMode.WAKE && containsWakePhrase(resultText, triggerPhrases)) {
                            isRunning = false
                            completionDelivered = true
                            onWakeDetected()
                            return
                        }
                    }
                }

                val now = System.currentTimeMillis()
                if (mode == ListeningMode.COMMAND) {
                    if (sawSpeech && now - lastSpeechAt >= COMMAND_SILENCE_MS) {
                        break
                    }
                    if (!sawSpeech && now - startAt >= COMMAND_IDLE_TIMEOUT_MS) {
                        break
                    }
                }
            }

            if (mode == ListeningMode.COMMAND && (finalizeTranscript || sawSpeech)) {
                val finalText = extractText(recognizerInstance.finalResult, "text").ifBlank { transcript }
                completionDelivered = true
                onCommandDetected(finalText)
            } else {
                completionDelivered = true
                onStopped()
            }
        } catch (e: Exception) {
            completionDelivered = true
            onError(e.message ?: "Voice capture failed")
        } finally {
            recognizer?.close()
            recognizer = null
            audioRecord?.releaseSafely()
            audioRecord = null
            if (!completionDelivered) {
                onStopped()
            }
        }
    }

    private fun containsWakePhrase(text: String, phrases: List<String>): Boolean {
        val normalized = text.lowercase(Locale.US)
        return phrases.any { phrase ->
            val normalizedPhrase = phrase.lowercase(Locale.US)
            // Exact substring match
            if (normalized.contains(normalizedPhrase)) return@any true
            // Fuzzy match using normalized Levenshtein distance
            val similarity = normalizedSimilarity(normalized, normalizedPhrase)
            if (similarity >= fuzzyThreshold) return@any true
            // Also check if any substring of the text of the same length as the phrase matches
            if (normalized.length >= normalizedPhrase.length) {
                val words = normalized.split(" ")
                val phraseWords = normalizedPhrase.split(" ")
                if (words.size >= phraseWords.size) {
                    for (i in 0..words.size - phraseWords.size) {
                        val window = words.subList(i, i + phraseWords.size).joinToString(" ")
                        if (normalizedSimilarity(window, normalizedPhrase) >= fuzzyThreshold) {
                            return@any true
                        }
                    }
                }
            }
            false
        }
    }

    private fun extractText(json: String, key: String): String =
        runCatching { JSONObject(json).optString(key).trim() }.getOrDefault("")

    private fun rmsLevel(buffer: ByteArray, length: Int): Int {
        if (length < 2) return 0
        var total = 0L
        var samples = 0
        var index = 0
        while (index + 1 < length) {
            val sample = ((buffer[index + 1].toInt() shl 8) or (buffer[index].toInt() and 0xff)).toShort()
            total += abs(sample.toInt())
            samples++
            index += 2
        }
        return if (samples == 0) 0 else (total / samples).toInt()
    }

    private fun AudioRecord.stopSafely() {
        runCatching {
            if (recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                stop()
            }
        }
    }

    private fun AudioRecord.releaseSafely() {
        stopSafely()
        runCatching { release() }
    }

    companion object {
        internal const val SAMPLE_RATE = 16_000
        private const val SPEECH_RMS_THRESHOLD = 900
        private const val COMMAND_SILENCE_MS = 1_300L
        private const val COMMAND_IDLE_TIMEOUT_MS = 8_000L

        /**
         * Computes normalized similarity between two strings using Levenshtein distance.
         * Returns a value between 0.0 (completely different) and 1.0 (identical).
         */
        fun normalizedSimilarity(a: String, b: String): Double {
            if (a == b) return 1.0
            val maxLen = maxOf(a.length, b.length)
            if (maxLen == 0) return 1.0
            return 1.0 - levenshteinDistance(a, b).toDouble() / maxLen
        }

        private fun levenshteinDistance(a: String, b: String): Int {
            val m = a.length
            val n = b.length
            val dp = Array(m + 1) { IntArray(n + 1) }
            for (i in 0..m) dp[i][0] = i
            for (j in 0..n) dp[0][j] = j
            for (i in 1..m) {
                for (j in 1..n) {
                    val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                    dp[i][j] = min(min(dp[i - 1][j] + 1, dp[i][j - 1] + 1), dp[i - 1][j - 1] + cost)
                }
            }
            return dp[m][n]
        }
    }
}
