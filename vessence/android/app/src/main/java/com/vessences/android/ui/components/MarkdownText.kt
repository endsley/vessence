package com.vessences.android.ui.components

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.sp

@Composable
fun MarkdownText(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.White,
    fontSize: Float = 14f,
) {
    val annotated = parseBasicMarkdown(text, color, fontSize)
    Text(
        text = annotated,
        modifier = modifier,
    )
}

private fun parseBasicMarkdown(
    text: String,
    baseColor: Color,
    fontSize: Float,
): AnnotatedString = buildAnnotatedString {
    val baseStyle = SpanStyle(color = baseColor, fontSize = fontSize.sp)
    var i = 0
    val chars = text.toCharArray()

    while (i < chars.size) {
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
