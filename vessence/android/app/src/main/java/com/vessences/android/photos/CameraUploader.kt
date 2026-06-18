package com.vessences.android.photos

import android.content.ContentResolver
import com.google.gson.Gson
import com.vessences.android.data.api.ApiClient
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okio.BufferedSink
import okio.source

class CameraUploader(
    private val resolver: ContentResolver,
) {
    suspend fun upload(photo: CameraPhoto): Boolean {
        val body = UriRequestBody(resolver, photo)
        val filePart = MultipartBody.Part.createFormData(
            "files",
            photo.displayName,
            body,
        )
        val destination = photo.destination.toRequestBody("text/plain".toMediaType())
        val descriptions = Gson()
            .toJson(listOf(photo.description))
            .toRequestBody("text/plain".toMediaType())
        val response = ApiClient.vaultApi.uploadFiles(
            files = listOf(filePart),
            destination = destination,
            descriptionsJson = descriptions,
        )
        if (!response.isSuccessful) return false
        val results = response.body()?.results.orEmpty()
        return results.any { it.status == "ok" || it.status == "duplicate" }
    }

    private class UriRequestBody(
        private val resolver: ContentResolver,
        private val photo: CameraPhoto,
    ) : RequestBody() {
        override fun contentType() = photo.mimeType.toMediaType()

        override fun contentLength(): Long = photo.size

        override fun writeTo(sink: BufferedSink) {
            resolver.openInputStream(photo.uri)?.use { input ->
                sink.writeAll(input.source())
            } ?: throw IllegalStateException("Cannot read ${photo.uri}")
        }
    }
}
