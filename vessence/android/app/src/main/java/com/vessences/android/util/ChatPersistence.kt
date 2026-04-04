package com.vessences.android.util

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.vessences.android.data.model.ChatMessage

/**
 * Persists chat messages to SharedPreferences so they survive app restarts.
 * Each backend (Jane, Amber) gets its own message list.
 */
class ChatPersistence(context: Context) {
    private val prefs = context.getSharedPreferences("chat_history", Context.MODE_PRIVATE)
    private val gson = Gson()

    private val maxPersistedMessages = 100

    fun saveMessages(backendKey: String, messages: List<ChatMessage>) {
        // Only persist completed (non-streaming) messages
        val toSave = messages
            .filter { !it.isStreaming }
            .takeLast(maxPersistedMessages)

        val json = gson.toJson(toSave.map { SerializableMessage.from(it) })
        prefs.edit().putString("messages_$backendKey", json).apply()
    }

    fun loadMessages(backendKey: String): List<ChatMessage> {
        val json = prefs.getString("messages_$backendKey", null) ?: return emptyList()
        return try {
            val type = object : TypeToken<List<SerializableMessage>>() {}.type
            val serialized: List<SerializableMessage> = gson.fromJson(json, type)
            serialized.map { it.toChatMessage() }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun clearMessages(backendKey: String) {
        prefs.edit().remove("messages_$backendKey").apply()
    }

    /**
     * Intermediate class for JSON serialization that avoids issues with
     * the StreamEvent.FileRef nested type.
     */
    private data class SerializableMessage(
        val id: String,
        val text: String,
        val isUser: Boolean,
        val statusText: String? = null,
    ) {
        fun toChatMessage() = ChatMessage(
            id = id,
            text = text,
            isUser = isUser,
            isStreaming = false,
            statusText = statusText,
            files = emptyList(),
        )

        companion object {
            fun from(msg: ChatMessage) = SerializableMessage(
                id = msg.id,
                text = msg.text,
                isUser = msg.isUser,
                statusText = msg.statusText,
            )
        }
    }
}
