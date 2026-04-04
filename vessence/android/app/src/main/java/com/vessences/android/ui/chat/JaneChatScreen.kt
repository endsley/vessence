package com.vessences.android.ui.chat

import android.Manifest
import android.app.Activity
import androidx.activity.ComponentActivity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import com.vessences.android.data.api.ApiClient
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.vessences.android.SharedIntentState
import com.vessences.android.data.api.AppVersion
import com.vessences.android.data.api.UpdateManager
import com.vessences.android.data.repository.ChatBackend
import java.io.File
import java.util.Locale

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val Violet500 = Color(0xFFA855F7)
private val SlateMuted = Color(0xFF94A3B8)
private val SubtleText = Color(0xFF64748B)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JaneChatScreen(
    onNavigateToEssenceView: (String) -> Unit = {},
    onBack: () -> Unit = {},
) {
    // Scope to Activity so the ViewModel survives navigation between tabs
    val activity = LocalContext.current as? ComponentActivity
        ?: error("JaneChatScreen requires a ComponentActivity context")
    val chatViewModel: ChatViewModel = viewModel(
        viewModelStoreOwner = activity,
        key = "jane_chat",
        factory = ChatViewModelFactory(
            appContext = LocalContext.current.applicationContext,
            backend = ChatBackend.JANE,
        )
    )
    val chatState by chatViewModel.state.collectAsState()

    // Update state from ViewModel (survives recomposition)
    val context = LocalContext.current

    // Consume shared intent URIs/text
    val sharedUris by SharedIntentState.sharedUris.collectAsState()
    val sharedText by SharedIntentState.sharedText.collectAsState()

    if (chatState.messages.isEmpty()) {
        // Empty chat: show simple prompt with back button
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(SlateBg)
                .navigationBarsPadding()
                .imePadding(),
        ) {
            // Top bar with back arrow
            JaneTopBar(onBack = onBack)

            // Update banner
            if (chatState.availableUpdate != null && !chatState.updateDismissed) {
                UpdateBanner(
                    version = chatState.availableUpdate!!,
                    onInstall = { chatViewModel.installUpdate() },
                    onDismiss = { chatViewModel.dismissUpdate() },
                )
            }

            // Simple empty state — centered
            Box(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentAlignment = Alignment.Center,
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    val janeUrl = "${ApiClient.getJaneBaseUrl()}/api/files/serve/images/people/jane/jane1.png"
                    val imgContext = LocalContext.current
                    val imageLoader = remember { ApiClient.getAuthenticatedImageLoader(imgContext) }
                    SubcomposeAsyncImage(
                        model = ImageRequest.Builder(imgContext).data(janeUrl).crossfade(true).build(),
                        imageLoader = imageLoader,
                        contentDescription = "Jane",
                        modifier = Modifier.size(72.dp).clip(androidx.compose.foundation.shape.CircleShape),
                        contentScale = ContentScale.Crop,
                        loading = {
                            Icon(Icons.Default.Psychology, null, tint = Violet500.copy(alpha = 0.4f), modifier = Modifier.size(64.dp))
                        },
                        error = {
                            Icon(Icons.Default.Psychology, null, tint = Violet500.copy(alpha = 0.4f), modifier = Modifier.size(64.dp))
                        },
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "I'm Jane",
                        color = SlateMuted,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Medium,
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Your personal genie.\nAsk me anything directly here.",
                        color = SubtleText,
                        fontSize = 14.sp,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    )
                }
            }

            // Chat input at bottom
            ChatInputBar(
                chatViewModel = chatViewModel,
                chatState = chatState,
                sharedUris = sharedUris,
                sharedText = sharedText,
            )
        }
    } else {
        // Active chat
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(SlateBg),
        ) {
            // Update banner in active chat
            if (chatState.availableUpdate != null && !chatState.updateDismissed) {
                UpdateBanner(
                    version = chatState.availableUpdate!!,
                    onInstall = { chatViewModel.installUpdate() },
                    onDismiss = { chatViewModel.dismissUpdate() },
                )
            }
            ChatScreen(
                viewModel = chatViewModel,
                aiName = "Jane",
                aiColor = Violet500,
                subtitle = "Your personal genie",
                wakeWordsLabel = "\"hey jane\"",
                onBack = onBack,
                onNavigateToEssence = onNavigateToEssenceView,
            )
        }
    }
}

