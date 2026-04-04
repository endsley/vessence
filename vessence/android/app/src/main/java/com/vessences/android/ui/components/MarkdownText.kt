package com.vessences.android.ui.components

import androidx.compose.foundation.text.ClickableText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.sp
import com.vessences.android.data.api.ApiClient

@Composable
fun MarkdownText(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.White,
    fontSize: Float = 14f,
) {
    val annotated = parseBasicMarkdown(text, color, fontSize)
    val uriHandler = LocalUriHandler.current

    ClickableText(
        text = annotated,
        modifier = modifier,
        onClick = { offset ->
            annotated.getStringAnnotations("URL", offset, offset).firstOrNull()?.let { annotation ->
                val url = annotation.item
                val fullUrl = if (url.startsWith("/")) {
                    ApiClient.getJaneBaseUrl().trimEnd('/') + url
                } else {
                    url
                }
                uriHandler.openUri(fullUrl)
            }
        },
    )
}

// Regex for markdown links: [text](url) — but NOT image links ![alt](url)
private val LINK_PATTERN = Regex("""(?<!!)\[([^\]]+)\]\(([^)]+)\)""")

private fun parseBasicMarkdown(
    text: String,
    baseColor: Color,
    fontSize: Float,
): AnnotatedString = buildAnnotatedString {
    val baseStyle = SpanStyle(color = baseColor, fontSize = fontSize.sp)
    val linkStyle = baseStyle.copy(
        color = Color(0xFF64B5F6),
        textDecoration = TextDecoration.Underline,
    )

    // First pass: find all markdown links and their positions
    val linkMatches = LINK_PATTERN.findAll(text).toList()
    var i = 0
    val chars = text.toCharArray()

    while (i < chars.size) {
        // Check if current position is the start of a markdown link
        val linkMatch = linkMatches.find { it.range.first == i }
        if (linkMatch != null) {
            val linkText = linkMatch.groupValues[1]
            val linkUrl = linkMatch.groupValues[2]
            pushStringAnnotation("URL", linkUrl)
            withStyle(linkStyle) {
                append(linkText)
            }
            pop()
            i = linkMatch.range.last + 1
            continue
        }

        // Skip if we're inside a link match range
        if (linkMatches.any { i in it.range }) {
            i++
            continue
        }

        when {
            // Bold: **text**
            i + 1 < chars.size && chars[i] == '*' && chars[i + 1] == '*' -> {
                val end = text.indexOf("**", i + 2)
                if (end > 0) {
                    withStyle(baseStyle.copy(fontWeight = FontWeight.Bold)) {
                        append(text.substring(i + 2, end))
                    }
                    i = end + 2
                } else {
                    withStyle(baseStyle) { append(chars[i]) }
                    i++
                }
            }
            // Inline code: `text`
            chars[i] == '`' -> {
                val end = text.indexOf('`', i + 1)
                if (end > 0) {
                    withStyle(
                        baseStyle.copy(
                            fontFamily = FontFamily.Monospace,
                            background = Color(0xFF334155),
                            fontSize = (fontSize - 1).sp,
                        )
                    ) {
                        append(" ${text.substring(i + 1, end)} ")
                    }
                    i = end + 1
                } else {
                    withStyle(baseStyle) { append(chars[i]) }
                    i++
                }
            }
            else -> {
                withStyle(baseStyle) { append(chars[i]) }
                i++
            }
        }
    }
}
