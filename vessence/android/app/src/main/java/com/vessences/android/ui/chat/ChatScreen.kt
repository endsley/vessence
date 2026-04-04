package com.vessences.android.ui.chat

import android.Manifest
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.runtime.Composable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val SlateMuted = Color(0xFF94A3B8)
private val MicHot = Color(0xFF38BDF8)

@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    aiName: String,
    aiColor: Color,
    subtitle: String,
    onNavigateToEssence: ((String) -> Unit)? = null,
    wakeWordsLabel: String,
    onBack: (() -> Unit)? = null,
) {
    val state by viewModel.state.collectAsState()
    val alwaysListeningRunning by com.vessences.android.voice.AlwaysListeningService.running.collectAsState()
    val inputText = remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val userDetachedFromBottom by remember {
        derivedStateOf {
            val layout = listState.layoutInfo
            val totalItems = layout.totalItemsCount
            if (totalItems == 0) {
                false
            } else {
                // Detached only if the sentinel (last item) is entirely off-screen,
                // meaning the user intentionally scrolled up past Jane's message.
                layout.visibleItemsInfo.none { it.index == totalItems - 1 }
            }
        }
    }

    // Attachment state
    val attachedFileUri = remember { mutableStateOf<Uri?>(null) }
    val attachedFileName = remember { mutableStateOf<String?>(null) }
    var showAttachmentSheet by remember { mutableStateOf(false) }
    var showQueueSheet by remember { mutableStateOf(false) }
    var showVoicePicker by remember { mutableStateOf(false) }
    var showNewSessionConfirm by remember { mutableStateOf(false) }
    val cameraPhotoUri = remember { mutableStateOf<Uri?>(null) }
    val ttsEnabled = remember { mutableStateOf(false) }
    
    val chatPrefs = remember { com.vessences.android.util.ChatPreferences(context) }
    val autoListenEnabled = remember { mutableStateOf(chatPrefs.isAutoListenEnabled()) }
    LaunchedEffect(autoListenEnabled.value) {
        chatPrefs.setAutoListenEnabled(autoListenEnabled.value)
    }

    // Always-listening permission state
    var pendingAlwaysListeningEnable by remember { mutableStateOf(false) }
    val recordAudioLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted && pendingAlwaysListeningEnable) {
            viewModel.setAlwaysListeningEnabled(true)
        }
        pendingAlwaysListeningEnable = false
    }

    fun hasMicPermission(): Boolean =
        ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO,
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED

    LaunchedEffect(Unit) {
        viewModel.syncVoicePreferences()
    }

    // Auto-scroll when user sends a message — always scroll to show their bubble
    val userMessageCount = state.messages.count { it.isUser }
    LaunchedEffect(userMessageCount) {
        if (state.messages.isNotEmpty()) {
            // Small delay to let Compose lay out the new item first
            kotlinx.coroutines.delay(100)
            listState.animateScrollToItem(state.messages.size) // scroll to sentinel
        }
    }

    // Auto-scroll during Jane's streaming only while the user is still following the bottom,
    // matching web Jane's behavior of pausing once they've scrolled up to read older content.
    // Uses scrollToItem (instant) instead of animateScrollToItem to avoid animation queue buildup
    // when deltas arrive rapidly during streaming.
    val totalMessages = state.messages.size
    val lastMessageText = state.messages.lastOrNull()?.text ?: ""
    LaunchedEffect(totalMessages, lastMessageText.length) {
        if (state.messages.isNotEmpty() && !state.messages.last().isUser) {
            if (!userDetachedFromBottom) {
                listState.scrollToItem(state.messages.size) // scroll to sentinel
            }
        }
    }

    // Attachment bottom sheet
    AttachmentSheet(
        showSheet = showAttachmentSheet,
        onDismiss = { showAttachmentSheet = false },
        aiColor = aiColor,
        ttsEnabled = ttsEnabled,
        autoListenEnabled = autoListenEnabled,
        attachedFileUri = attachedFileUri,
        attachedFileName = attachedFileName,
        cameraPhotoUri = cameraPhotoUri,
        isSending = state.isSending,
        onCancel = { viewModel.cancelCurrentResponse() },
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg)
            .navigationBarsPadding()
            .imePadding(),
    ) {
        // Header
        ChatHeader(
            aiName = aiName,
            aiColor = aiColor,
            subtitle = subtitle,
            onBack = onBack,
            onNewChat = { showNewSessionConfirm = true },
            isWakeListening = alwaysListeningRunning || state.voice.isWakeListening,
            ttsEnabled = state.ttsEnabled,
            isSpeaking = state.isSpeaking,
            onToggleTts = { viewModel.toggleTts() },
            onStopSpeaking = { viewModel.stopSpeaking() },
            onVoiceSettings = { showVoicePicker = true },
        )

        // Prompt Queue bottom sheet (Jane only)
        PromptQueueSheet(
            visible = showQueueSheet,
            onDismiss = { showQueueSheet = false },
        )

        // TTS Voice Picker sheet
        com.vessences.android.ui.settings.TtsVoicePickerSheet(
            visible = showVoicePicker,
            onDismiss = { showVoicePicker = false },
        )

        // Voice status banner removed — wake word status shown as icon in header

        // Messages
        Box(modifier = Modifier.weight(1f)) {
            ChatMessageList(
                messages = state.messages,
                aiName = aiName,
                aiColor = aiColor,
                listState = listState,
                modifier = Modifier.fillMaxSize(),
                onNavigateToEssence = onNavigateToEssence,
                onSpeakText = { text -> viewModel.speakText(text) },
                onSwitchProvider = { provider -> viewModel.switchProvider(provider) },
            )

            if (userDetachedFromBottom && state.messages.isNotEmpty()) {
                FloatingActionButton(
                    onClick = {
                        scope.launch {
                            listState.animateScrollToItem(state.messages.size) // scroll to sentinel
                        }
                    },
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(end = 16.dp, bottom = 16.dp),
                    containerColor = SlateCard,
                    contentColor = Color.White,
                ) {
                    Icon(
                        imageVector = Icons.Default.KeyboardArrowDown,
                        contentDescription = "Jump to latest message",
                    )
                }
            }
        }

        // Error banner
        ErrorBanner(
            error = state.error,
            onDismiss = { viewModel.clearError() },
        )

        // Stop speaking banner
        if (state.isSpeaking) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF1E293B))
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.Center,
            ) {
                Surface(
                    onClick = { viewModel.stopSpeaking() },
                    shape = RoundedCornerShape(20.dp),
                    color = Color(0xFFEF4444).copy(alpha = 0.15f),
                ) {
                    Text(
                        text = "Stop speaking",
                        color = Color(0xFFEF4444),
                        fontSize = 13.sp,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    )
                }
            }
        }

        // Input row (includes upload progress, attachment indicator, text field, mic, send)
        ChatInputRow(
            inputText = inputText,
            onSend = { text, uri -> viewModel.sendMessage(text = text, fileUri = uri) },
            onSendVoice = { text -> viewModel.sendMessage(text = text, fromVoice = true) },
            fileAttachment = attachedFileUri,
            fileAttachmentName = attachedFileName,
            isSending = state.isSending,
            isUploading = state.isUploading,
            uploadProgress = state.uploadProgress,
            aiName = aiName,
            aiColor = aiColor,
            onShowAttachmentSheet = { showAttachmentSheet = true },
            onCancel = { viewModel.cancelCurrentResponse() },
            queuedCount = state.queuedCount,
            triggerSpeech = state.wakeWordTriggered,
            onSpeechTriggered = { viewModel.clearWakeWordTrigger() },
        )
    }

    // New session confirmation dialog
    if (showNewSessionConfirm) {
        AlertDialog(
            onDismissRequest = { showNewSessionConfirm = false },
            title = { Text("Start new session?") },
            text = { Text("Some memories from this session might be lost. Are you sure?") },
            confirmButton = {
                TextButton(onClick = {
                    showNewSessionConfirm = false
                    viewModel.clearSession()
                }) {
                    Text("Yes, start new")
                }
            },
            dismissButton = {
                TextButton(onClick = { showNewSessionConfirm = false }) {
                    Text("Cancel")
                }
            },
        )
    }

    // Voice error dialog
    if (state.voice.error != null) {
        AlertDialog(
            onDismissRequest = { viewModel.clearVoiceError() },
            confirmButton = {
                TextButton(onClick = { viewModel.clearVoiceError() }) {
                    Text("OK")
                }
            },
            title = { Text("Voice unavailable") },
            text = { Text(state.voice.error ?: "") },
        )
    }
}