@Composable
private fun JaneTopBar(
    onBack: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "Back to home",
                tint = Color.White,
            )
        }
        val janeUrl = "${ApiClient.getJaneBaseUrl()}/api/files/serve/images/people/jane/jane1.png"
        val imgContext = LocalContext.current
        val imageLoader = remember { ApiClient.getAuthenticatedImageLoader(imgContext) }
        SubcomposeAsyncImage(
            model = ImageRequest.Builder(imgContext).data(janeUrl).crossfade(true).build(),
            imageLoader = imageLoader,
            contentDescription = "Jane",
            modifier = Modifier.size(28.dp).clip(androidx.compose.foundation.shape.CircleShape),
            contentScale = ContentScale.Crop,
            loading = { Icon(Icons.Default.Psychology, null, tint = Violet500, modifier = Modifier.size(28.dp)) },
            error = { Icon(Icons.Default.Psychology, null, tint = Violet500, modifier = Modifier.size(28.dp)) },
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = "Jane",
            color = Color.White,
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun UpdateBanner(
    version: AppVersion,
    onInstall: () -> Unit,
    onDismiss: () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = Color(0xFF1E3A5F),
        shape = RoundedCornerShape(0.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
        ) {
            Text(
                text = "Update available: v${version.versionName}",
                color = Color.White,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
            )
            if (version.changelog.isNotBlank()) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = version.changelog,
                    color = SlateMuted,
                    fontSize = 12.sp,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(modifier = Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                androidx.compose.material3.Button(
                    onClick = onInstall,
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                        containerColor = Violet500,
                    ),
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 6.dp),
                ) {
                    Text("Install", fontSize = 13.sp)
                }
                androidx.compose.material3.OutlinedButton(
                    onClick = onDismiss,
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 6.dp),
                ) {
                    Text("OK", fontSize = 13.sp, color = SlateMuted)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChatInputBar(
    chatViewModel: ChatViewModel,
    chatState: ChatUiState,
    sharedUris: List<Uri> = emptyList(),
    sharedText: String? = null,
) {
    var inputText by remember { mutableStateOf("") }
    var attachedFileUri by remember { mutableStateOf<Uri?>(null) }
    var attachedFileName by remember { mutableStateOf<String?>(null) }
    var showAttachmentSheet by remember { mutableStateOf(false) }
    var isListeningForSpeech by remember { mutableStateOf(false) }
    val context = LocalContext.current

    // Camera photo URI
    var cameraPhotoUri by remember { mutableStateOf<Uri?>(null) }
    var ttsEnabled by remember { mutableStateOf(false) }

    val chatPrefs = remember { com.vessences.android.util.ChatPreferences(context) }
    var autoListenEnabled by remember { mutableStateOf(chatPrefs.isAutoListenEnabled()) }
    LaunchedEffect(autoListenEnabled) {
        chatPrefs.setAutoListenEnabled(autoListenEnabled)
    }

    // Consume shared intent data
    LaunchedEffect(sharedUris, sharedText) {
        if (sharedUris.isNotEmpty()) {
            attachedFileUri = sharedUris.first()
            attachedFileName = sharedUris.first().lastPathSegment ?: "shared file"
            SharedIntentState.clear()
        }
        if (sharedText != null) {
            inputText = sharedText
            SharedIntentState.clear()
        }
    }

    // File picker launcher
    val filePickerLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            attachedFileUri = uri
            attachedFileName = uri.lastPathSegment ?: "file"
        }
    }

    // Camera launcher
    val cameraLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture()
    ) { success: Boolean ->
        if (success && cameraPhotoUri != null) {
            attachedFileUri = cameraPhotoUri
            attachedFileName = "photo.jpg"
        }
    }

    // Camera permission launcher
    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            val photoFile = File.createTempFile("photo_", ".jpg", context.cacheDir)
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", photoFile)
            cameraPhotoUri = uri
            cameraLauncher.launch(uri)
        }
    }

    // Speech recognition launcher
    // Track when STT was last launched to prevent premature always-listen restart
    var lastSttLaunchTime by remember { mutableStateOf(0L) }

    val speechLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        isListeningForSpeech = false
        val timeSinceLaunch = System.currentTimeMillis() - lastSttLaunchTime
        if (result.resultCode == Activity.RESULT_OK) {
            val matches = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            val spoken = matches?.firstOrNull()
            if (!spoken.isNullOrBlank()) {
                chatViewModel.sendMessage(spoken, fromVoice = true)
            } else {
                // Empty result (silence timeout) — conversation over
                com.vessences.android.voice.WakeWordBridge.sttActive = false
                com.vessences.android.voice.AlwaysListeningService.start(context)
            }
        } else if (timeSinceLaunch > 2000) {
            // STT cancelled after running for >2s — user dismissed it, conversation over
            com.vessences.android.voice.WakeWordBridge.sttActive = false
            com.vessences.android.voice.AlwaysListeningService.start(context)
        } else {
            // STT cancelled within 2s of launch — likely failed to start properly.
            // Don't restart always-listen yet, the wake word flow will retry.
            android.util.Log.w("JaneChatScreen", "STT cancelled too quickly (${timeSinceLaunch}ms) — not restarting always-listen")
        }
    }

    // Mic permission launcher (for speech-to-text)
    val micPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            isListeningForSpeech = true
            val speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak your message...")
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 6000L)
            }
            speechLauncher.launch(speechIntent)
        }
    }

    fun launchSpeechRecognition() {
        val hasMicPerm = ContextCompat.checkSelfPermission(
            context, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        if (hasMicPerm) {
            isListeningForSpeech = true
            lastSttLaunchTime = System.currentTimeMillis()
            // Mark STT as active so onResume doesn't restart always-listen
            com.vessences.android.voice.WakeWordBridge.sttActive = true
            // Stop wake word service to release mic before STT
            com.vessences.android.voice.AlwaysListeningService.stop(context)
            val speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak your message...")
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 6000L)
            }
            speechLauncher.launch(speechIntent)
        } else {
            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    // Single STT trigger — handles both wake word and auto-listen after TTS
    // ChatViewModel sets wakeWordTriggered=true from WakeWordPendingFlag OR from onSendComplete
    LaunchedEffect(chatState.wakeWordTriggered) {
        if (chatState.wakeWordTriggered) {
            chatViewModel.clearWakeWordTrigger()
            kotlinx.coroutines.delay(200)
            launchSpeechRecognition()
        }
    }

    // Attachment bottom sheet
    if (showAttachmentSheet) {
        ModalBottomSheet(
            onDismissRequest = { showAttachmentSheet = false },
            containerColor = SlateCard,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 32.dp),
            ) {
                Text(
                    text = "Attach",
                    color = Color.White,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                )
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            showAttachmentSheet = false
                            filePickerLauncher.launch("*/*")
                        },
                    color = Color.Transparent,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Default.Description, contentDescription = null, tint = Violet500)
                        Spacer(modifier = Modifier.width(12.dp))
                        Text("Choose file", color = Color.White, fontSize = 16.sp)
                    }
                }
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            showAttachmentSheet = false
                            val hasCamPerm = ContextCompat.checkSelfPermission(
                                context, Manifest.permission.CAMERA
                            ) == PackageManager.PERMISSION_GRANTED
                            if (hasCamPerm) {
                                val photoFile = File.createTempFile("photo_", ".jpg", context.cacheDir)
                                val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", photoFile)
                                cameraPhotoUri = uri
                                cameraLauncher.launch(uri)
                            } else {
                                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        },
                    color = Color.Transparent,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Default.CameraAlt, contentDescription = null, tint = Violet500)
                        Spacer(modifier = Modifier.width(12.dp))
                        Text("Take photo", color = Color.White, fontSize = 16.sp)
                    }
                }
                
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            autoListenEnabled = !autoListenEnabled
                            // Don't dismiss, let them see it change
                        },
                    color = Color.Transparent,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            if (autoListenEnabled) Icons.Default.Mic else Icons.Default.MicOff,
                            contentDescription = null,
                            tint = if (autoListenEnabled) Color(0xFF22C55E) else SlateMuted,
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = if (autoListenEnabled) "Auto-listen after speaking (on)" else "Auto-listen after speaking (off)",
                            color = Color.White,
                            fontSize = 16.sp,
                        )
                    }
                }
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(SlateCard),
    ) {
        // Upload progress indicator
        if (chatState.isUploading) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                LinearProgressIndicator(
                    modifier = Modifier
                        .weight(1f)
                        .height(4.dp),
                    color = Violet500,
                    trackColor = Color(0xFF334155),
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = chatState.uploadProgress ?: "Uploading...",
                    color = SlateMuted,
                    fontSize = 12.sp,
                )
            }
        }

        // Attached file indicator
        if (attachedFileUri != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Default.AttachFile,
                    contentDescription = null,
                    tint = Violet500,
                    modifier = Modifier.size(16.dp),
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = attachedFileName ?: "file",
                    color = Violet500,
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                IconButton(
                    onClick = {
                        attachedFileUri = null
                        attachedFileName = null
                    },
                    modifier = Modifier.size(24.dp),
                ) {
                    Icon(
                        Icons.Default.Close,
                        contentDescription = "Remove attachment",
                        tint = SlateMuted,
                        modifier = Modifier.size(16.dp),
                    )
                }
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            // Attachment button
            IconButton(
                onClick = { showAttachmentSheet = true },
                modifier = Modifier.size(40.dp),
            ) {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = "Attach file",
                    tint = SlateMuted,
                )
            }

            Spacer(modifier = Modifier.width(4.dp))

            OutlinedTextField(
                value = inputText,
                onValueChange = { inputText = it },
                modifier = Modifier.weight(1f),
                placeholder = {
                    Text("Message Jane...", color = SubtleText)
                },
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    focusedContainerColor = SlateBg,
                    unfocusedContainerColor = SlateBg,
                    focusedBorderColor = Violet500,
                    unfocusedBorderColor = Color(0xFF334155),
                    cursorColor = Violet500,
                ),
                shape = RoundedCornerShape(16.dp),
                maxLines = 4,
            )
            Spacer(modifier = Modifier.width(4.dp))

            // Mic button for speech-to-text / Stop button when listening
            if (chatState.voice.isCapturingCommand || isListeningForSpeech) {
                // Show stop button while actively listening
                IconButton(
                    onClick = {
                        chatViewModel.cancelListening()
                        isListeningForSpeech = false
                    },
                    modifier = Modifier.size(40.dp),
                ) {
                    val pulseTransition = rememberInfiniteTransition(label = "micPulse")
                    val scale by pulseTransition.animateFloat(
                        initialValue = 1f,
                        targetValue = 1.3f,
                        animationSpec = infiniteRepeatable(
                            animation = tween(500),
                            repeatMode = RepeatMode.Reverse,
                        ),
                        label = "micScale",
                    )
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Stop listening",
                        tint = Color(0xFFEF4444),
                        modifier = Modifier.scale(scale),
                    )
                }
            } else {
                IconButton(
                    onClick = { launchSpeechRecognition() },
                    modifier = Modifier.size(40.dp),
                ) {
                    Icon(
                        imageVector = Icons.Default.Mic,
                        contentDescription = "Voice input",
                        tint = Violet500,
                    )
                }
            }

            Spacer(modifier = Modifier.width(4.dp))
            IconButton(
                onClick = {
                    val hasText = inputText.isNotBlank()
                    val hasFile = attachedFileUri != null
                    if ((hasText || hasFile) && !chatState.isSending) {
                        val currentFileUri = attachedFileUri
                        val messageText = if (hasText) inputText.trim() else (attachedFileName ?: "file")
                        chatViewModel.sendMessage(
                            text = messageText,
                            fileUri = currentFileUri,
                        )
                        inputText = ""
                        attachedFileUri = null
                        attachedFileName = null
                    }
                },
                enabled = (inputText.isNotBlank() || attachedFileUri != null) && !chatState.isSending,
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.Send,
                    contentDescription = "Send",
                    tint = if ((inputText.isNotBlank() || attachedFileUri != null) && !chatState.isSending) Violet500 else Color(0xFF475569),
                )
            }
        }
    }
}
