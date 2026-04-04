package com.vessences.android.ui.chat

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vessences.android.data.model.ChatMessage
import com.vessences.android.data.repository.ChatBackend
import com.vessences.android.data.repository.ChatRepository
import com.vessences.android.data.repository.AnnouncementPoller
import com.vessences.android.data.repository.LiveBroadcastListener
import com.vessences.android.voice.AndroidTtsManager
import com.vessences.android.data.repository.VoiceSettingsRepository
import com.vessences.android.notifications.ChatNotificationManager
import com.vessences.android.util.ChatPersistence
import com.vessences.android.util.ChatPreferences
import com.vessences.android.voice.VoiceController
import com.vessences.android.voice.VoiceState
import kotlinx.coroutines.Dispatchers
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch
import java.util.UUID
import java.util.concurrent.ConcurrentLinkedQueue

data class PendingMessage(
    val text: String,
    val fileUri: Uri? = null,
    val fromVoice: Boolean = false,
)

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val isSending: Boolean = false,
    val isUploading: Boolean = false,
    val uploadProgress: String? = null,
    val voice: VoiceState = VoiceState(),
    val error: String? = null,
    val queuedCount: Int = 0,
    val liveStatus: String = "",
    val livePlatform: String = "",
    val availableUpdate: com.vessences.android.data.api.AppVersion? = null,
    val updateDismissed: Boolean = false,
    val ttsEnabled: Boolean = false,
    val isSpeaking: Boolean = false,
    val progressBubble: String = "",
)

