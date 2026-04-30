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
import java.util.concurrent.TimeUnit

/**
 * Single-source-of-truth disk cache for the daily Briefing screen.
 *
 * Stores the entire briefing payload (articles JSON, topics, marketplace,
 * saved-article IDs, archive index) and all article + marketplace thumbnail
 * images under a per-day cache directory. On the first refresh of a new
 * calendar day the previous day's directory is purged.
 *
 * Lifecycle:
 *   - WiFi + stale → fetch all + write cache + prefetch images
 *   - WiFi + fresh → render from cache, no network
 *   - Cellular + cache present → render from cache (saves data); pull-to-refresh
 *     forces a re-fetch
 *   - Offline → existing "no internet" block screen handles it; cache untouched
 *
 * On-disk layout (under context.filesDir/briefing_cache/YYYY-MM-DD/):
 *   articles.json
 *   topics.json
 *   marketplace.json
 *   saved_articles.json
 *   saved_categories.json
 *   archive_dates.json
 *   stamp.txt           (epoch-ms of last successful refresh)
 *   images/<articleId>
 *   marketplace_images/<searchSlug>__<querySlug>__<listingId>__<photoName>
 */
object BriefingCache {
    private const val TAG = "BriefingCache"
    private const val CACHE_ROOT = "briefing_cache"

    // ── Network state ──────────────────────────────────────────────────────────

