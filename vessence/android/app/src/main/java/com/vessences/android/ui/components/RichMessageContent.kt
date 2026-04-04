package com.vessences.android.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.vessences.android.data.api.ApiClient
import org.json.JSONObject

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
                is MessagePart.JobQueue -> {
                    JobQueueCards(data = part.jsonData)
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
    data class JobQueue(val jsonData: String) : MessagePart()
}

private val IMAGE_PATTERN = Regex("""!\[([^\]]*)\]\(([^)]+)\)""")
private val LINK_IMAGE_PATTERN = Regex("""\[([^\]]*)\]\((\/api\/files\/serve\/[^)]*\.(?:png|jpe?g|gif|webp|bmp|heic|svg))\)""", RegexOption.IGNORE_CASE)
private val JOB_QUEUE_PATTERN = Regex("""<job-queue-data>([\s\S]*?)</job-queue-data>""")

private fun splitMessageParts(text: String): List<MessagePart> {
    val parts = mutableListOf<MessagePart>()

    // First, extract job-queue-data blocks
    data class TagMatch(val range: IntRange, val part: MessagePart)
    val tagMatches = mutableListOf<TagMatch>()

    for (m in JOB_QUEUE_PATTERN.findAll(text)) {
        tagMatches.add(TagMatch(m.range, MessagePart.JobQueue(m.groupValues[1])))
    }
    for (m in IMAGE_PATTERN.findAll(text)) {
        if (tagMatches.none { it.range.first <= m.range.first && m.range.last <= it.range.last }) {
            tagMatches.add(TagMatch(m.range, MessagePart.Image(m.groupValues[1], m.groupValues[2])))
        }
    }
    for (m in LINK_IMAGE_PATTERN.findAll(text)) {
        if (tagMatches.none { it.range.first <= m.range.first && m.range.last <= it.range.last }) {
            tagMatches.add(TagMatch(m.range, MessagePart.Image(m.groupValues[1], m.groupValues[2])))
        }
    }

    val sorted = tagMatches.sortedBy { it.range.first }

    if (sorted.isEmpty()) {
        parts.add(MessagePart.Text(text))
        return parts
    }

    var lastEnd = 0
    for (tm in sorted) {
        if (tm.range.first < lastEnd) continue
        if (tm.range.first > lastEnd) {
            parts.add(MessagePart.Text(text.substring(lastEnd, tm.range.first)))
        }
        parts.add(tm.part)
        lastEnd = tm.range.last + 1
    }
    if (lastEnd < text.length) {
        parts.add(MessagePart.Text(text.substring(lastEnd)))
    }
    return parts
}

private fun resolveImageUrl(url: String): String {
    if (url.startsWith("http://") || url.startsWith("https://")) return url
    val base = ApiClient.getJaneBaseUrl().trimEnd('/')
    val path = if (url.startsWith("/")) url else "/api/files/serve/$url"
    return "$base$path"
}

private data class ParsedJob(
    val num: String,
    val name: String,
    val statusIcon: String,
    val summary: String,
    val status: String,
    val priorityLabel: String,
    val result: String,
    val isComplete: Boolean,
)

private fun parseJobQueue(data: String): Pair<Int, List<ParsedJob>>? {
    return try {
        val json = JSONObject(data)
        val jobs = json.getJSONArray("jobs")
        val count = json.optInt("count", jobs.length())
        val parsed = (0 until jobs.length()).map { i ->
            val job = jobs.getJSONObject(i)
            ParsedJob(
                num = job.optString("num", "?"),
                name = job.optString("name", ""),
                statusIcon = job.optString("status_icon", "❓"),
                summary = job.optString("summary", ""),
                status = job.optString("status", "unknown"),
                priorityLabel = job.optString("priority_label", ""),
                result = job.optString("result", "\u2014"),
                isComplete = job.optString("status", "unknown").contains("complete", ignoreCase = true),
            )
        }
        count to parsed
    } catch (_: Exception) {
        null
    }
}

@Composable
private fun JobQueueCards(data: String) {
    val parsed = remember(data) { parseJobQueue(data) }
    if (parsed == null) {
        Text(
            text = "Could not render job queue.",
            fontSize = 12.sp,
            color = Color(0xFF888888),
        )
        return
    }
    val (count, jobs) = parsed

    Text(
        text = "Job Queue: $count job${if (count != 1) "s" else ""}",
        fontWeight = FontWeight.SemiBold,
        fontSize = 14.sp,
        color = Color.White,
    )
    Spacer(modifier = Modifier.height(4.dp))

    for (job in jobs) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Color(0xFF1A1A2E))
                .padding(horizontal = 12.dp, vertical = 10.dp)
        ) {
            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "#${job.num} ${job.name}",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 13.sp,
                        color = Color.White,
                        modifier = Modifier.weight(1f),
                    )
                    Text(text = job.statusIcon, fontSize = 12.sp)
                }
                if (job.summary.isNotBlank()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = job.summary,
                        fontSize = 11.sp,
                        color = Color(0xFFAAAAAA),
                    )
                }
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(text = job.priorityLabel, fontSize = 11.sp, color = Color.White)
                    Text(text = job.status, fontSize = 11.sp, color = Color(0xFF888888))
                }
                if (job.isComplete && job.result != "\u2014") {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = job.result,
                        fontSize = 11.sp,
                        color = Color(0xFF77CC99),
                    )
                }
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
    }
}
