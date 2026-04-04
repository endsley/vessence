package com.vessences.android.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.vessences.android.data.api.ApiClient
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

private val BgColor = Color(0xFF0F172A)
private val CardColor = Color(0xFF1E293B)
private val StatusGreen = Color(0xFF22C55E)
private val StatusGrey = Color(0xFF64748B)
private val StatusOrange = Color(0xFFF97316)

data class QueuePrompt(
    val index: Int,
    val status: String,
    val text: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PromptQueueSheet(
    visible: Boolean,
    onDismiss: () -> Unit,
) {
    if (!visible) return

    val scope = rememberCoroutineScope()
    var prompts by remember { mutableStateOf<List<QueuePrompt>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var newText by remember { mutableStateOf("") }
    val gson = remember { Gson() }

    fun loadPrompts() {
        scope.launch(Dispatchers.IO) {
            loading = true
            try {
                val request = Request.Builder()
                    .url("${ApiClient.getJaneBaseUrl()}/api/prompts/list")
                    .get()
                    .build()
                val response = ApiClient.getOkHttpClient().newCall(request).execute()
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    val type = object : TypeToken<Map<String, List<QueuePrompt>>>() {}.type
                    val data: Map<String, List<QueuePrompt>> = gson.fromJson(body, type)
                    withContext(Dispatchers.Main) {
                        prompts = data["prompts"] ?: emptyList()
                    }
                }
                response.close()
            } catch (_: Exception) {}
            withContext(Dispatchers.Main) { loading = false }
        }
    }

    fun addPrompt() {
        val text = newText.trim()
        if (text.isEmpty()) return
        scope.launch(Dispatchers.IO) {
            try {
                val body = gson.toJson(mapOf("text" to text))
                val request = Request.Builder()
                    .url("${ApiClient.getJaneBaseUrl()}/api/prompts/add")
                    .post(body.toRequestBody("application/json".toMediaType()))
                    .build()
                ApiClient.getOkHttpClient().newCall(request).execute().close()
                withContext(Dispatchers.Main) { newText = "" }
                loadPrompts()
            } catch (_: Exception) {}
        }
    }

    fun deletePrompt(index: Int) {
        scope.launch(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url("${ApiClient.getJaneBaseUrl()}/api/prompts/delete/$index")
                    .delete()
                    .build()
                ApiClient.getOkHttpClient().newCall(request).execute().close()
                loadPrompts()
            } catch (_: Exception) {}
        }
    }

    fun retryPrompt(index: Int) {
        scope.launch(Dispatchers.IO) {
            try {
                val body = "{}".toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url("${ApiClient.getJaneBaseUrl()}/api/prompts/retry/$index")
                    .post(body)
                    .build()
                ApiClient.getOkHttpClient().newCall(request).execute().close()
                loadPrompts()
            } catch (_: Exception) {}
        }
    }

    fun reorder(index: Int, direction: Int) {
        val pending = prompts.filter { it.status == "pending" }.toMutableList()
        val pos = pending.indexOfFirst { it.index == index }
        if (pos < 0) return
        val newPos = pos + direction
        if (newPos < 0 || newPos >= pending.size) return
        val tmp = pending[pos]
        pending[pos] = pending[newPos]
        pending[newPos] = tmp
        val nonPending = prompts.filter { it.status != "pending" }
        val newOrder = (pending + nonPending).map { it.index }

        scope.launch(Dispatchers.IO) {
            try {
                val body = gson.toJson(mapOf("order" to newOrder))
                val request = Request.Builder()
                    .url("${ApiClient.getJaneBaseUrl()}/api/prompts/reorder")
                    .post(body.toRequestBody("application/json".toMediaType()))
                    .build()
                ApiClient.getOkHttpClient().newCall(request).execute().close()
                loadPrompts()
            } catch (_: Exception) {}
        }
    }

    LaunchedEffect(visible) {
        if (visible) loadPrompts()
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = BgColor,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp),
        ) {
            Text("Prompt Queue", color = Color.White, fontSize = 18.sp)
            Spacer(modifier = Modifier.height(12.dp))

            // Add new
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = newText,
                    onValueChange = { newText = it },
                    placeholder = { Text("Add a task...", fontSize = 13.sp) },
                    modifier = Modifier.weight(1f).height(48.dp),
                    textStyle = androidx.compose.ui.text.TextStyle(fontSize = 13.sp, color = Color.White),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFF7C3AED),
                        unfocusedBorderColor = Color(0xFF334155),
                        cursorColor = Color.White,
                    ),
                )
                Spacer(modifier = Modifier.width(8.dp))
                Button(
                    onClick = { addPrompt() },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF7C3AED)),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                ) {
                    Text("Add", fontSize = 13.sp)
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (loading) {
                Box(modifier = Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Color(0xFF7C3AED), modifier = Modifier.size(24.dp))
                }
            } else if (prompts.isEmpty()) {
                Text("Queue is empty", color = StatusGrey, fontSize = 13.sp, modifier = Modifier.padding(16.dp))
            } else {
                LazyColumn(
                    modifier = Modifier.heightIn(max = 400.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    itemsIndexed(prompts) { _, p ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(CardColor, RoundedCornerShape(8.dp))
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.Top,
                        ) {
                            // Status dot
                            Box(
                                modifier = Modifier
                                    .padding(top = 4.dp)
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(
                                        when (p.status) {
                                            "pending" -> StatusGreen
                                            "complete" -> StatusGrey
                                            "incomplete" -> StatusOrange
                                            else -> StatusGrey
                                        }
                                    )
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            // Text
                            Text(
                                text = p.text,
                                color = if (p.status == "complete") StatusGrey else Color(0xFFCBD5E1),
                                fontSize = 12.sp,
                                maxLines = 3,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f),
                            )
                            // Actions
                            if (p.status == "pending") {
                                IconButton(onClick = { reorder(p.index, -1) }, modifier = Modifier.size(28.dp)) {
                                    Icon(Icons.Default.ArrowUpward, "Move up", tint = StatusGrey, modifier = Modifier.size(16.dp))
                                }
                                IconButton(onClick = { reorder(p.index, 1) }, modifier = Modifier.size(28.dp)) {
                                    Icon(Icons.Default.ArrowDownward, "Move down", tint = StatusGrey, modifier = Modifier.size(16.dp))
                                }
                            }
                            if (p.status == "incomplete") {
                                IconButton(onClick = { retryPrompt(p.index) }, modifier = Modifier.size(28.dp)) {
                                    Icon(Icons.Default.Refresh, "Retry", tint = StatusOrange, modifier = Modifier.size(16.dp))
                                }
                            }
                            IconButton(onClick = { deletePrompt(p.index) }, modifier = Modifier.size(28.dp)) {
                                Icon(Icons.Default.Delete, "Delete", tint = Color(0xFFEF4444).copy(alpha = 0.6f), modifier = Modifier.size(16.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}
