package com.vessences.android.util

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import com.vessences.android.data.api.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import java.io.File

/**
 * Manages local caching of briefing audio files.
 * - WiFi: prefetch all audio to local cache
 * - Mobile: stream on demand
 * - Daily cleanup: delete cached files older than 1 day
 */
object BriefingAudioCache {
    private const val TAG = "BriefingAudioCache"
    private const val CACHE_DIR_NAME = "briefing_audio"
    private const val MAX_AGE_MS = 24 * 60 * 60 * 1000L // 1 day

    private fun getCacheDir(context: Context): File {
        val dir = File(context.cacheDir, CACHE_DIR_NAME)
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    fun isOnWifi(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return false
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }

    fun getCachedFile(context: Context, articleId: String, summaryType: String = "brief"): File? {
        // Prefer .ogg (Opus), fall back to .wav
        val oggFile = File(getCacheDir(context), "${articleId}_${summaryType}.ogg")
        if (oggFile.exists() && oggFile.length() > 0) return oggFile
        val wavFile = File(getCacheDir(context), "${articleId}_${summaryType}.wav")
        if (wavFile.exists() && wavFile.length() > 0) return wavFile
        return null
    }

    /**
     * Download a single audio file to cache. Returns the local file, null on
     * normal failure, or throws ServerBusyException on 503 so callers can
     * stop hammering the server.
     */
    class ServerBusyException(val retryAfterSecs: Int = 60) : Exception("Server busy (503)")

    suspend fun downloadToCache(
        context: Context,
        articleId: String,
        summaryType: String = "brief",
    ): File? = withContext(Dispatchers.IO) {
        // Check if already cached (either extension)
        val existing = getCachedFile(context, articleId, summaryType)
        if (existing != null) return@withContext existing

        try {
            val url = "${ApiClient.getJaneBaseUrl()}/api/briefing/audio/$articleId/$summaryType"
            val request = Request.Builder().url(url).build()
            val response = ApiClient.getOkHttpClient().newCall(request).execute()
            if (response.code == 503) {
                // Server is under heavy load — stop prefetching
                val retryAfter = response.header("Retry-After")?.toIntOrNull() ?: 60
                response.close()
                throw ServerBusyException(retryAfter)
            }
            if (!response.isSuccessful) {
                response.close()
                return@withContext null
            }
            // Determine file extension from Content-Type header
            val contentType = response.header("Content-Type") ?: ""
            val ext = when {
                contentType.contains("audio/wav") || contentType.contains("audio/wave") -> ".wav"
                contentType.contains("audio/ogg") || contentType.contains("audio/opus") -> ".ogg"
                else -> ".ogg" // Default to .ogg (server prefers Opus)
            }
            val cacheFile = File(getCacheDir(context), "${articleId}_${summaryType}$ext")
            response.body?.byteStream()?.use { input ->
                cacheFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            }
            response.close()
            if (cacheFile.length() > 0) {
                Log.d(TAG, "Cached: ${cacheFile.name} (${cacheFile.length()} bytes)")
                cacheFile
            } else {
                cacheFile.delete()
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "Download failed for $articleId: ${e.message}")
            null
        }
    }

    /**
     * Prefetch audio for a list of article IDs. Call on WiFi only.
     * Stops early if the server returns 503 (busy). Returns count cached.
     */
    suspend fun prefetchAll(
        context: Context,
        articleIds: List<String>,
        summaryType: String = "brief",
    ): Int = withContext(Dispatchers.IO) {
        var cached = 0
        for (id in articleIds) {
            try {
                val result = downloadToCache(context, id, summaryType)
                if (result != null) cached++
            } catch (e: ServerBusyException) {
                Log.i(TAG, "Server busy — pausing prefetch (retry after ${e.retryAfterSecs}s). Cached $cached so far.")
                break
            }
        }
        Log.d(TAG, "Prefetched $cached/${articleIds.size} audio files")
        cached
    }

    /**
     * Delete cached audio files older than 1 day.
     */
    fun cleanupOldFiles(context: Context): Int {
        val dir = getCacheDir(context)
        val cutoff = System.currentTimeMillis() - MAX_AGE_MS
        var deleted = 0
        dir.listFiles()?.forEach { file ->
            if (file.lastModified() < cutoff) {
                file.delete()
                deleted++
            }
        }
        if (deleted > 0) Log.d(TAG, "Cleaned up $deleted old audio files")
        return deleted
    }
}
