package com.vessences.android.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import com.vessences.android.data.api.ApiClient
import com.vessences.android.data.model.ChatMessage
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.material3.Surface
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Pause
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.media.MediaPlayer
import android.net.Uri
import android.widget.Toast
import okhttp3.HttpUrl.Companion.toHttpUrl

private val UserBubbleColor = Color(0xFF6D28D9)
private val AiBubbleColor = Color(0xFF1E293B)
private val StatusColor = Color(0xFF94A3B8)
private val ActionChipColor = Color(0xFF7C3AED)

private val ACTION_PATTERN = Regex("""\{\{(navigate|open_file|image|play):(.+?)\}\}""")

@Composable
fun MessageBubble(
    message: ChatMessage,
    aiName: String = "Amber",
    aiColor: Color = Color(0xFFF59E0B),
    onNavigateToEssence: ((String) -> Unit)? = null,
    onSpeakText: ((String) -> Unit)? = null,
    onSwitchProvider: ((String) -> Unit)? = null,
) {
    if (message.isUser) {
        UserBubble(message)
    } else {
        AiBubble(message, aiName, aiColor, onNavigateToEssence, onSpeakText, onSwitchProvider)
    }
}

@Composable
private fun UserBubble(message: ChatMessage) {
    val context = LocalContext.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.End,
    ) {
        Column(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .background(UserBubbleColor, RoundedCornerShape(16.dp, 16.dp, 4.dp, 16.dp))
                .padding(12.dp),
        ) {
            RichMessageContent(text = message.text, color = Color.White)
            if (message.text.isNotEmpty()) {
                Text(
                    text = "Copy",
                    color = Color.White.copy(alpha = 0.5f),
                    fontSize = 10.sp,
                    modifier = Modifier
                        .align(Alignment.End)
                        .padding(top = 6.dp)
                        .clickable {
                            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                            clipboard.setPrimaryClip(ClipData.newPlainText("Message", message.text))
                            Toast.makeText(context, "Copied", Toast.LENGTH_SHORT).show()
                        },
                )
            }
        }
    }
}

