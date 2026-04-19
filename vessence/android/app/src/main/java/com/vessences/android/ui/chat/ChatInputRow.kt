package com.vessences.android.ui.chat

import android.Manifest
import android.app.Activity
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
import androidx.compose.animation.core.tween
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import java.util.Locale

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val Violet500 = Color(0xFFA855F7)
private val SlateMuted = Color(0xFF94A3B8)

private val END_PHRASES = listOf(
    // Direct end statements
    "we're done", "we are done", "were done",  // STT may drop apostrophe
    "ok we're done", "ok we are done", "okay we're done", "okay we are done",
    "ok were done", "okay were done",  // apostrophe-free variants
    "i'm done", "i am done", "im done",  // apostrophe-free
    "done now", "i'm done now", "i am done now", "im done now",
    "ok done", "okay done", "alright done", "all done",
    "that's all", "that is all", "ok that's all", "alright that's all",
    "that's it", "that is it", "ok that's it",
    "that'll be all", "that will be all",
    "nothing else", "no more questions", "no more",
    "end conversation", "conversation over", "this conversation ends",
    "end chat", "close conversation",

    // Goodbyes
    "goodbye", "good bye", "bye", "bye bye", "bye jane", "bye now",
    "see you", "see ya", "see you later", "see ya later",
    "later", "talk to you later", "talk later", "catch you later",
    "good night", "goodnight", "night jane", "night night",
    "take care", "have a good one",
    "peace", "peace out", "adios", "ciao",

    // Stop / cancel
    "stop", "stop listening", "stop talking", "shut up",
    "be quiet", "quiet", "enough", "that's enough",
    "cancel", "dismiss", "go away", "leave me alone",
    "never mind", "nevermind", "forget it", "forget about it",
    "no thanks", "nah", "nope",

    // Thank you + end
    "thank you", "thanks", "thank you jane", "thanks jane",
    "thanks that's it", "thanks that's all", "thank you that's all",
    "thanks i'm good", "thanks i am good",
    "thanks for your help", "thank you for your help",
    "thanks for the help", "appreciate it",
    "thanks bye", "thank you bye", "thanks goodbye",

    // Informal / casual
    "ok cool", "alright cool", "sounds good we're done",
    "got it thanks", "got it bye", "perfect thanks",
    "ok great", "alright great", "awesome thanks",
    "k bye", "k thanks", "ok thanks bye",
    "roger", "roger that done", "over and out",
    "i'm good", "i am good", "all good", "we're good", "we are good",
    "no worries", "all set", "i'm all set", "i am all set",
)

private fun isConversationEndPhrase(text: String): Boolean {
    // Normalize: lowercase, strip punctuation, smart quotes → straight, collapse spaces
    val normalized = text.lowercase(java.util.Locale.US).trim()
        .replace('\u2019', '\'')  // smart apostrophe → straight
        .replace('\u2018', '\'')  // left smart quote → straight
        .replace(".", "").replace(",", "").replace("!", "").replace("?", "")
        .replace("  ", " ").trim()
    val matched = END_PHRASES.any { phrase ->
        if (phrase in setOf("ok", "okay", "stop", "quiet", "enough", "cancel", "dismiss", "nah", "nope")) {
            normalized == phrase
        } else if (phrase.length <= 5) {
            normalized == phrase || normalized.startsWith("$phrase ")
        } else {
            normalized.contains(phrase)
        }
    }
    if (!matched) {
        android.util.Log.d("EndPhrase", "NOT matched: '$normalized' (raw: '$text')")
    }
    return matched
}

