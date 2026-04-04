package com.vessences.android.ui.chat

import androidx.compose.runtime.Composable
import androidx.activity.ComponentActivity
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import com.vessences.android.data.repository.ChatBackend

@Composable
fun AmberChatScreen() {
    val activity = LocalContext.current as? ComponentActivity
        ?: error("AmberChatScreen requires a ComponentActivity context")
    val viewModel: ChatViewModel = viewModel(
        viewModelStoreOwner = activity,
        key = "amber_chat",
        factory = ChatViewModelFactory(
            appContext = LocalContext.current.applicationContext,
            backend = ChatBackend.VAULT,
        )
    )
    ChatScreen(
        viewModel = viewModel,
        aiName = "Amber",
        aiColor = Color(0xFFF59E0B),
        subtitle = "Personal AI companion",
        wakeWordsLabel = "\"hey amber\", \"amberlee\"",
    )
}