@Composable
private fun ChatHeader(
    aiName: String,
    aiColor: Color,
    subtitle: String,
    onBack: (() -> Unit)?,
    onNewChat: (() -> Unit)? = null,
    isWakeListening: Boolean = false,
    ttsEnabled: Boolean = false,
    isSpeaking: Boolean = false,
    onToggleTts: (() -> Unit)? = null,
    onStopSpeaking: (() -> Unit)? = null,
    onVoiceSettings: (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 4.dp, end = 16.dp, top = 4.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (onBack != null) {
            IconButton(onClick = onBack) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "Back to home",
                    tint = Color.White,
                )
            }
        }
        Row(
            modifier = Modifier.weight(1f),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = aiName,
                color = Color.White,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = if (ttsEnabled) "$subtitle · TTS on" else subtitle,
                color = if (ttsEnabled) Color(0xFF38BDF8) else SlateMuted,
                fontSize = 11.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        // TTS toggle — always visible
        if (onToggleTts != null) {
            IconButton(onClick = onToggleTts) {
                Icon(
                    imageVector = if (ttsEnabled) Icons.Default.VolumeUp else Icons.Default.VolumeOff,
                    contentDescription = if (ttsEnabled) "Disable read aloud" else "Enable read aloud",
                    tint = if (ttsEnabled) Color(0xFF38BDF8) else SlateMuted,
                )
            }
        }
        if (onVoiceSettings != null && ttsEnabled) {
            IconButton(onClick = onVoiceSettings) {
                Icon(
                    imageVector = Icons.Default.GraphicEq,
                    contentDescription = "Voice Settings",
                    tint = Color(0xFF38BDF8),
                    modifier = Modifier.size(20.dp),
                )
            }
        }
        Icon(
            imageVector = Icons.Default.GraphicEq,
            contentDescription = if (isWakeListening) "Wake word active" else "Wake word off",
            tint = if (isWakeListening) Color(0xFF22C55E) else Color(0xFF334155),
            modifier = Modifier.size(18.dp),
        )
        Spacer(modifier = Modifier.width(4.dp))
        if (onNewChat != null) {
            IconButton(onClick = onNewChat) {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = "New session",
                    tint = SlateMuted,
                    modifier = Modifier.size(22.dp),
                )
            }
        }
    }
}