@Composable
fun ChatInputRow(
    inputText: MutableState<String>,
    onSend: (String, Uri?) -> Unit,
    onSendVoice: (String) -> Unit,
    fileAttachment: MutableState<Uri?>,
    fileAttachmentName: MutableState<String?>,
    isSending: Boolean,
    isUploading: Boolean,
    uploadProgress: String?,
    aiName: String,
    aiColor: Color,
    onShowAttachmentSheet: () -> Unit,
    onCancel: (() -> Unit)? = null,
    queuedCount: Int = 0,
    triggerSpeech: Boolean = false,
    onSpeechTriggered: () -> Unit = {},
) {
    val context = LocalContext.current
    var isListeningForSpeech by remember { mutableStateOf(false) }

    // Speech recognition launcher
    val speechLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        isListeningForSpeech = false
        if (result.resultCode == Activity.RESULT_OK) {
            val matches = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            val spoken = matches?.firstOrNull()
            if (!spoken.isNullOrBlank()) {
                // Check for end-of-conversation phrases — silently end without sending to Jane
                if (EndPhraseDetector.isEndPhrase(spoken)) {
                    // Don't send to Jane, don't TTS — just end and restart wake word
                    android.util.Log.i("ChatInputRow", "End phrase detected: '$spoken' — restarting always-listen")
                    com.vessences.android.DiagnosticReporter.report("service", "end_phrase_restart", mapOf("phrase" to spoken))
                    try {
                        com.vessences.android.voice.AlwaysListeningService.start(context.applicationContext)
                    } catch (e: Exception) {
                        android.util.Log.e("ChatInputRow", "Failed to restart service: ${e.message}")
                        com.vessences.android.DiagnosticReporter.nonFatalError("ChatInputRow", "service_restart_failed", e)
                    }
                } else {
                    // Voice-initiated — use onSendVoice so Jane speaks back
                    onSendVoice(spoken)
                    fileAttachment.value = null
                }
            } else {
                // Empty result — conversation over, restart service
                com.vessences.android.voice.AlwaysListeningService.start(context)
            }
        } else {
            // STT cancelled or failed — restart service
            com.vessences.android.voice.AlwaysListeningService.start(context)
        }
    }

    // Mic permission launcher for speech-to-text
    val speechMicPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            isListeningForSpeech = true
            val speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak your message...")
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
            }
            speechLauncher.launch(speechIntent)
        }
    }

    fun launchSpeechToText() {
        // Stop wake word service to release mic before STT
        com.vessences.android.voice.AlwaysListeningService.stop(context)
        val hasPerm = ContextCompat.checkSelfPermission(
            context, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        android.util.Log.i("ChatInputRow", "launchSpeechToText: hasPerm=$hasPerm")
        if (hasPerm) {
            isListeningForSpeech = true
            val speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak your message...")
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
            }
            try {
                speechLauncher.launch(speechIntent)
                android.util.Log.i("ChatInputRow", "speechLauncher.launch() succeeded")
            } catch (e: Exception) {
                android.util.Log.e("ChatInputRow", "speechLauncher.launch() FAILED", e)
                android.widget.Toast.makeText(context, "STT failed: ${e.message}", android.widget.Toast.LENGTH_LONG).show()
                isListeningForSpeech = false
            }
        } else {
            android.util.Log.i("ChatInputRow", "Requesting RECORD_AUDIO permission")
            speechMicPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    // Auto-launch STT when triggered by wake word
    // Delay briefly to ensure the Activity is fully resumed before launching STT intent
    LaunchedEffect(triggerSpeech) {
        if (triggerSpeech) {
            kotlinx.coroutines.delay(600)
            onSpeechTriggered()
            launchSpeechToText()
        }
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
    ) {
        // Upload progress indicator
        if (isUploading) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(SlateCard)
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                LinearProgressIndicator(
                    modifier = Modifier
                        .weight(1f)
                        .height(4.dp),
                    color = aiColor,
                    trackColor = Color(0xFF334155),
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = uploadProgress ?: "Uploading...",
                    color = SlateMuted,
                    fontSize = 12.sp,
                )
            }
        }

        // Error banner is handled in ChatScreen directly

        // Attached file indicator
        if (fileAttachment.value != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(SlateCard)
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
                    text = fileAttachmentName.value ?: "file",
                    color = Violet500,
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                IconButton(
                    onClick = {
                        fileAttachment.value = null
                        fileAttachmentName.value = null
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
                .background(SlateCard)
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            // Attachment button
            IconButton(
                onClick = onShowAttachmentSheet,
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
                value = inputText.value,
                onValueChange = { inputText.value = it },
                modifier = Modifier.weight(1f),
                placeholder = {
                    Text("Message $aiName...", color = Color(0xFF64748B))
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

            // Speech-to-text mic button
            IconButton(
                onClick = { launchSpeechToText() },
                modifier = Modifier.size(40.dp),
            ) {
                if (isListeningForSpeech) {
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
                        imageVector = Icons.Default.Mic,
                        contentDescription = "Listening...",
                        tint = Color(0xFFEF4444),
                        modifier = Modifier.scale(scale),
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.Mic,
                        contentDescription = "Voice input",
                        tint = Violet500,
                    )
                }
            }

            Spacer(modifier = Modifier.width(4.dp))

            if (isSending && onCancel != null) {
                IconButton(
                    onClick = onCancel,
                    modifier = Modifier.size(40.dp),
                ) {
                    Icon(
                        Icons.Default.Stop,
                        contentDescription = "Stop",
                        tint = Color(0xFFEF4444),
                    )
                }
            } else {
                IconButton(
                    onClick = {
                        val hasText = inputText.value.isNotBlank()
                        val hasFile = fileAttachment.value != null
                        if (hasText || hasFile) {
                            val currentFileUri = fileAttachment.value
                            val messageText = if (hasText) inputText.value.trim() else (fileAttachmentName.value ?: "file")
                            onSend(messageText, currentFileUri)
                            inputText.value = ""
                            fileAttachment.value = null
                            fileAttachmentName.value = null
                        }
                    },
                    enabled = inputText.value.isNotBlank() || fileAttachment.value != null,
                    modifier = Modifier.size(40.dp),
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.Send,
                        contentDescription = "Send",
                        tint = if (inputText.value.isNotBlank() || fileAttachment.value != null) Violet500 else Color(0xFF475569),
                    )
                }
            }
        }

        // Queued messages indicator
        if (queuedCount > 0) {
            Text(
                text = "$queuedCount message${if (queuedCount > 1) "s" else ""} queued",
                color = SlateMuted,
                fontSize = 11.sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(SlateCard)
                    .padding(horizontal = 16.dp, vertical = 2.dp),
            )
        }
    }
}
