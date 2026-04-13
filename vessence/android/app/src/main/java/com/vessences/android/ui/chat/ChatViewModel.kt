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
import com.vessences.android.voice.HybridTtsManager
import com.vessences.android.voice.SentenceTtsQueue
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
import android.os.PowerManager
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
    val wakeWordTriggered: Boolean = false,
)

class ChatViewModel(
    context: Context,
    private val backend: ChatBackend,
) : ViewModel() {
    private val appContext = context.applicationContext
    private val repo = ChatRepository()
    private val backendKey = backend.name.lowercase()
    private val chatPersistence = ChatPersistence(appContext)
    private val chatPrefs = ChatPreferences(appContext)
    private val sessionId = if (backend == ChatBackend.JANE) chatPrefs.getJaneSessionId()
                            else "${backendKey}_android_${UUID.randomUUID().toString().take(8)}"
    private val pendingQueue = ConcurrentLinkedQueue<PendingMessage>()
    private var currentStreamJob: Job? = null
    private val liveListener = LiveBroadcastListener(viewModelScope, sessionId.take(12))
    private val announcementPoller = AnnouncementPoller(viewModelScope, appContext)
    private val tts = HybridTtsManager(appContext)

    // Jane Phone Tools (Phase 1 scaffolding): dispatcher + action queue.
    // The dispatcher's handler registry is empty in Phase 1; Phase 2 populates
    // it with contacts / SMS / messages handlers. Feature-flag-gated via
    // Constants.PREF_PHONE_TOOLS_ENABLED (default OFF) so this scaffolding
    // ships with zero user-visible change.
    private val toolActionQueue: com.vessences.android.tools.ActionQueue =
        com.vessences.android.tools.ActionQueue().also { it.attachTts(tts.localTts) }
    private val toolDispatcher: com.vessences.android.tools.ClientToolDispatcher =
        com.vessences.android.tools.ClientToolDispatcher(toolActionQueue)

    // Wake lock to keep network alive during chat streaming when screen is off
    private var streamWakeLock: PowerManager.WakeLock? = null

    // Track last transient-error retry to avoid retry loops on flaky network
    private var lastTransientRetryAt: Long = 0L

    private fun acquireStreamWakeLock() {
        if (streamWakeLock?.isHeld == true) return
        val pm = appContext.getSystemService(Context.POWER_SERVICE) as PowerManager
        streamWakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "vessence:chat_streaming",
        ).apply { acquire(10 * 60 * 1000L) } // 10 min safety timeout
    }

    private fun releaseStreamWakeLock() {
        streamWakeLock?.let { if (it.isHeld) it.release() }
        streamWakeLock = null
    }

    /** Emits a playlist ID when Jane responds with [MUSIC_PLAY:id]. UI observes and navigates. */
    private val _musicPlayRequest = MutableStateFlow<String?>(null)
    val musicPlayRequest: StateFlow<String?> = _musicPlayRequest
    fun consumeMusicPlayRequest() { _musicPlayRequest.value = null }

    private val _state = MutableStateFlow(
        ChatUiState(
            messages = try { chatPersistence.loadMessages(backendKey) } catch (_: Exception) { emptyList() },
            ttsEnabled = chatPrefs.isTtsEnabled(backendKey),
        )
    )
    val state: StateFlow<ChatUiState> = _state

    private val notifier: ChatNotificationManager? = try { ChatNotificationManager(appContext) } catch (_: Throwable) { null }
    private val voiceSettings: VoiceSettingsRepository? = try { VoiceSettingsRepository(appContext) } catch (_: Throwable) { null }
    private val voiceController: VoiceController? = try {
        VoiceController(
            context = appContext,
            backend = backend,
            externalScope = viewModelScope,
            initialAlwaysListening = false,  // AlwaysListeningService handles wake word, not VoiceController
            onStateChanged = { voiceState ->
                _state.value = _state.value.copy(voice = voiceState)
            },
            onTranscriptReady = { transcript ->
                if (com.vessences.android.ui.chat.EndPhraseDetector.isEndPhrase(transcript)) {
                    android.util.Log.i("ChatVM", "End phrase from VoiceController: '$transcript'")
                    endVoiceConversation()
                } else {
                    sendMessage(transcript, fromVoice = true)
                }
            },
        )
    } catch (_: Throwable) { null }

    init {
        voiceController?.onSpeakingDone = {
            _state.value = _state.value.copy(isSpeaking = false)
        }
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
                        .post(ByteArray(0).toRequestBody(null))
                        .build()
                    com.vessences.android.data.api.ApiClient.getOkHttpClient().newCall(request).execute().close()
                } catch (_: Exception) {}
            }
            // Headless STT bridge: listen/partial/result callbacks for in-app voice UI
            com.vessences.android.SttResultBus.onListening = { active ->
                val newVoice = _state.value.voice.copy(
                    isCapturingCommand = active,
                    transcriptPreview = if (!active) "" else _state.value.voice.transcriptPreview,
                    status = if (active) "Listening..." else null,
                )
                _state.value = _state.value.copy(voice = newVoice)
            }
            com.vessences.android.SttResultBus.onPartialResult = { preview ->
                _state.value = _state.value.copy(
                    voice = _state.value.voice.copy(transcriptPreview = preview)
                )
            }
            com.vessences.android.SttResultBus.onResult = { spoken ->
                // Clear listening UI immediately
                _state.value = _state.value.copy(
                    voice = _state.value.voice.copy(
                        isCapturingCommand = false,
                        transcriptPreview = "",
                        status = null,
                    )
                )
                if (spoken != null && spoken.isNotBlank()) {
                    if (com.vessences.android.ui.chat.EndPhraseDetector.isEndPhrase(spoken)) {
                        endVoiceConversation()
                    } else {
                        sendMessage(spoken, fromVoice = true)
                    }
                } else {
                    // Silence timeout or cancel — end conversation
                    endVoiceConversation()
                }
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
        releaseStreamWakeLock()
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

        acquireStreamWakeLock()
        currentStreamJob = viewModelScope.launch(Dispatchers.IO) {
            var gotDone = false
            // Sentence-level TTS: accumulate text, fire TTS per sentence during streaming
            var sentenceQueue: SentenceTtsQueue? = null
            val sentenceBuffer = StringBuilder()
            var sentenceTtsActive = false
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

                // Phone tools: drain any pending tool results and prepend them
                // as [TOOL_RESULT:{json}] markers so Jane's mind sees what the
                // last phone-tool invocation did. jane_proxy strips these from
                // the user-visible bubble before showing the persisted message.
                val outgoingText = prependPendingToolResults(text)

                val flow = repo.streamChat(backend, outgoingText, sessionId, resolvedFileContext, ttsEnabled = fromVoice)
                var accumulated = ""
                var statusLog = mutableListOf<String>()
                // Incremental ACK parser state
                val visibleBuffer = StringBuilder()
                val ackBuffer = StringBuilder()
                var inAckBlock = false
                var ackSpoken = false
                var currentMsgId = aiMsg.id
                var files = emptyList<com.vessences.android.data.model.StreamEvent.FileRef>()
                var toolCallDispatched = false  // track if a tool call fired this turn
                var serverConversationEnd = false  // server signalled END_CONVERSATION

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
                                // Pre-warm TTS model as soon as we know Jane is working
                                if (fromVoice) tts.ensureWarm()
                                // Give Compose a chance to render status updates before the next
                                // event arrives — without this, IO-thread StateFlow conflation
                                // can swallow the status phase entirely when deltas follow fast.
                                kotlinx.coroutines.delay(60)
                            }
                        }
                        "thought" -> {
                            if (event.data.isNotEmpty()) {
                                statusLog.add(event.data)
                                updateAiMessage(currentMsgId, accumulated, isStreaming = true, status = "Thinking…", statusLog = statusLog.toList())
                                kotlinx.coroutines.delay(60)
                            }
                        }
                        "tool_use" -> {
                            if (event.data.isNotEmpty()) {
                                statusLog.add(event.data)
                                updateAiMessage(currentMsgId, accumulated, isStreaming = true, status = "Working…", statusLog = statusLog.toList())
                                kotlinx.coroutines.delay(60)
                            }
                        }
                        "tool_result" -> {
                            if (event.data.isNotEmpty()) {
                                statusLog.add(event.data)
                                updateAiMessage(currentMsgId, accumulated, isStreaming = true, status = null, statusLog = statusLog.toList())
                            }
                        }
                        "provider_error" -> {
                            gotDone = true
                            try {
                                val errJson = com.google.gson.Gson().fromJson(event.data, com.google.gson.JsonObject::class.java)
                                val provider = errJson.get("provider")?.asString ?: "provider"
                                val category = errJson.get("category")?.asString ?: "error"
                                val alts = errJson.getAsJsonArray("alternatives")?.map { it.asString } ?: emptyList()
                                val categoryLabel = if (category == "billing") "billing/quota issue" else "rate limit"
                                val errorMsg = "⚠️ ${provider.replaceFirstChar { it.uppercase() }} hit a $categoryLabel."
                                updateAiMessage(currentMsgId, errorMsg, isStreaming = false, switchAlternatives = alts)
                            } catch (e: Exception) {
                                updateAiMessage(currentMsgId, event.data.ifEmpty { "⚠️ Provider error." }, isStreaming = false)
                            }
                            onSendComplete(fromVoice, null)
                        }
                        "client_tool_call" -> {
                            // Jane Phone Tools: server-extracted [[CLIENT_TOOL:...]] marker
                            // arriving as a structured SSE event. Dispatcher gates on the
                            // PREF_PHONE_TOOLS_ENABLED feature flag (default OFF in Phase 1).
                            try {
                                toolDispatcher.dispatchRaw(event.data, appContext)
                                toolCallDispatched = true
                            } catch (e: Exception) {
                                android.util.Log.w("ChatVM", "tool dispatch failed: ${e.message}")
                            }
                        }
                        "ack" -> {
                            // Quick ack from gemma4 — speak it for immediate feedback.
                            // Uses raw tts.speak() which does NOT trigger auto-listen.
                            // Auto-listen only fires after the "done" event via onSendComplete.
                            val ackText = event.data.trim()
                            if (ackText.isNotBlank() && !ackSpoken) {
                                ackSpoken = true
                                if (fromVoice) {
                                    viewModelScope.launch { tts.speak(ackText) }
                                }
                                statusLog.add(ackText)
                                updateAiMessage(currentMsgId, accumulated, isStreaming = true, status = ackText, statusLog = statusLog.toList())
                            }
                        }
                        "conversation_end" -> {
                            // Server signalled END_CONVERSATION — after TTS completes, switch
                            // back to wake-word passive mode instead of reopening active STT.
                            serverConversationEnd = true
                        }
                        "delta" -> {
                            // Incremental ACK parser — never leaks ACK markup into visible text
                            for (ch in event.data) {
                                if (inAckBlock) {
                                    ackBuffer.append(ch)
                                    // Check if we just closed [/ACK]
                                    if (ackBuffer.endsWith("[/ACK]")) {
                                        // Extract ACK content, speak it once
                                        val ackContent = ackBuffer.toString()
                                            .removePrefix("[ACK]")
                                            .removeSuffix("[/ACK]")
                                            .trim()
                                        if (ackContent.isNotBlank() && !ackSpoken) {
                                            ackSpoken = true
                                            if (fromVoice) {
                                                viewModelScope.launch { tts.speak(ackContent) }
                                            }
                                            statusLog.add(ackContent)
                                        }
                                        ackBuffer.clear()
                                        inAckBlock = false
                                    }
                                } else {
                                    visibleBuffer.append(ch)
                                    // Check if visible buffer ends with [ACK] — start of ACK block
                                    if (visibleBuffer.endsWith("[ACK]")) {
                                        // Remove the [ACK] tag from visible text
                                        visibleBuffer.setLength(visibleBuffer.length - "[ACK]".length)
                                        inAckBlock = true
                                        ackBuffer.clear()
                                        ackBuffer.append("[ACK]")
                                    }
                                }
                            }
                            // Only show non-ACK content in the bubble.
                            // Strip all markup tags so they never flash in the UI.
                            val rawAccumulated = visibleBuffer.toString()
                            accumulated = rawAccumulated
                                .replace(Regex("<spoken>[\\s\\S]*?</spoken>", RegexOption.IGNORE_CASE), "")
                                .replace(Regex("<visual>([\\s\\S]*?)</visual>", RegexOption.IGNORE_CASE)) { it.groupValues[1] }
                                .replace(Regex("</?(?:spoken|visual|think|thinking|artifact)>", RegexOption.IGNORE_CASE), "")
                                // Strip leaked [[CLIENT_TOOL:...]] markers during streaming
                                .replace(Regex("\\[\\[CLIENT_TOOL:[a-z][a-z0-9_.]*:\\{[\\s\\S]*?\\}\\]\\]"), "")
                                .trim()
                            val ackStatus = if (statusLog.isNotEmpty()) statusLog.last() else null

                            // Sentence-level TTS: detect complete sentences and submit for generation
                            if (fromVoice && HybridTtsManager.USE_SERVER_TTS) {
                                // Initialize queue on first delta
                                if (sentenceQueue == null) {
                                    sentenceQueue = SentenceTtsQueue(appContext.cacheDir, viewModelScope)
                                    sentenceQueue!!.startPlayback()
                                    sentenceTtsActive = true
                                }
                                // Feed raw text (without markup) into sentence buffer
                                val cleanDelta = event.data
                                    .replace(Regex("</?(?:spoken|visual|think|thinking|artifact)>", RegexOption.IGNORE_CASE), "")
                                    .replace(Regex("\\[\\[CLIENT_TOOL:[a-z][a-z0-9_.]*:\\{[\\s\\S]*?\\}\\]\\]"), "")
                                sentenceBuffer.append(cleanDelta)
                                // Extract complete sentences (ending with . ! ?)
                                val sentenceRegex = Regex("([^.!?]+[.!?])\\s*")
                                val matches = sentenceRegex.findAll(sentenceBuffer.toString()).toList()
                                if (matches.isNotEmpty()) {
                                    val consumed = matches.last().range.last + 1
                                    for (m in matches) {
                                        val sentence = m.groupValues[1].trim()
                                        if (sentence.length > 3) {  // skip tiny fragments
                                            sentenceQueue!!.submitSentence(sentence)
                                        }
                                    }
                                    sentenceBuffer.delete(0, consumed)
                                }
                            }

                            // In voice mode with server TTS, hide text while speaking —
                            // the user hears it via audio, text reveals when TTS finishes.
                            // For Android TTS or non-voice mode, show text normally.
                            if (sentenceTtsActive) {
                                updateAiMessage(currentMsgId, "", isStreaming = true, status = "Speaking\u2026", statusLog = statusLog.toList())
                            } else {
                                updateAiMessage(currentMsgId, accumulated, isStreaming = true, status = ackStatus, statusLog = statusLog.toList())
                            }
                        }
                        "done" -> {
                            gotDone = true
                            var rawText = if (event.data.isNotEmpty()) event.data else accumulated
                            files = event.files
                            // Strip [ACK] tags (already spoken during streaming)
                            val ackRegex = Regex("\\[ACK\\][\\s\\S]*?\\[/ACK\\]\\s*")
                            rawText = rawText.replace(ackRegex, "").trim()
                            // Strip any leaked [[CLIENT_TOOL:...]] markers so TTS never
                            // speaks raw tool syntax (server should strip these, but
                            // belt-and-suspenders for edge cases).
                            rawText = rawText.replace(
                                Regex("\\[\\[CLIENT_TOOL:[a-z][a-z0-9_.]*:\\{[\\s\\S]*?\\}\\]\\]"),
                                ""
                            ).trim()
                            // TTS mode: main text is spoken-friendly; <visual> blocks are display-only
                            val visualRegex = Regex("<visual>([\\s\\S]*?)</visual>", RegexOption.IGNORE_CASE)
                            // For display: keep visual content but strip the tags; also strip legacy <spoken> tags
                            val spokenRegex = Regex("<spoken>([\\s\\S]*?)</spoken>", RegexOption.IGNORE_CASE)
                            val spokenMatch = spokenRegex.find(rawText)
                            // Check for music play command: [MUSIC_PLAY:playlist_id]
                            val musicPlayRegex = Regex("\\[MUSIC_PLAY:([^\\]]+)\\]")
                            val musicMatch = musicPlayRegex.find(rawText)
                            if (musicMatch != null) {
                                val playlistId = musicMatch.groupValues[1]
                                android.util.Log.i("ChatVM", "Music play command detected: playlist=$playlistId — ending conversation")
                                _musicPlayRequest.value = playlistId
                                com.vessences.android.MusicPlayNavigationState.requestPlay(playlistId)
                                // Music = conversation ending event — no STT after this
                                endVoiceConversation()
                            }
                            rawText = rawText.replace(musicPlayRegex, "").trim()

                            val displayText = rawText.replace(visualRegex) { it.groupValues[1] }
                                .replace(spokenRegex, "").trimEnd().ifBlank { rawText }
                            // For TTS: if legacy <spoken> block exists, use it;
                            // otherwise strip <visual> blocks and read the rest
                            val spokenText = spokenMatch?.groupValues?.getOrNull(1)?.trim()
                                ?: rawText.replace(visualRegex, "").replace(spokenRegex, "").trim().ifBlank { null }
                            // If <spoken> tag exists, store both versions for TTS toggle
                            val hasSpokenBlock = spokenMatch != null
                            // If sentence-level TTS was active, flush remaining buffer,
                            // wait for all audio to finish, THEN reveal the text.
                            // If a tool call was dispatched this turn (e.g., read_inbox),
                            // wait for the handler to finish, then auto-send the tool
                            // results as a follow-up so Jane can respond with the data.
                            // This prevents the dead-end where STT re-launches before
                            // the user has heard anything.
                            if (toolCallDispatched && com.vessences.android.tools.PendingToolResultBuffer.inFlightHandlers.get() > 0) {
                                android.util.Log.i("ChatVM", "Tool call in-flight — waiting for result before completing turn")
                                // Show interim message
                                updateAiMessage(currentMsgId, displayText.ifBlank { "Working on it..." }, isStreaming = true, status = "Waiting for phone data...")
                                // Wait up to 10s for the tool handler to finish
                                val allToolResults = com.vessences.android.tools.PendingToolResultBuffer.awaitAndDrainAll(10_000)
                                // Filter: only send follow-up for tools that return data
                                // for Jane to analyze (e.g. messages.fetch_unread).
                                // Fire-and-forget tools (sms_send_direct, sync.force_sms)
                                // don't need a follow-up — the action is already done.
                                val FIRE_AND_FORGET = setOf(
                                    "contacts.sms_send_direct",
                                    "contacts.sms_send",
                                    "contacts.sms_draft",
                                    "contacts.sms_cancel",
                                    "sync.force_sms",
                                )
                                val toolResults = allToolResults.filter { it.tool !in FIRE_AND_FORGET }
                                if (toolResults.isNotEmpty()) {
                                    android.util.Log.i("ChatVM", "Got ${toolResults.size} tool result(s) — auto-sending follow-up")
                                    // Build the tool result prefix
                                    val sb = StringBuilder()
                                    for (r in toolResults) {
                                        val obj = com.google.gson.JsonObject()
                                        obj.addProperty("tool", r.tool)
                                        obj.addProperty("call_id", r.callId)
                                        obj.addProperty("status", r.status)
                                        obj.addProperty("message", r.message)
                                        if (r.data != null) obj.add("data", r.data)
                                        sb.append("[TOOL_RESULT:").append(com.google.gson.Gson().toJson(obj).replace("\n", " ")).append("] ")
                                    }
                                    // Auto-send a follow-up with the tool results
                                    // This triggers a new brain turn with the data
                                    val followUp = sb.toString() + "(tool results from previous request — please analyze and respond)"
                                    updateAiMessage(currentMsgId, displayText.ifBlank { "Got the data, analyzing..." }, isStreaming = false)
                                    _state.value = _state.value.copy(isSending = false)
                                    // Re-send with tool results prepended
                                    sendMessage(followUp, fromVoice = fromVoice)
                                    return@collect
                                }
                                // If no results after 10s, fall through to normal completion
                                android.util.Log.w("ChatVM", "Tool result wait timed out — completing normally")
                            }
                            if (sentenceTtsActive && sentenceQueue != null) {
                                val remaining = sentenceBuffer.toString().trim()
                                if (remaining.length > 3) {
                                    sentenceQueue!!.submitSentence(remaining)
                                }
                                sentenceBuffer.clear()
                                sentenceQueue!!.finishSubmitting()
                                sentenceQueue!!.awaitCompletion()
                                sentenceTtsActive = false
                                // Now reveal the full text after TTS finished
                                updateAiMessage(
                                    currentMsgId, displayText, isStreaming = false, files = files,
                                    statusLog = statusLog.toList(),
                                    spokenText = if (hasSpokenBlock) spokenMatch?.groupValues?.getOrNull(1)?.trim() else null,
                                    fullText = if (hasSpokenBlock) displayText else null,
                                )
                                notifier?.showReplyNotification(senderName = backend.displayName, message = displayText)
                                // Skip normal TTS in onSendComplete — already played
                                onSendComplete(fromVoice = false, displayText, spokenText)
                                // But still handle auto-listen for voice mode
                                if (fromVoice) {
                                    _state.value = _state.value.copy(isSpeaking = false)
                                    val lastUserMsg = _state.value.messages.lastOrNull { it.isUser }?.text ?: ""
                                    if (!serverConversationEnd && !isConversationEnding(lastUserMsg) && chatPrefs.isAutoListenEnabled()) {
                                        com.vessences.android.MainActivity.instance?.launchStt()
                                    } else {
                                        endVoiceConversation()
                                    }
                                }
                            } else {
                                // Non-server-TTS path: show text immediately, then speak
                                updateAiMessage(
                                    currentMsgId, displayText, isStreaming = false, files = files,
                                    statusLog = statusLog.toList(),
                                    spokenText = if (hasSpokenBlock) spokenMatch?.groupValues?.getOrNull(1)?.trim() else null,
                                    fullText = if (hasSpokenBlock) displayText else null,
                                )
                                notifier?.showReplyNotification(senderName = backend.displayName, message = displayText)
                                onSendComplete(fromVoice, displayText, spokenText, serverConversationEnd)
                            }
                        }
                        "error" -> {
                            gotDone = true
                            val errorText = event.data ?: ""
                            // Detect server-restart/busy errors and handle gracefully:
                            // speak a friendly message, auto-retry after a delay, resume listening.
                            val isServerBusy = errorText.contains("busy", ignoreCase = true)
                                || errorText.contains("restarting", ignoreCase = true)
                                || errorText.contains("unavailable", ignoreCase = true)
                                || errorText.contains("empty response", ignoreCase = true)
                            if (isServerBusy) {
                                val friendlyMsg = "Jane is briefly restarting. Give me about thirty seconds and I'll be right back."
                                updateAiMessage(currentMsgId, friendlyMsg, isStreaming = false)
                                if (fromVoice) {
                                    viewModelScope.launch {
                                        tts.speak(friendlyMsg)
                                        // Wait 30 seconds then auto-retry
                                        kotlinx.coroutines.delay(30_000)
                                        val retryMsg = "I'm back. Let me try that again."
                                        viewModelScope.launch { tts.speak(retryMsg) }
                                        // Re-launch always-listen so user can speak again
                                        _state.value = _state.value.copy(isSending = false)
                                        if (chatPrefs.isAutoListenEnabled()) {
                                            com.vessences.android.MainActivity.instance?.launchStt()
                                        }
                                    }
                                } else {
                                    // Text mode: just show the message, auto-clear sending state
                                    viewModelScope.launch {
                                        kotlinx.coroutines.delay(30_000)
                                        _state.value = _state.value.copy(
                                            error = null
                                        )
                                    }
                                }
                                _state.value = _state.value.copy(isSending = false)
                                processNextInQueue()
                            } else {
                                updateAiMessage(currentMsgId, errorText, isStreaming = false)
                                onSendComplete(fromVoice, errorText)
                            }
                        }
                    }
                }
                // If the stream ended without a done/error event, finalize the message
                if (!gotDone) {
                    val finalText = if (accumulated.isNotBlank()) accumulated else "No response received."
                    updateAiMessage(currentMsgId, finalText, isStreaming = false)
                    onSendComplete(fromVoice, finalText)
                }
            } catch (e: Exception) {
                val msg = e.message ?: ""
                // Send full error details to server diagnostics so we can see
                // the real stack trace and exception class instead of just "abort"
                try {
                    val sw = java.io.StringWriter()
                    e.printStackTrace(java.io.PrintWriter(sw))
                    com.vessences.android.DiagnosticReporter.report(
                        "chat_error",
                        "Stream error: ${e.javaClass.simpleName}: ${msg.take(200)}",
                        mapOf(
                            "exception_class" to e.javaClass.name,
                            "message" to msg,
                            "stack_trace" to sw.toString().take(2000),
                            "from_voice" to fromVoice.toString(),
                        )
                    )
                } catch (_: Exception) {}
                val isTransient = msg.contains("stream", ignoreCase = true)
                    || msg.contains("reset", ignoreCase = true)
                    || msg.contains("timeout", ignoreCase = true)
                    || msg.contains("refused", ignoreCase = true)
                    || msg.contains("connect", ignoreCase = true)
                    || msg.contains("abort", ignoreCase = true)
                    || msg.contains("broken pipe", ignoreCase = true)
                    || msg.contains("eof", ignoreCase = true)
                    || msg.contains("unexpected end", ignoreCase = true)
                    || msg.contains("canceled", ignoreCase = true)
                    || msg.contains("cancelled", ignoreCase = true)
                if (isTransient) {
                    android.util.Log.w("ChatVM", "Transient connection error: ${msg.take(120)}")
                    val friendlyMsg = "Jane seems to be restarting. I'll try again in about thirty seconds."
                    updateAiMessage(aiMsg.id, friendlyMsg, isStreaming = false)
                    if (fromVoice) {
                        viewModelScope.launch {
                            tts.speak(friendlyMsg)
                            kotlinx.coroutines.delay(30_000)
                            val retryMsg = "I'm back. Let me try that again."
                            viewModelScope.launch { tts.speak(retryMsg) }
                            _state.value = _state.value.copy(isSending = false)
                            if (chatPrefs.isAutoListenEnabled()) {
                                com.vessences.android.MainActivity.instance?.launchStt()
                            }
                        }
                    }
                } else {
                    updateAiMessage(aiMsg.id, "Error: $msg", isStreaming = false)
                    if (fromVoice) {
                        voiceController?.onAssistantReply("Sorry, something went wrong.", chatPrefs.isAutoListenEnabled())
                    }
                }
                _state.value = _state.value.copy(isSending = false)
                processNextInQueue()
            } finally {
                releaseStreamWakeLock()
            }
        }
    }

    private fun isConversationEnding(text: String): Boolean {
        val lower = text.lowercase().trim()
        val endings = listOf(
            "we're done", "we are done", "were done",
            "goodbye", "good bye", "bye",
            "that's all", "that is all",
            "talk to you later", "talk later",
            "i'm done", "im done", "i am done",
            "end conversation", "stop listening",
            "okay we're done", "okay we are done",
            "ok we're done", "ok we are done",
            "thanks that's it", "that's it",
            "never mind", "nevermind",
        )
        return endings.any { lower.contains(it) }
    }

    private fun onSendComplete(fromVoice: Boolean, replyText: String?, spokenText: String? = null, serverConversationEnd: Boolean = false) {
        if (fromVoice) {
            val textToSpeak = spokenText?.takeIf { it.isNotBlank() }
                ?: replyText?.takeIf { it.isNotBlank() }
                ?: ""  // empty = silent end, no misleading "I finished" message

            // Check if the user's last message was a conversation-ending phrase,
            // OR if the server explicitly signalled END_CONVERSATION.
            val lastUserMsg = _state.value.messages.lastOrNull { it.isUser }?.text ?: ""
            val conversationOver = serverConversationEnd || isConversationEnding(lastUserMsg)
            // If music is about to play, sttActive was already cleared by endVoiceConversation()
            // in the MUSIC_PLAY handler. Treat it as a conversation-ending event — no STT re-launch.
            val musicPlaying = !com.vessences.android.voice.WakeWordBridge.sttActive

            // If reply was empty (error / tool-only response), end silently — don't say anything misleading
            if (textToSpeak.isBlank()) {
                endVoiceConversation()
                _state.value = _state.value.copy(isSending = false)
                processNextInQueue()
                return
            }

            // If VoiceController is waiting for a reply, use it (handles TTS + auto re-listen)
            if (voiceController != null && voiceController.isWaitingForReply()) {
                _state.value = _state.value.copy(isSpeaking = true)
                voiceController.onAssistantReply(textToSpeak, chatPrefs.isAutoListenEnabled() && !conversationOver && !musicPlaying)
            } else {
                // Voice came from Android SpeechRecognizer (mic button / wake word), not VoiceController
                viewModelScope.launch {
                    _state.value = _state.value.copy(isSpeaking = true)
                    tts.speak(textToSpeak)
                    // If stopSpeaking() was called while TTS was active, it already
                    // set isSpeaking=false and called endVoiceConversation().
                    // Don't re-launch STT in that case.
                    if (!_state.value.isSpeaking) return@launch
                    _state.value = _state.value.copy(isSpeaking = false)
                    if (conversationOver || musicPlaying) {
                        // Music playing or user said goodbye — stop listening, release mic for wake word
                        endVoiceConversation()
                    } else if (chatPrefs.isAutoListenEnabled()) {
                        // Unified path: trigger Google STT popup (same as mic button + wake word)
                        com.vessences.android.MainActivity.instance?.launchStt()
                    } else {
                        // Auto-listen disabled — conversation over, release mic for wake word
                        endVoiceConversation()
                    }
                }
            }
        }
        // Text-initiated: no speech — user reads the response
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
        // Dismiss banner after starting download — user will install from notification
        _state.value = _state.value.copy(updateDismissed = true)
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
        voiceController?.stopTts()
        _state.value = _state.value.copy(isSpeaking = false)
        // Stop Speaking = conversation ends immediately (no STT), but always-listen resumes
        endVoiceConversation()
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
            // Auto-listen removed here — only onSendComplete triggers auto-listen.
            // This prevents STT from opening prematurely after acks or intermediate speech.
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
        // Trigger the same Google STT UI as the mic button and wake word
        com.vessences.android.MainActivity.instance?.launchStt()
    }



    /**
     * End the voice conversation: release the sttActive flag and restart
     * the always-listening service so it resumes wake word detection.
     */
    /** Set to true when conversation started from wake word trigger (screen was off) */
    var cameFromWakeWord: Boolean = false

    private fun endVoiceConversation() {
        com.vessences.android.voice.WakeWordBridge.sttActive = false
        // Restart wake word service if always-listen is enabled
        if (voiceSettings?.isAlwaysListeningEnabled() == true) {
            com.vessences.android.voice.AlwaysListeningService.start(appContext)
            android.util.Log.i("ChatVM", "Restarted AlwaysListeningService after conversation end")
        }
        // If we came from wake word trigger, return app to background (lock screen)
        if (cameFromWakeWord) {
            cameFromWakeWord = false
            val activity = appContext as? android.app.Activity
            activity?.moveTaskToBack(true)
            android.util.Log.i("ChatVM", "Returning to background after wake-word conversation")
        }
    }

    private fun isConversationEndPhrase(text: String): Boolean {
        val normalized = text.lowercase(java.util.Locale.US).trim()
        val endPhrases = listOf(
            "we're done", "we are done", "ok we're done", "ok we are done",
            "this conversation ends", "end conversation", "conversation over",
            "that's all", "that is all", "ok that's all",
            "goodbye", "good bye", "bye jane", "bye bye",
            "stop listening", "stop", "never mind", "nevermind",
            "thank you jane", "thanks jane", "thanks that's it",
            "ok done", "okay done", "i'm done", "i am done",
        )
        return endPhrases.any { phrase ->
            if (phrase.length <= 5) {
                normalized == phrase || normalized.startsWith("$phrase ") || normalized.endsWith(" $phrase")
            } else {
                normalized.contains(phrase)
            }
        }
    }

    private fun showSystemMessage(text: String) {
        val msg = ChatMessage(
            id = java.util.UUID.randomUUID().toString(),
            text = text,
            isUser = false,
        )
        _state.value = _state.value.copy(messages = _state.value.messages + msg)
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
        // AlwaysListeningService handles wake word — NOT VoiceController
        // Don't call voiceController?.setAlwaysListeningEnabled() — it would start
        // a competing wake word detector that fights the service for the mic
    }

    fun syncVoicePreferences() {
        // No-op: VoiceController no longer manages always-listening state
    }

    fun clearWakeWordTrigger() {
        _state.value = _state.value.copy(wakeWordTriggered = false)
    }

    /** Called by VessencesApp when wake word fires — single entry point */
    fun triggerWakeWord() {
        cameFromWakeWord = true
        com.vessences.android.MainActivity.instance?.launchStt()
    }

    fun startPushToTalk() {
        voiceController?.startPushToTalk()
    }

    fun stopPushToTalk() {
        voiceController?.stopPushToTalk()
    }

    fun cancelListening() {
        voiceController?.cancelListening()
    }

    /** Stop listening immediately and return to always-listen (wake word) mode. */
    fun stopListeningAndReturnToWakeWord() {
        voiceController?.cancelListening()
        com.vessences.android.voice.WakeWordBridge.sttActive = false
        if (voiceSettings?.isAlwaysListeningEnabled() == true) {
            com.vessences.android.voice.AlwaysListeningService.start(appContext)
            android.util.Log.i("ChatVM", "X button: cancelled STT, restarted AlwaysListeningService")
        }
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
        switchAlternatives: List<String> = emptyList(),
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
                    switchAlternatives = if (switchAlternatives.isNotEmpty()) switchAlternatives else msg.switchAlternatives,
                )
                else msg
            }
        )
    }

    fun switchProvider(provider: String) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                _state.value = _state.value.copy(isSending = true)
                val baseUrl = com.vessences.android.data.api.ApiClient.getJaneBaseUrl()
                val jsonBody = com.google.gson.Gson().toJson(mapOf("provider" to provider))
                val request = okhttp3.Request.Builder()
                    .url("$baseUrl/api/jane/switch-provider")
                    .post(jsonBody.toByteArray().toRequestBody("application/json".toMediaType()))
                    .build()
                val response = com.vessences.android.data.api.ApiClient.getOkHttpClient().newCall(request).execute()
                val body = response.body?.string() ?: "{}"
                val result = com.google.gson.Gson().fromJson(body, com.google.gson.JsonObject::class.java)
                response.close()

                val ok = result.get("ok")?.asBoolean ?: false
                if (ok) {
                    val model = result.get("model")?.asString ?: provider
                    val needsAuth = result.get("needs_auth")?.asBoolean ?: false
                    val msg = if (needsAuth) {
                        "🔑 ${provider.replaceFirstChar { it.uppercase() }} needs authentication. Please log in from the web interface."
                    } else {
                        "✅ Switched to $model. You can continue chatting."
                    }
                    val aiMsg = ChatMessage(text = msg, isUser = false)
                    _state.value = _state.value.copy(
                        messages = _state.value.messages.map {
                            if (it.switchAlternatives.isNotEmpty()) it.copy(switchAlternatives = emptyList()) else it
                        } + aiMsg,
                        isSending = false,
                    )
                } else {
                    val error = result.get("error")?.asString ?: "Unknown error"
                    val aiMsg = ChatMessage(text = "⚠️ Switch failed: $error", isUser = false)
                    _state.value = _state.value.copy(
                        messages = _state.value.messages + aiMsg,
                        isSending = false,
                    )
                }
            } catch (e: Exception) {
                val aiMsg = ChatMessage(text = "⚠️ Switch failed: ${e.message}", isUser = false)
                _state.value = _state.value.copy(
                    messages = _state.value.messages + aiMsg,
                    isSending = false,
                )
            }
        }
    }

    /**
     * Drain any queued phone-tool results and prepend them as
     * `[TOOL_RESULT:{json}]` markers on the outgoing user message.
     *
     * If tool handlers are still in-flight (async on Dispatchers.Default),
     * waits up to 5 seconds for them to complete before draining. This
     * prevents the race condition where a handler hasn't finished by the
     * time the user sends their next message, causing silent result loss.
     *
     * The server's _extract_tool_results helper in jane_proxy.py strips these
     * from the user-visible bubble before persistence but passes the parsed
     * results into Jane's mind's context for the next turn, so she stays in
     * sync with what actually happened on the phone.
     */
    private suspend fun prependPendingToolResults(text: String): String {
        val results = com.vessences.android.tools.PendingToolResultBuffer.awaitAndDrainAll()
        if (results.isEmpty()) return text
        val gson = com.google.gson.Gson()
        val sb = StringBuilder()
        for (r in results) {
            val obj = com.google.gson.JsonObject()
            obj.addProperty("tool", r.tool)
            obj.addProperty("call_id", r.callId)
            obj.addProperty("status", r.status)
            obj.addProperty("message", r.message)
            if (r.data != null) obj.add("data", r.data)
            if (r.extra.isNotEmpty()) {
                val ex = com.google.gson.JsonObject()
                for ((k, v) in r.extra) ex.addProperty(k, v)
                obj.add("extra", ex)
            }
            // Server regex requires the marker payload to be compact JSON on
            // one line and match `\[TOOL_RESULT:(\{.*?\})\]\s*` at the head.
            val json = gson.toJson(obj).replace("\n", " ").replace("\r", "")
            sb.append("[TOOL_RESULT:").append(json).append("] ")
        }
        sb.append(text)
        return sb.toString()
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
        toolDispatcher.shutdown()  // cancel any in-flight phone-tool handlers
        announcementPoller.stop()
        if (backend == ChatBackend.JANE) {
            viewModelScope.launch { repo.endJaneSession(sessionId) }
        }
    }
}
