package com.vessences.android.util

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.vessences.android.data.model.StreamEvent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import okhttp3.ResponseBody
import java.io.BufferedReader
import java.io.InputStreamReader

object NdjsonParser {
    private val gson = Gson()

    fun parse(body: ResponseBody): Flow<StreamEvent> = flow {
        val reader = BufferedReader(InputStreamReader(body.byteStream()))
        try {
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                val trimmed = line?.trim() ?: continue
                if (trimmed.isEmpty()) continue
                try {
                    val json = gson.fromJson(trimmed, JsonObject::class.java)
                    val type = json.get("type")?.asString ?: continue
                    val data = json.get("data")?.asString ?: ""
                    val files = if (json.has("files")) {
                        gson.fromJson(json.getAsJsonArray("files"), Array<StreamEvent.FileRef>::class.java).toList()
                    } else {
                        emptyList()
                    }
                    emit(StreamEvent(type = type, data = data, files = files))
                } catch (_: Exception) {
                    // skip malformed lines
                }
            }
        } finally {
            reader.close()
            body.close()
        }
    }.flowOn(Dispatchers.IO)
}