class ChatViewModel(
    context: Context,
    private val backend: ChatBackend,
) : ViewModel() {
    private val appContext = context.applicationContext
    private val repo = ChatRepository()
    private val backendKey = backend.name.lowercase()
    private val sessionId = "${backendKey}_android_${UUID.randomUUID().toString().take(8)}"
    private val chatPersistence = ChatPersistence(appContext)
    private val chatPrefs = ChatPreferences(appContext)
    private val pendingQueue = ConcurrentLinkedQueue<PendingMessage>()
    private var currentStreamJob: Job? = null
    private val liveListener = LiveBroadcastListener(viewModelScope, sessionId.take(12))
    private val announcementPoller = AnnouncementPoller(viewModelScope)
    private val tts = AndroidTtsManager(appContext)

    private val _state = MutableStateFlow(
        ChatUiState(
            messages = try { chatPersistence.loadMessages(backendKey) } catch (_: Exception) { emptyList() },
            ttsEnabled = chatPrefs.isTtsEnabled(backendKey),
        )
    )
    val state: StateFlow<ChatUiState> = _state

    private val notifier: ChatNotificationManager? = try { ChatNotificationManager(appContext) } catch (_: Exception) { null }
    private val voiceSettings: VoiceSettingsRepository? = try { VoiceSettingsRepository(appContext) } catch (_: Exception) { null }
    private val voiceController: VoiceController? = try {
        VoiceController(
            context = appContext,
            backend = backend,
            externalScope = viewModelScope,
            initialAlwaysListening = voiceSettings?.isAlwaysListeningEnabled() ?: false,
            onStateChanged = { voiceState ->
                _state.value = _state.value.copy(voice = voiceState)
            },
            onTranscriptReady = { transcript ->
                sendMessage(transcript, fromVoice = true)
            },
        )
    } catch (_: Exception) { null }

    init {
        try { notifier?.ensureChannels() } catch (_: Exception) {}
        // Auto-save messages whenever sending completes
        viewModelScope.launch {
            _state.collect { uiState ->
                if (!uiState.isSending && uiState.messages.isNotEmpty()) {
                    try { chatPersistence.saveMessages(backendKey, uiState.messages) } catch (_: Exception) {}
                }
            }
        }
        // Check for app updates
        if (backend == com.vessences.android.data.repository.ChatBackend.JANE) {
            viewModelScope.launch(Dispatchers.IO) {
                val update = com.vessences.android.data.api.UpdateManager.checkForUpdate(appContext)
                if (update != null) {
                    _state.value = _state.value.copy(availableUpdate = update)
                }
            }
        }

        // Sync settings from server on startup
        viewModelScope.launch(Dispatchers.IO) {
            try { com.vessences.android.util.SettingsSync.pullFromServer(appContext) } catch (_: Exception) {}
        }

        // Live broadcast: show when Jane is working on another session
        if (backend == ChatBackend.JANE) {
            liveListener.start()
            announcementPoller.start()
            viewModelScope.launch {
                liveListener.status.collect { live ->
                    _state.value = _state.value.copy(
                        liveStatus = live.message,
                        livePlatform = live.platform,
                    )
                }
            }
            viewModelScope.launch {
                announcementPoller.bubble.collect { bubble ->
                    _state.value = _state.value.copy(progressBubble = bubble.text)
                }
            }
            // Always pre-warm Jane's session on launch.
            // If messages exist, warm silently (no greeting bubble).
            // If empty, show the wake-up greeting.
            initSession(showGreeting = _state.value.messages.isEmpty())
            // Fire prefetch-memory in background after session init starts
            viewModelScope.launch(Dispatchers.IO) {
                try {
                    val baseUrl = com.vessences.android.data.api.ApiClient.getJaneBaseUrl()
                    val request = okhttp3.Request.Builder()
                        .url("$baseUrl/api/jane/prefetch-memory")
                        .post(okhttp3.RequestBody.create(null, ByteArray(0)))
                        .build()
                    com.vessences.android.data.api.ApiClient.getOkHttpClient().newCall(request).execute().close()
                } catch (_: Exception) {}
            }
        }
    }

    private fun initSession(showGreeting: Boolean = true) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val initMsg = if (showGreeting) {
                    // Show wake-up message for fresh sessions
                    val msg = ChatMessage(
                        text = "",
                        isUser = false,
                        isStreaming = true,
                        statusText = "Waking up...",
                        statusLog = listOf("Initializing memory and context..."),
                    )
                    _state.value = _state.value.copy(messages = _state.value.messages + msg)
                    msg
                } else null

                val flow = repo.initSession(sessionId)
                var greeting = ""
                flow.catch { e ->
                    greeting = "Hey! What's on your mind?"
                }.collect { event ->
                    when (event.type) {
                        "done" -> greeting = event.data.ifEmpty { "Hey! What's on your mind?" }
                        "status" -> {}
                    }
                }

                // Update the greeting bubble if we showed one
                if (initMsg != null) {
                    if (greeting.isEmpty()) greeting = "Hey! What's on your mind?"
                    _state.value = _state.value.copy(
                        messages = _state.value.messages.map { msg ->
                            if (msg.id == initMsg.id) msg.copy(
                                text = greeting,
                                isStreaming = false,
                                statusText = null,
                                statusLog = listOf("Ready"),
                            )
                            else msg
                        }
                    )
                }
                // Either way, the server-side session is now warm
            } catch (e: Exception) {
                // Silently handle — not critical
            }
        }
    }

    fun sendMessage(
        text: String,
        fileContext: String? = null,
        fileUri: Uri? = null,
        fromVoice: Boolean = false,
    ) {
        if (text.isBlank() && fileUri == null) return

        // If already sending, queue the message for later
        if (_state.value.isSending) {
            pendingQueue.add(PendingMessage(text = text, fileUri = fileUri, fromVoice = fromVoice))
            // Show the user message immediately so they see it in chat
            val userMsg = ChatMessage(text = text, isUser = true)
            _state.value = _state.value.copy(
                messages = _state.value.messages + userMsg,
                queuedCount = pendingQueue.size,
            )
            return
        }

        executeSend(text, fileContext, fileUri, fromVoice)
    }

    fun cancelCurrentResponse() {
        currentStreamJob?.cancel()
        currentStreamJob = null
        // Finalize any streaming AI message
        val msgs = _state.value.messages
        val updatedMsgs = msgs.map { msg ->
            if (msg.isStreaming) msg.copy(
                text = if (msg.text.isNotBlank()) msg.text + "\n\n*(cancelled)*" else "*(cancelled)*",
                isStreaming = false,
            ) else msg
        }
        _state.value = _state.value.copy(
            messages = updatedMsgs,
            isSending = false,
        )
        // Drain the queue — don't auto-send after cancel
        pendingQueue.clear()
        _state.value = _state.value.copy(queuedCount = 0)
    }

    private fun executeSend(
        text: String,
        fileContext: String? = null,
        fileUri: Uri? = null,
        fromVoice: Boolean = false,
    ) {
        val userMsg = ChatMessage(text = text, isUser = true)
        val aiMsg = ChatMessage(
            id = "ai_${System.currentTimeMillis()}",
            text = "",
            isUser = false,
            isStreaming = true,
        )

        // Only add user message if it's not already in the list (queued messages are added earlier)
        val currentMsgs = _state.value.messages
        val alreadyShown = currentMsgs.any { it.isUser && it.text == text && it == currentMsgs.lastOrNull { m -> m.isUser } }
        val newMsgs = if (alreadyShown) currentMsgs + aiMsg else currentMsgs + userMsg + aiMsg

        _state.value = _state.value.copy(
            messages = newMsgs,
            isSending = true,
            error = null,
        )

        currentStreamJob = viewModelScope.launch(Dispatchers.IO) {
            var gotDone = false
            try {
                // If there's a file attachment, upload it first
                var resolvedFileContext = fileContext
                if (fileUri != null) {
                    _state.value = _state.value.copy(isUploading = true, uploadProgress = "Uploading file...")
                    try {
                        val uploadResult = repo.uploadFile(fileUri, appContext, backend)
                        resolvedFileContext = "[Attached file: ${uploadResult.filename}](${uploadResult.file_url})"
                        _state.value = _state.value.copy(isUploading = false, uploadProgress = null)
                    } catch (e: Exception) {
                        _state.value = _state.value.copy(
                            isUploading = false,
                            uploadProgress = null,
                            isSending = false,
                            error = "Upload failed: ${e.message}",
                        )
                        updateAiMessage(aiMsg.id, "File upload failed: ${e.message}", isStreaming = false)
                        processNextInQueue()
                        return@launch
                    }
                }

                val flow = repo.streamChat(backend, text, sessionId, resolvedFileContext, ttsEnabled = _state.value.ttsEnabled)
                var accumulated = ""
                var statusLog = mutableListOf<String>()
                var currentMsgId = aiMsg.id
                var files = emptyList<com.vessences.android.data.model.StreamEvent.FileRef>()

                flow.catch { e ->
                    val msg = e.message ?: ""
                    if (msg.contains("stream", ignoreCase = true) || msg.contains("reset", ignoreCase = true) || msg.contains("timeout", ignoreCase = true)) {
                        // Network glitch — show friendly message instead of raw error
                        updateAiMessage(currentMsgId, if (accumulated.isNotBlank()) accumulated else "Connection interrupted. Please try again.", isStreaming = false)
                    } else {
                        updateAiMessage(currentMsgId, "Error: $msg", isStreaming = false)
                    }
                    gotDone = true
                    onSendComplete(fromVoice, null)
                }.collect { event ->
                    when (event.type) {
                        "status" -> {
                            if (event.data.isNotEmpty()) {
                                statusLog.add(event.data)
                                updateAiMessage(currentMsgId, accumulated, isStreaming = true, status = "Working…", statusLog = statusLog.toList())
                                // Give Compose a chance to render status updates before the next
                                // event arrives — without this, IO-thread StateFlow conflation
                                // can swallow the status phase entirely when deltas follow fast.
                                kotlinx.coroutines.delay(60)
                            }
                        }
                        "delta" -> {
                            accumulated += event.data
                            updateAiMessage(currentMsgId, accumulated, isStreaming = true, status = null, statusLog = statusLog.toList())
                        }
                        "done" -> {
                            gotDone = true
                            val rawText = if (event.data.isNotEmpty()) event.data else accumulated
                            files = event.files
                            // TTS mode: main text is spoken-friendly; <visual> blocks are display-only
                            val visualRegex = Regex("<visual>([\\s\\S]*?)</visual>", RegexOption.IGNORE_CASE)
                            // For display: keep visual content but strip the tags; also strip legacy <spoken> tags
                            val spokenRegex = Regex("<spoken>([\\s\\S]*?)</spoken>", RegexOption.IGNORE_CASE)
                            val spokenMatch = spokenRegex.find(rawText)
                            val displayText = rawText.replace(visualRegex) { it.groupValues[1] }
                                .replace(spokenRegex, "").trimEnd().ifBlank { rawText }
                            // For TTS: if legacy <spoken> block exists, use it;
                            // otherwise strip <visual> blocks and read the rest
                            val spokenText = spokenMatch?.groupValues?.getOrNull(1)?.trim()
                                ?: rawText.replace(visualRegex, "").replace(spokenRegex, "").trim().ifBlank { null }
                            // If <spoken> tag exists, store both versions for TTS toggle
                            val hasSpokenBlock = spokenMatch != null
                            updateAiMessage(
                                currentMsgId, displayText, isStreaming = false, files = files,
                                statusLog = statusLog.toList(),
                                spokenText = if (hasSpokenBlock) spokenMatch?.groupValues?.getOrNull(1)?.trim() else null,
                                fullText = if (hasSpokenBlock) displayText else null,
                            )
                            notifier?.showReplyNotification(senderName = backend.displayName, message = displayText)
                            onSendComplete(fromVoice, displayText, spokenText)
                        }
                        "error" -> {
                            gotDone = true
                            updateAiMessage(currentMsgId, event.data, isStreaming = false)
                            onSendComplete(fromVoice, event.data)
                        }
                    }
                }
                // If the stream ended without a done/error event, finalize the message
                if (!gotDone) {
                    val finalText = if (accumulated.isNotBlank()) accumulated else "No response received."
                    updateAiMessage(currentMsgId, finalText, isStreaming = false)
                    onSendComplete(fromVoice, null)
                }
            } catch (e: Exception) {
                val msg = e.message ?: ""
                if (msg.contains("stream", ignoreCase = true) || msg.contains("reset", ignoreCase = true) || msg.contains("timeout", ignoreCase = true)) {
                    updateAiMessage(aiMsg.id, "Connection interrupted. Please try again.", isStreaming = false)
                } else {
                    updateAiMessage(aiMsg.id, "Error: $msg", isStreaming = false)
                }
                if (fromVoice) {
                    voiceController?.onAssistantReply("Sorry, the connection was interrupted.")
                }
                _state.value = _state.value.copy(isSending = false)
                processNextInQueue()
            }
        }
    }

    private fun onSendComplete(fromVoice: Boolean, replyText: String?, spokenText: String? = null) {
        if (fromVoice && replyText != null) {
            voiceController?.onAssistantReply(replyText)
        } else if (replyText != null) {
            // Use <spoken> block for TTS if available; fall back to full display text
            speakIfEnabled(spokenText?.takeIf { it.isNotBlank() } ?: replyText)
        }
        _state.value = _state.value.copy(isSending = false)
        processNextInQueue()
    }

    private fun processNextInQueue() {
        val next = pendingQueue.poll()
        if (next != null) {
            _state.value = _state.value.copy(queuedCount = pendingQueue.size)
            executeSend(text = next.text, fileUri = next.fileUri, fromVoice = next.fromVoice)
        } else {
            _state.value = _state.value.copy(queuedCount = 0)
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }

    fun dismissUpdate() {
        _state.value = _state.value.copy(updateDismissed = true)
    }

    fun installUpdate() {
        val update = _state.value.availableUpdate ?: return
        com.vessences.android.data.api.UpdateManager.downloadAndInstall(appContext, update.downloadUrl, update.versionName)
    }

    fun toggleTts() {
        val newValue = !_state.value.ttsEnabled
        _state.value = _state.value.copy(ttsEnabled = newValue)
        chatPrefs.setTtsEnabled(backendKey, newValue)
        if (!newValue) {
            tts.stop()
            _state.value = _state.value.copy(isSpeaking = false)
        }
    }

    fun stopSpeaking() {
        tts.stop()
        _state.value = _state.value.copy(isSpeaking = false)
    }

    fun speakText(text: String) {
        speakIfEnabled(text)
    }

    private var chatMediaPlayer: android.media.MediaPlayer? = null

    private fun speakIfEnabled(text: String) {
        if (!_state.value.ttsEnabled || text.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(isSpeaking = true)
            tts.speak(text)
            _state.value = _state.value.copy(isSpeaking = false)
            // Auto-listen after TTS completes (if enabled)
            if (chatPrefs.isAutoListenEnabled()) {
                autoListenAfterTts()
            }
        }
    }

    private suspend fun tryServerTts(text: String): Boolean {
        return try {
            val baseUrl = com.vessences.android.data.api.ApiClient.getJaneBaseUrl()
            val jsonBody = com.google.gson.Gson().toJson(mapOf("text" to text.take(500)))
            val request = okhttp3.Request.Builder()
                .url("$baseUrl/api/tts/generate")
                .post(jsonBody.toByteArray().toRequestBody("application/json".toMediaType()))
                .build()

            val response = withContext(Dispatchers.IO) {
                com.vessences.android.data.api.ApiClient.getOkHttpClient().newCall(request).execute()
            }

            if (!response.isSuccessful) {
                response.close()
                return false
            }

            // Save to temp file and play
            val tempFile = java.io.File.createTempFile("jane_tts_", ".wav", appContext.cacheDir)
            withContext(Dispatchers.IO) {
                response.body?.byteStream()?.use { input ->
                    tempFile.outputStream().use { output -> input.copyTo(output) }
                }
            }
            response.close()

            if (tempFile.length() == 0L) {
                tempFile.delete()
                return false
            }

            withContext(Dispatchers.Main) {
                kotlinx.coroutines.suspendCancellableCoroutine<Boolean> { cont ->
                    chatMediaPlayer?.release()
                    val mp = android.media.MediaPlayer()
                    chatMediaPlayer = mp
                    mp.setDataSource(tempFile.absolutePath)
                    mp.setOnPreparedListener { it.start() }
                    mp.setOnCompletionListener {
                        it.release()
                        chatMediaPlayer = null
                        tempFile.delete()
                        cont.resume(true)
                    }
                    mp.setOnErrorListener { _, _, _ ->
                        mp.release()
                        chatMediaPlayer = null
                        tempFile.delete()
                        cont.resume(false)
                        true
                    }
                    cont.invokeOnCancellation { mp.release(); chatMediaPlayer = null; tempFile.delete() }
                    mp.prepare()
                    mp.start()
                }
            }
        } catch (e: Exception) {
            false
        }
    }

    private fun autoListenAfterTts() {
        // Try VoiceController first (Vosk offline), fall back to Android SpeechRecognizer
        if (voiceController != null) {
            voiceController.startListeningWithTimeout(6000)
        } else {
            // Use Android's built-in SpeechRecognizer (no UI popup)
            startAndroidSpeechRecognizer()
        }
    }

    private fun startAndroidSpeechRecognizer() {
        viewModelScope.launch(Dispatchers.Main) {
            try {
                val recognizer = android.speech.SpeechRecognizer.createSpeechRecognizer(appContext)
                val intent = android.content.Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL, android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE, java.util.Locale.getDefault())
                    putExtra(android.speech.RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 6000L)
                    putExtra(android.speech.RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
                }
                recognizer.setRecognitionListener(object : android.speech.RecognitionListener {
                    override fun onResults(results: android.os.Bundle?) {
                        val matches = results?.getStringArrayList(android.speech.SpeechRecognizer.RESULTS_RECOGNITION)
                        val transcript = matches?.firstOrNull()?.trim() ?: ""
                        recognizer.destroy()
                        if (transcript.isNotEmpty()) {
                            sendMessage(transcript)
                        }
                    }
                    override fun onError(error: Int) { recognizer.destroy() }
                    override fun onReadyForSpeech(params: android.os.Bundle?) {}
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {}
                    override fun onPartialResults(partialResults: android.os.Bundle?) {}
                    override fun onEvent(eventType: Int, params: android.os.Bundle?) {}
                })
                recognizer.startListening(intent)
            } catch (e: Exception) {
                // Speech recognition not available — silently fail
            }
        }
    }

    fun clearSession() {
        cancelCurrentResponse()
        // End the current session on the server (kills Claude CLI session too)
        viewModelScope.launch { try { repo.endJaneSession(sessionId) } catch (_: Exception) {} }
        // Clear all messages and persisted chat
        _state.value = _state.value.copy(messages = emptyList(), error = null)
        try { chatPersistence.saveMessages(backendKey, emptyList()) } catch (_: Exception) {}
        // Immediately re-initialize with fresh context (show greeting)
        if (backend == com.vessences.android.data.repository.ChatBackend.JANE) {
            initSession(showGreeting = true)
        }
    }

    fun setAlwaysListeningEnabled(enabled: Boolean) {
        voiceSettings?.setAlwaysListeningEnabled(enabled)
        voiceController?.setAlwaysListeningEnabled(enabled)
    }

    fun syncVoicePreferences() {
        voiceController?.setAlwaysListeningEnabled(voiceSettings?.isAlwaysListeningEnabled() ?: false)
    }

    fun startPushToTalk() {
        voiceController?.startPushToTalk()
    }

    fun stopPushToTalk() {
        voiceController?.stopPushToTalk()
    }

    fun clearVoiceError() {
        voiceController?.clearError()
    }

    private fun updateAiMessage(
        id: String,
        text: String,
        isStreaming: Boolean,
        status: String? = null,
        statusLog: List<String> = emptyList(),
        files: List<com.vessences.android.data.model.StreamEvent.FileRef> = emptyList(),
        spokenText: String? = null,
        fullText: String? = null,
    ) {
        _state.value = _state.value.copy(
            messages = _state.value.messages.map { msg ->
                if (msg.id == id) msg.copy(
                    text = text,
                    isStreaming = isStreaming,
                    statusText = status,
                    statusLog = if (statusLog.isNotEmpty()) statusLog else msg.statusLog,
                    files = files,
                    spokenText = spokenText ?: msg.spokenText,
                    fullText = fullText ?: msg.fullText,
                )
                else msg
            }
        )
    }

    override fun onCleared() {
        // Force-save messages before cleanup (catches mid-stream navigation)
        val messages = _state.value.messages
        if (messages.isNotEmpty()) {
            try { chatPersistence.saveMessages(backendKey, messages) } catch (_: Exception) {}
        }
        super.onCleared()
        voiceController?.release()
        tts.shutdown()
        liveListener.stop()
        announcementPoller.stop()
        if (backend == ChatBackend.JANE) {
            viewModelScope.launch { repo.endJaneSession(sessionId) }
        }
    }
}