@Composable
private fun AiBubble(message: ChatMessage, aiName: String, aiColor: Color, onNavigateToEssence: ((String) -> Unit)? = null, onSpeakText: ((String) -> Unit)? = null, onSwitchProvider: ((String) -> Unit)? = null) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.Start,
        verticalAlignment = Alignment.Top,
    ) {
        // Avatar — load from server for Jane, fallback to letter circle
        if (aiName == "Jane") {
            val avatarUrl = "${ApiClient.getJaneBaseUrl()}/api/files/serve/images/people/jane/jane1.png"
            val context = LocalContext.current
            val imageLoader = remember { ApiClient.getAuthenticatedImageLoader(context) }
            SubcomposeAsyncImage(
                model = ImageRequest.Builder(context)
                    .data(avatarUrl)
                    .crossfade(true)
                    .build(),
                imageLoader = imageLoader,
                contentDescription = "Jane",
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape),
                contentScale = ContentScale.Crop,
                loading = {
                    AvatarFallback(aiName, aiColor)
                },
                error = {
                    AvatarFallback(aiName, aiColor)
                },
            )
        } else {
            AvatarFallback(aiName, aiColor)
        }
        Spacer(modifier = Modifier.width(8.dp))

        Column(modifier = Modifier.widthIn(max = 300.dp)) {
            // Status log: expanded while streaming, collapsible once response arrives
            if (message.statusLog.isNotEmpty()) {
                if (message.text.isEmpty()) {
                    // Streaming: show all steps live
                    Column(modifier = Modifier.padding(bottom = 4.dp, start = 4.dp)) {
                        for (entry in message.statusLog) {
                            Text(text = entry, color = StatusColor, fontSize = 11.sp)
                        }
                        if (message.statusText != null) {
                            Text(text = message.statusText, color = StatusColor.copy(alpha = 0.7f), fontSize = 11.sp)
                        }
                    }
                } else {
                    // Completed: collapsible summary
                    var expanded by remember { mutableStateOf(false) }
                    val stepCount = message.statusLog.size
                    val label = "Jane worked through $stepCount step${if (stepCount == 1) "" else "s"}"
                    Text(
                        text = "${if (expanded) "▾" else "▸"} $label",
                        color = StatusColor,
                        fontSize = 11.sp,
                        modifier = Modifier
                            .padding(bottom = 4.dp)
                            .clickable { expanded = !expanded },
                    )
                    AnimatedVisibility(
                        visible = expanded,
                        enter = expandVertically(),
                        exit = shrinkVertically(),
                    ) {
                        Column(modifier = Modifier.padding(bottom = 4.dp, start = 8.dp)) {
                            for (entry in message.statusLog) {
                                Text(text = entry, color = StatusColor, fontSize = 11.sp)
                            }
                        }
                    }
                }
            } else if (message.statusText != null) {
                // Fallback: single status text (no log entries yet)
                Text(
                    text = message.statusText,
                    color = StatusColor,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(bottom = 4.dp),
                )
            }
            Column(
                modifier = Modifier
                    .background(AiBubbleColor, RoundedCornerShape(16.dp, 16.dp, 16.dp, 4.dp))
                    .padding(12.dp),
            ) {
                if (message.isStreaming && message.text.isEmpty()) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = aiColor,
                    )
                } else {
                    // Strip action tags from displayed text
                    val cleanText = ACTION_PATTERN.replace(message.text, "").trim()
                    Row(verticalAlignment = Alignment.Bottom) {
                        Box(modifier = Modifier.weight(1f, fill = false)) {
                            RichMessageContent(text = cleanText, color = Color(0xFFE2E8F0))
                        }
                        // Copy button inline after last word
                        if (message.text.isNotEmpty() && !message.isStreaming) {
                            val context = LocalContext.current
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = "Copy",
                                color = StatusColor.copy(alpha = 0.6f),
                                fontSize = 10.sp,
                                modifier = Modifier
                                    .clickable {
                                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                        clipboard.setPrimaryClip(ClipData.newPlainText("Jane", message.text))
                                        Toast.makeText(context, "Copied", Toast.LENGTH_SHORT).show()
                                    },
                            )
                            // TTS buttons: short summary + full response (when <spoken> tag was present)
                            if (onSpeakText != null && message.spokenText != null) {
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "\uD83D\uDD0A Short",
                                    color = StatusColor.copy(alpha = 0.6f),
                                    fontSize = 10.sp,
                                    modifier = Modifier.clickable { onSpeakText(message.spokenText) },
                                )
                                if (message.fullText != null) {
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = "\uD83D\uDD0A Full",
                                        color = StatusColor.copy(alpha = 0.6f),
                                        fontSize = 10.sp,
                                        modifier = Modifier.clickable { onSpeakText(message.fullText) },
                                    )
                                }
                            }
                        }
                    }
                }
            }
            // Render action chips, inline images, and audio players
            val actions = ACTION_PATTERN.findAll(message.text).toList()
            if (actions.isNotEmpty() && !message.isStreaming) {
                // Inline images
                for (match in actions) {
                    if (match.groupValues[1] == "image") {
                        val target = match.groupValues[2].trim()
                        val imageUrl = "${ApiClient.getJaneBaseUrl()}/api/files/serve/$target"
                        val context = LocalContext.current
                        val imageLoader = remember { ApiClient.getAuthenticatedImageLoader(context) }
                        var showFullscreen by remember { mutableStateOf(false) }
                        SubcomposeAsyncImage(
                            model = ImageRequest.Builder(context)
                                .data(imageUrl)
                                .crossfade(true)
                                .build(),
                            imageLoader = imageLoader,
                            contentDescription = target.substringAfterLast('/'),
                            modifier = Modifier
                                .padding(top = 6.dp)
                                .widthIn(max = 280.dp)
                                .clip(RoundedCornerShape(12.dp))
                                .clickable { showFullscreen = true },
                            contentScale = ContentScale.FillWidth,
                            loading = {
                                Text("Loading image...", color = StatusColor, fontSize = 11.sp)
                            },
                            error = {
                                Text("[Image not found]", color = StatusColor, fontSize = 11.sp)
                            },
                        )
                        // Fullscreen image overlay
                        if (showFullscreen) {
                            androidx.compose.ui.window.Dialog(
                                onDismissRequest = { showFullscreen = false },
                            ) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .background(Color.Black.copy(alpha = 0.9f))
                                        .clickable { showFullscreen = false },
                                    contentAlignment = Alignment.Center,
                                ) {
                                    SubcomposeAsyncImage(
                                        model = ImageRequest.Builder(context)
                                            .data(imageUrl)
                                            .crossfade(true)
                                            .build(),
                                        imageLoader = imageLoader,
                                        contentDescription = target.substringAfterLast('/'),
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(16.dp),
                                        contentScale = ContentScale.Fit,
                                    )
                                }
                            }
                        }
                    }
                }
                // Audio players removed — music plays via Music Playlist view, not inline.
                // {{play:...}} tags are ignored and stripped from display text.
                // Navigation / open_file chips
                val navActions = actions.filter { it.groupValues[1] in listOf("navigate", "open_file") }
                if (navActions.isNotEmpty()) {
                    Row(
                        modifier = Modifier.padding(top = 6.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        for (match in navActions) {
                            val actionType = match.groupValues[1]
                            val target = match.groupValues[2].trim()
                            val label = when (actionType) {
                                "navigate" -> "Open $target"
                                "open_file" -> "View file"
                                else -> target
                            }
                            Surface(
                                onClick = {
                                    when (actionType) {
                                        "navigate" -> onNavigateToEssence?.invoke(target)
                                        "open_file" -> onNavigateToEssence?.invoke("Life Librarian")
                                    }
                                },
                                shape = RoundedCornerShape(12.dp),
                                color = ActionChipColor.copy(alpha = 0.2f),
                            ) {
                                Text(
                                    text = label,
                                    color = ActionChipColor,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Medium,
                                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                )
                            }
                        }
                    }
                }
            }
            // Provider switch buttons (shown on provider_error)
            if (message.switchAlternatives.isNotEmpty() && onSwitchProvider != null) {
                Row(
                    modifier = Modifier.padding(top = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    for (alt in message.switchAlternatives) {
                        val btnColor = when (alt) {
                            "claude" -> Color(0xFF7C3AED)
                            "gemini" -> Color(0xFF2563EB)
                            "openai" -> Color(0xFF059669)
                            else -> ActionChipColor
                        }
                        Surface(
                            onClick = { onSwitchProvider(alt) },
                            shape = RoundedCornerShape(12.dp),
                            color = btnColor,
                        ) {
                            Text(
                                text = "Switch to ${alt.replaceFirstChar { it.uppercase() }}",
                                color = Color.White,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Medium,
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AudioPlayCard(
    fileName: String,
    audioUrl: String,
) {
    val context = LocalContext.current
    var isPlaying by remember { mutableStateOf(false) }
    var isPrepared by remember { mutableStateOf(false) }
    val mediaPlayer = remember { MediaPlayer() }

    DisposableEffect(audioUrl) {
        onDispose {
            try {
                if (mediaPlayer.isPlaying) mediaPlayer.stop()
                mediaPlayer.reset()
                mediaPlayer.release()
            } catch (_: Exception) {}
        }
    }

    Surface(
        modifier = Modifier
            .padding(top = 6.dp)
            .fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF1E293B),
        border = BorderStroke(1.dp, Color(0xFF334155)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(
                onClick = {
                    try {
                        if (isPlaying) {
                            mediaPlayer.pause()
                            isPlaying = false
                        } else if (isPrepared) {
                            mediaPlayer.start()
                            isPlaying = true
                        } else {
                            mediaPlayer.reset()
                            // Build cookie header from the cookie store
                            val cookieStore = ApiClient.getCookieStore()
                            val httpUrl = try { audioUrl.toHttpUrl() } catch (_: Exception) { null }
                            val cookies = if (httpUrl != null) cookieStore.loadForRequest(httpUrl) else emptyList()
                            val cookieHeader = cookies.joinToString("; ") { "${it.name}=${it.value}" }
                            val headers = mutableMapOf<String, String>()
                            if (cookieHeader.isNotEmpty()) {
                                headers["Cookie"] = cookieHeader
                            }
                            mediaPlayer.setDataSource(context, Uri.parse(audioUrl), headers)
                            mediaPlayer.setOnPreparedListener { mp ->
                                isPrepared = true
                                mp.start()
                                isPlaying = true
                            }
                            mediaPlayer.setOnCompletionListener {
                                isPlaying = false
                            }
                            mediaPlayer.prepareAsync()
                        }
                    } catch (_: Exception) {
                        isPlaying = false
                    }
                },
                modifier = Modifier.size(32.dp),
            ) {
                Icon(
                    imageVector = if (isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                    contentDescription = if (isPlaying) "Pause" else "Play",
                    tint = Color(0xFF8B5CF6),
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = fileName,
                color = Color(0xFFCBD5E1),
                fontSize = 13.sp,
                maxLines = 1,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun AvatarFallback(aiName: String, aiColor: Color) {
    Box(
        modifier = Modifier
            .size(32.dp)
            .clip(CircleShape)
            .background(aiColor),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = aiName.first().toString(),
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 14.sp,
        )
    }
}