    fun isOnline(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return false
        val net = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(net) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    fun isOnWifi(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return false
        val net = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(net) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }

    // ── Day stamp ──────────────────────────────────────────────────────────────

    /** Local-date string used as the cache directory name. */
    private fun todayKey(): String {
        val cal = java.util.Calendar.getInstance()
        return "%04d-%02d-%02d".format(
            cal.get(java.util.Calendar.YEAR),
            cal.get(java.util.Calendar.MONTH) + 1,
            cal.get(java.util.Calendar.DAY_OF_MONTH),
        )
    }

    private fun rootDir(context: Context): File =
        File(context.filesDir, CACHE_ROOT).apply { mkdirs() }

    private fun todayDir(context: Context): File {
        val dir = File(rootDir(context), todayKey())
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    /** True when articles.json exists in today's directory. */
    fun isFreshForToday(context: Context): Boolean {
        return File(todayDir(context), "articles.json").exists()
    }

    /** Epoch-ms of the last successful refresh, or 0. */
    fun lastRefreshedAt(context: Context): Long {
        val stamp = File(todayDir(context), "stamp.txt")
        return runCatching { stamp.readText().trim().toLong() }.getOrDefault(0L)
    }

    /** Mark today's cache as freshly written. */
    fun stamp(context: Context) {
        runCatching {
            File(todayDir(context), "stamp.txt").writeText(System.currentTimeMillis().toString())
        }
    }

    /**
     * Delete every cache directory whose name is not today's. Returns the
     * count of directories removed. Called on every successful refresh so
     * yesterday's payload doesn't accumulate.
     */
    fun purgeOldDays(context: Context): Int {
        val today = todayKey()
        var removed = 0
        rootDir(context).listFiles()?.forEach { dir ->
            if (dir.isDirectory && dir.name != today) {
                if (dir.deleteRecursively()) removed++
            }
        }
        if (removed > 0) Log.i(TAG, "Purged $removed old briefing cache day(s)")
        return removed
    }

    // ── JSON file helpers ──────────────────────────────────────────────────────

    private fun read(context: Context, name: String): String? {
        val f = File(todayDir(context), name)
        return if (f.exists() && f.length() > 0) runCatching { f.readText() }.getOrNull() else null
    }

    private fun write(context: Context, name: String, json: String) {
        runCatching { File(todayDir(context), name).writeText(json) }
            .onFailure { Log.w(TAG, "Failed to write $name: ${it.message}") }
    }

    fun loadArticlesJson(context: Context): String? = read(context, "articles.json")
    fun saveArticlesJson(context: Context, json: String) = write(context, "articles.json", json)

    fun loadTopicsJson(context: Context): String? = read(context, "topics.json")
    fun saveTopicsJson(context: Context, json: String) = write(context, "topics.json", json)

    fun loadMarketplaceJson(context: Context): String? = read(context, "marketplace.json")
    fun saveMarketplaceJson(context: Context, json: String) = write(context, "marketplace.json", json)

    fun loadSavedArticlesJson(context: Context): String? = read(context, "saved_articles.json")
    fun saveSavedArticlesJson(context: Context, json: String) = write(context, "saved_articles.json", json)

    fun loadSavedCategoriesJson(context: Context): String? = read(context, "saved_categories.json")
    fun saveSavedCategoriesJson(context: Context, json: String) = write(context, "saved_categories.json", json)

    fun loadArchiveDatesJson(context: Context): String? = read(context, "archive_dates.json")
    fun saveArchiveDatesJson(context: Context, json: String) = write(context, "archive_dates.json", json)

    // ── Article images ─────────────────────────────────────────────────────────

    private fun imagesDir(context: Context): File =
        File(todayDir(context), "images").apply { if (!exists()) mkdirs() }

    fun cachedImageFile(context: Context, articleId: String): File? {
        val f = File(imagesDir(context), articleId)
        return if (f.exists() && f.length() > 0) f else null
    }

    /**
     * Returns a `file://...` URI Coil can load directly when the image is
     * cached locally; otherwise returns the original server URL so Coil
     * falls back to the network fetcher (and OkHttp's normal cache).
     */
    fun resolveImageUrl(context: Context, articleId: String, serverUrl: String): String {
        val f = cachedImageFile(context, articleId) ?: return serverUrl
        return f.toURI().toString()
    }

    suspend fun downloadImage(
        context: Context,
        articleId: String,
        serverUrl: String,
    ): File? = withContext(Dispatchers.IO) {
        val existing = cachedImageFile(context, articleId)
        if (existing != null) return@withContext existing
        try {
            val req = Request.Builder().url(serverUrl).build()
            val resp = ApiClient.getOkHttpClient().newCall(req).execute()
            if (!resp.isSuccessful) {
                resp.close()
                return@withContext null
            }
            val target = File(imagesDir(context), articleId)
            resp.body?.byteStream()?.use { input ->
                target.outputStream().use { out -> input.copyTo(out) }
            }
            resp.close()
            if (target.length() > 0) target else { target.delete(); null }
        } catch (e: Exception) {
            Log.w(TAG, "image download failed for $articleId: ${e.message}")
            null
        }
    }

    /**
     * Best-effort prefetch of a list of (articleId, url) pairs. Stops on
     * first repeated network failure to avoid hammering a flaky link.
     * Caller should gate this on isOnWifi().
     */
    suspend fun prefetchImages(
        context: Context,
        items: List<Pair<String, String>>,
    ): Int = withContext(Dispatchers.IO) {
        var ok = 0
        var consecutiveFailures = 0
        for ((id, url) in items) {
            val result = runCatching { downloadImage(context, id, url) }.getOrNull()
            if (result != null) {
                ok++
                consecutiveFailures = 0
            } else {
                consecutiveFailures++
                if (consecutiveFailures >= 5) {
                    Log.i(TAG, "image prefetch: 5 consecutive failures, giving up after $ok cached")
                    break
                }
            }
        }
        Log.d(TAG, "image prefetch: cached $ok of ${items.size}")
        ok
    }

    // ── Marketplace images ─────────────────────────────────────────────────────

    private fun marketplaceImagesDir(context: Context): File =
        File(todayDir(context), "marketplace_images").apply { if (!exists()) mkdirs() }

    private fun marketplaceImageKey(
        searchName: String,
        querySlug: String,
        listingId: String,
        photoName: String,
    ): String = "${searchName}__${querySlug}__${listingId}__${photoName}"
        .replace('/', '_').replace(File.separatorChar, '_')

    fun cachedMarketplaceImageFile(
        context: Context,
        searchName: String,
        querySlug: String,
        listingId: String,
        photoName: String,
    ): File? {
        val f = File(
            marketplaceImagesDir(context),
            marketplaceImageKey(searchName, querySlug, listingId, photoName),
        )
        return if (f.exists() && f.length() > 0) f else null
    }

    fun resolveMarketplaceImageUrl(
        context: Context,
        searchName: String,
        querySlug: String,
        listingId: String,
        photoName: String,
        serverUrl: String,
    ): String {
        val f = cachedMarketplaceImageFile(context, searchName, querySlug, listingId, photoName)
            ?: return serverUrl
        return f.toURI().toString()
    }

    /**
     * Marketplace image prefetch entries: serverUrl + the four key parts
     * needed to build the on-disk filename.
     */
    data class MarketplaceImageRef(
        val searchName: String,
        val querySlug: String,
        val listingId: String,
        val photoName: String,
        val serverUrl: String,
    )

    suspend fun prefetchMarketplaceImages(
        context: Context,
        items: List<MarketplaceImageRef>,
    ): Int = withContext(Dispatchers.IO) {
        var ok = 0
        var consecutiveFailures = 0
        for (it in items) {
            val target = File(
                marketplaceImagesDir(context),
                marketplaceImageKey(it.searchName, it.querySlug, it.listingId, it.photoName),
            )
            if (target.exists() && target.length() > 0) {
                ok++
                continue
            }
            try {
                val req = Request.Builder().url(it.serverUrl).build()
                val resp = ApiClient.getOkHttpClient().newCall(req).execute()
                if (!resp.isSuccessful) {
                    resp.close()
                    consecutiveFailures++
                    if (consecutiveFailures >= 5) break
                    continue
                }
                resp.body?.byteStream()?.use { input ->
                    target.outputStream().use { out -> input.copyTo(out) }
                }
                resp.close()
                if (target.length() > 0) {
                    ok++
                    consecutiveFailures = 0
                } else {
                    target.delete()
                    consecutiveFailures++
                }
            } catch (e: Exception) {
                Log.w(TAG, "marketplace image fetch failed (${it.listingId}): ${e.message}")
                consecutiveFailures++
                if (consecutiveFailures >= 5) break
            }
        }
        Log.d(TAG, "marketplace image prefetch: cached $ok of ${items.size}")
        ok
    }

    // ── Total cache size (for diagnostics / Settings UI) ───────────────────────

    fun totalSizeBytes(context: Context): Long {
        var total = 0L
        rootDir(context).walkBottomUp().forEach {
            if (it.isFile) total += it.length()
        }
        return total
    }

    @Suppress("unused")
    fun ageMillis(context: Context): Long {
        val stamp = lastRefreshedAt(context)
        return if (stamp == 0L) Long.MAX_VALUE else System.currentTimeMillis() - stamp
    }

    @Suppress("unused")
    fun cacheTtl(): Long = TimeUnit.HOURS.toMillis(24)
}
