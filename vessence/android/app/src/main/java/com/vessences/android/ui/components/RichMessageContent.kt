package com.vessences.android.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.vessences.android.data.api.ApiClient

/**
 * Renders a chat message with inline images. Splits the text on markdown image
 * syntax ![alt](url) and renders text parts with MarkdownText and image parts
 * as clickable thumbnails.
 */
@Composable
fun RichMessageContent(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.White,
    fontSize: Float = 14f,
) {
    val parts = splitMessageParts(text)
    val context = LocalContext.current
    val imageLoader = remember { ApiClient.getAuthenticatedImageLoader(context) }
    var fullScreenImageUrl by remember { mutableStateOf<String?>(null) }

    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        for (part in parts) {
            when (part) {
                is MessagePart.Text -> {
                    if (part.content.isNotBlank()) {
                        MarkdownText(text = part.content.trim(), color = color, fontSize = fontSize)
                    }
                }
                is MessagePart.Image -> {
                    val fullUrl = resolveImageUrl(part.url)
                    AsyncImage(
                        model = ImageRequest.Builder(context)
                            .data(fullUrl)
                            .crossfade(true)
                            .build(),
                        imageLoader = imageLoader,
                        contentDescription = part.alt,
                        modifier = Modifier
                            .widthIn(max = 200.dp)
                            .heightIn(max = 200.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .clickable { fullScreenImageUrl = fullUrl },
                        contentScale = ContentScale.Fit,
                    )
                }
            }
        }
    }

    // Full-screen image viewer dialog
    if (fullScreenImageUrl != null) {
        Dialog(
            onDismissRequest = { fullScreenImageUrl = null },
            properties = DialogProperties(usePlatformDefaultWidth = false),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.9f))
                    .clickable { fullScreenImageUrl = null },
                contentAlignment = Alignment.Center,
            ) {
                AsyncImage(
                    model = ImageRequest.Builder(context)
                        .data(fullScreenImageUrl)
                        .crossfade(true)
                        .build(),
                    imageLoader = imageLoader,
                    contentDescription = "Full-size image",
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    contentScale = ContentScale.Fit,
                )
                IconButton(
                    onClick = { fullScreenImageUrl = null },
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(16.dp),
                ) {
                    Icon(
                        Icons.Default.Close,
                        contentDescription = "Close",
                        tint = Color.White,
                    )
                }
            }
        }
    }
}

private sealed class MessagePart {
    data class Text(val content: String) : MessagePart()
    data class Image(val alt: String, val url: String) : MessagePart()
}

private val IMAGE_PATTERN = Regex("""!\[([^\]]*)\]\(([^)]+)\)""")
private val LINK_IMAGE_PATTERN = Regex("""\[([^\]]*)\]\((\/api\/files\/serve\/[^)]*\.(?:png|jpe?g|gif|webp|bmp|heic|svg))\)""", RegexOption.IGNORE_CASE)

private fun splitMessageParts(text: String): List<MessagePart> {
    val parts = mutableListOf<MessagePart>()
    val remaining = text

    // Find all image patterns
    val allMatches = (IMAGE_PATTERN.findAll(remaining) + LINK_IMAGE_PATTERN.findAll(remaining))
        .sortedBy { it.range.first }
        .toList()

    if (allMatches.isEmpty()) {
        parts.add(MessagePart.Text(remaining))
        return parts
    }

    var lastEnd = 0
    for (match in allMatches) {
        if (match.range.first < lastEnd) continue // skip overlapping
        if (match.range.first > lastEnd) {
            parts.add(MessagePart.Text(remaining.substring(lastEnd, match.range.first)))
        }
        val alt = match.groupValues[1]
        val url = match.groupValues[2]
        parts.add(MessagePart.Image(alt, url))
        lastEnd = match.range.last + 1
    }
    if (lastEnd < remaining.length) {
        parts.add(MessagePart.Text(remaining.substring(lastEnd)))
    }
    return parts
}

private fun resolveImageUrl(url: String): String {
    if (url.startsWith("http://") || url.startsWith("https://")) return url
    val base = ApiClient.getJaneBaseUrl().trimEnd('/')
    val path = if (url.startsWith("/")) url else "/api/files/serve/$url"
    return "$base$path"
}