@Composable
private fun LiveActivityBanner(
    status: String,
    platform: String,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF2E1065).copy(alpha = 0.5f))
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Pulsing dot
        Surface(
            modifier = Modifier.size(8.dp),
            shape = RoundedCornerShape(4.dp),
            color = Color(0xFFA78BFA),
        ) {}
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = status,
            color = Color(0xFFC4B5FD),
            fontSize = 12.sp,
            maxLines = 2,
            modifier = Modifier.weight(1f),
        )
        if (platform.isNotBlank()) {
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "($platform)",
                color = Color(0xFF7C3AED),
                fontSize = 11.sp,
            )
        }
    }
}

@Composable
private fun VoiceStatusBanner(
    voice: com.vessences.android.voice.VoiceState,
    aiColor: Color,
) {
    if (
        voice.isPreparingModel ||
        voice.isWakeListening ||
        voice.isCapturingCommand ||
        voice.transcriptPreview.isNotBlank() ||
        !voice.status.isNullOrBlank()
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            color = SlateCard,
            shape = RoundedCornerShape(16.dp),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    imageVector = if (voice.isCapturingCommand) Icons.Default.Mic else Icons.Default.GraphicEq,
                    contentDescription = null,
                    tint = if (voice.isCapturingCommand) MicHot else aiColor,
                )
                Spacer(modifier = Modifier.width(10.dp))
                Column {
                    Text(
                        text = voice.status ?: "Voice ready",
                        color = Color.White,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                    if (voice.transcriptPreview.isNotBlank()) {
                        Text(
                            text = voice.transcriptPreview,
                            color = SlateMuted,
                            fontSize = 12.sp,
                        )
                    }
                }
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
    }
}

@Composable
private fun ErrorBanner(
    error: String?,
    onDismiss: () -> Unit,
) {
    if (error != null) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF7F1D1D))
                .padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = error,
                color = Color(0xFFFCA5A5),
                fontSize = 12.sp,
                modifier = Modifier.weight(1f),
            )
            IconButton(
                onClick = onDismiss,
                modifier = Modifier.size(24.dp),
            ) {
                Icon(
                    Icons.Default.Close,
                    contentDescription = "Dismiss",
                    tint = Color(0xFFFCA5A5),
                    modifier = Modifier.size(16.dp),
                )
            }
        }
    }
}
