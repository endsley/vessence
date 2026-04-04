package com.vessences.android.ui.chat

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.vessences.android.data.model.ChatMessage
import com.vessences.android.ui.components.MessageBubble

@Composable
fun ChatMessageList(
    messages: List<ChatMessage>,
    aiName: String,
    aiColor: Color,
    listState: LazyListState,
    modifier: Modifier = Modifier,
    onNavigateToEssence: ((String) -> Unit)? = null,
    onSpeakText: ((String) -> Unit)? = null,
) {
    LazyColumn(
        modifier = modifier
            .fillMaxWidth(),
        state = listState,
        contentPadding = PaddingValues(vertical = 8.dp),
    ) {
        if (messages.isEmpty()) {
            item {
                Box(
                    modifier = Modifier
                        .fillParentMaxSize()
                        .padding(32.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "Say something to $aiName",
                        color = Color(0xFF64748B),
                        fontSize = 16.sp,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    )
                }
            }
        }
        items(messages, key = { it.id }) { message ->
            MessageBubble(
                message = message,
                aiName = aiName,
                aiColor = aiColor,
                onNavigateToEssence = onNavigateToEssence,
                onSpeakText = onSpeakText,
            )
        }
    }
}
