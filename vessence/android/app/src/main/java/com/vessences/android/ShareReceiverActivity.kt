package com.vessences.android

import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.EditText
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.core.app.NotificationCompat
import com.vessences.android.data.api.ApiClient
import com.vessences.android.util.Constants
import com.vessences.android.voice.AndroidTtsManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

/**
 * Handles shared URLs via a two-option dialog. The normal share flow is
 * server-first: Android sends the URL/category to Jane and the backend handles
 * extraction, summarization, and saving. WebView extraction is not part of the
 * default path.
 */
class ShareReceiverActivity : ComponentActivity() {

    companion object {
        private const val CATEGORY_PATH_SEPARATOR = " > "
    }

    private data class SavedArticleChoice(
        val category: String,
        val title: String,
    )

    private data class SavedDestinationData(
        val categories: List<String>,
        val articles: List<SavedArticleChoice>,
    )

    private sealed class CategoryBrowserRow {
        data object Up : CategoryBrowserRow()
        data class Category(val path: String) : CategoryBrowserRow()
        data class Article(val title: String) : CategoryBrowserRow()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (intent?.action != Intent.ACTION_SEND) {
            finish()
            return
        }

        val sharedText = intent.getStringExtra(Intent.EXTRA_TEXT)
        if (sharedText == null) {
            finish()
            return
        }

        val url = extractUrl(sharedText)

        if (url == null) {
            val forward = Intent(this, MainActivity::class.java).apply {
                action = Intent.ACTION_SEND
                type = intent.type
                putExtra(Intent.EXTRA_TEXT, sharedText)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(forward)
            finish()
            return
        }

        try {
            ApiClient.getOkHttpClient()
        } catch (_: UninitializedPropertyAccessException) {
            ApiClient.init(applicationContext)
        }

        AlertDialog.Builder(this)
            .setTitle("Share Article")
            .setItems(arrayOf("Summarize Now", "Save to Daily Briefing")) { _, which ->
                when (which) {
                    0 -> summarizeNow(url)
                    1 -> chooseSaveDestination(url)
                }
            }
            .setOnCancelListener { finish() }
            .show()
    }

    private fun extractUrl(text: String): String? {
        val urlPattern = Regex("""https?://\S+""")
        return urlPattern.find(text)?.value
    }

    private fun openArticleReader(url: String, mode: String, saveCategory: String? = null) {
        startActivity(Intent(this, ArticleReaderV2Activity::class.java).apply {
            putExtra(ArticleReaderV2Activity.EXTRA_URL, url)
            putExtra(ArticleReaderV2Activity.EXTRA_MODE, mode)
            if (!saveCategory.isNullOrBlank()) {
                putExtra(ArticleReaderV2Activity.EXTRA_SAVE_CATEGORY, saveCategory)
            }
        })
        finish()
    }

    private fun chooseSaveDestination(url: String) {
        val progress = AlertDialog.Builder(this)
            .setTitle("Saved Categories")
            .setMessage("Loading categories...")
            .setNegativeButton("Cancel") { _, _ -> finish() }
            .setOnCancelListener { finish() }
            .show()

        ShareSummarizer.scope.launch {
            val data = fetchSavedDestinationData()
            withContext(Dispatchers.Main) {
                if (!isFinishing && !isDestroyed) {
                    progress.dismiss()
                    showCategoryBrowser(url, data, currentPath = "")
                }
            }
        }
    }

    private suspend fun fetchSavedDestinationData(): SavedDestinationData = withContext(Dispatchers.IO) {
        val categories = mutableSetOf("Uncategorized")
        val articles = mutableListOf<SavedArticleChoice>()
        try {
            val client = ApiClient.getOkHttpClient()
            val categoriesRequest = Request.Builder()
                .url("${serverBaseUrl().trimEnd('/')}/api/briefing/saved/categories")
                .get()
                .build()
            client.newCall(categoriesRequest).execute().use { response ->
                if (response.isSuccessful) {
                    val body = response.body?.string().orEmpty()
                    val arr = JSONObject(body).optJSONArray("categories") ?: JSONArray()
                    for (i in 0 until arr.length()) {
                        normalizeCategory(arr.optString(i))?.let { categories += it }
                    }
                }
            }

            val articlesRequest = Request.Builder()
                .url("${serverBaseUrl().trimEnd('/')}/api/briefing/saved")
                .get()
                .build()
            client.newCall(articlesRequest).execute().use { response ->
                if (response.isSuccessful) {
                    val body = response.body?.string().orEmpty()
                    val arr = JSONObject(body).optJSONArray("articles") ?: JSONArray()
                    for (i in 0 until arr.length()) {
                        val entry = arr.optJSONObject(i) ?: continue
                        val category = normalizeCategory(entry.optString("category"))
                            ?: "Uncategorized"
                        val article = entry.optJSONObject("article")
                        val title = article?.optString("title")?.takeIf { it.isNotBlank() }
                            ?: entry.optString("article_id", "Saved article")
                        categories += category
                        articles += SavedArticleChoice(category, title)
                    }
                }
            }
        } catch (_: Exception) {
            // Empty destination data is still usable: the user can add a category.
        }
        SavedDestinationData(
            categories = categories.toList().sortedWith(String.CASE_INSENSITIVE_ORDER),
            articles = articles.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.title }),
        )
    }

    private fun showCategoryBrowser(url: String, data: SavedDestinationData, currentPath: String) {
        val currentCategory = currentPath.ifBlank { "Uncategorized" }
        val childCategories = data.categories
            .mapNotNull { childCategoryPath(currentPath, it) }
            .distinct()
            .sortedWith(String.CASE_INSENSITIVE_ORDER)
        val directArticles = if (currentPath.isBlank()) {
            emptyList()
        } else {
            data.articles
                .filter { it.category == currentCategory }
                .sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.title })
        }
        val rows = buildList {
            if (currentPath.isNotBlank()) add(CategoryBrowserRow.Up)
            childCategories.forEach { add(CategoryBrowserRow.Category(it)) }
            directArticles.forEach { add(CategoryBrowserRow.Article(it.title)) }
        }
        val labels = rows.map { row ->
            when (row) {
                CategoryBrowserRow.Up -> "< Up one level"
                is CategoryBrowserRow.Category -> "Category: ${categoryLabel(row.path)}"
                is CategoryBrowserRow.Article -> "Article: ${row.title}"
            }
        }.ifEmpty {
            listOf("No subcategories or articles here yet")
        }.toTypedArray()

        val dialog = AlertDialog.Builder(this)
            .setTitle(if (currentPath.isBlank()) "Choose Category" else currentPath)
            .setItems(labels) { _, which ->
                val row = rows.getOrNull(which)
                when (row) {
                    CategoryBrowserRow.Up -> showCategoryBrowser(url, data, parentCategoryPath(currentPath))
                    is CategoryBrowserRow.Category -> showCategoryBrowser(url, data, row.path)
                    is CategoryBrowserRow.Article -> {
                        Toast.makeText(this, row.title, Toast.LENGTH_SHORT).show()
                        showCategoryBrowser(url, data, currentPath)
                    }
                    null -> showCategoryBrowser(url, data, currentPath)
                }
            }
            .setPositiveButton(if (currentPath.isBlank()) "Save Uncategorized" else "Save to This Category") { _, _ ->
                addToBriefing(url, currentCategory)
            }
            .setNegativeButton("Cancel") { _, _ -> finish() }
            .setNeutralButton("New Category", null)
            .setOnCancelListener { finish() }
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener {
                dialog.dismiss()
                showAddCategoryDialog(url, data, currentPath)
            }
        }
        dialog.show()
    }

    private fun showAddCategoryDialog(url: String, data: SavedDestinationData, parentPath: String) {
        showTextInputDialog(
            title = if (parentPath.isBlank()) "New Category" else "New Category In $parentPath",
            hint = "Category name",
            finishOnCancel = false,
            onCancel = { showCategoryBrowser(url, data, parentPath) },
        ) { value ->
            val child = normalizeCategory(value) ?: return@showTextInputDialog false
            val newPath = if (parentPath.isBlank()) child else "$parentPath$CATEGORY_PATH_SEPARATOR$child"
            val updated = data.copy(categories = (data.categories + newPath).distinct())
            showCategoryBrowser(url, updated, newPath)
            true
        }
    }

    private fun childCategoryPath(parentPath: String, category: String): String? {
        val normalized = normalizeCategory(category) ?: return null
        if (parentPath.isBlank()) {
            return normalized.substringBefore(CATEGORY_PATH_SEPARATOR).trim().takeIf { it.isNotBlank() }
        }
        if (normalized == parentPath) return null
        val prefix = "$parentPath$CATEGORY_PATH_SEPARATOR"
        if (!normalized.startsWith(prefix)) return null
        val child = normalized.removePrefix(prefix)
            .substringBefore(CATEGORY_PATH_SEPARATOR)
            .trim()
        if (child.isBlank()) return null
        return "$parentPath$CATEGORY_PATH_SEPARATOR$child"
    }

    private fun parentCategoryPath(path: String): String {
        val index = path.lastIndexOf(CATEGORY_PATH_SEPARATOR)
        return if (index > 0) path.substring(0, index) else ""
    }

    private fun categoryLabel(path: String): String =
        path.substringAfterLast(CATEGORY_PATH_SEPARATOR).ifBlank { path }

    private fun showTextInputDialog(
        title: String,
        hint: String,
        finishOnCancel: Boolean = true,
        onCancel: (() -> Unit)? = null,
        onSubmit: (String) -> Boolean,
    ) {
        val input = EditText(this).apply {
            this.hint = hint
            setSingleLine(true)
            setSelectAllOnFocus(false)
        }
        val dialog = AlertDialog.Builder(this)
            .setTitle(title)
            .setView(input)
            .setPositiveButton("Save", null)
            .setNegativeButton("Cancel") { _, _ ->
                onCancel?.invoke()
                if (finishOnCancel) finish()
            }
            .setOnCancelListener {
                onCancel?.invoke()
                if (finishOnCancel) finish()
            }
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                if (!onSubmit(input.text?.toString().orEmpty())) {
                    Toast.makeText(this, "Enter a category name", Toast.LENGTH_SHORT).show()
                } else {
                    dialog.dismiss()
                }
            }
        }
        dialog.show()
    }

    private fun normalizeCategory(raw: String?): String? {
        val value = raw
            ?.trim()
            ?.replace(Regex("""\s*/\s*"""), CATEGORY_PATH_SEPARATOR)
            ?.replace(Regex("""\s*>\s*"""), CATEGORY_PATH_SEPARATOR)
            ?.replace(Regex("""\s+"""), " ")
            ?.trim()
            ?.trim('>')
            ?.trim()
            .orEmpty()
        return value.takeIf { it.isNotBlank() }
    }

    private fun serverBaseUrl(): String {
        val prefs = applicationContext.getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        return prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL
    }

    /**
     * Send URL to the server. The server fetches it (HTTP first, headless
     * browser fallback) and returns an LLM summary. No WebView extraction.
     */
    private fun summarizeNow(url: String) {
        val appCtx = applicationContext
        val prefs = appCtx.getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        val progress = AlertDialog.Builder(this)
            .setTitle("Summarizing article")
            .setMessage("Jane is fetching and summarizing...")
            .setNegativeButton("Cancel") { _, _ -> finish() }
            .setOnCancelListener { finish() }
            .show()

        ShareSummarizer.scope.launch {
            val result = try {
                withContext(Dispatchers.IO) {
                    val client = ApiClient.getOkHttpClient()
                    val body = JSONObject().apply { put("url", url) }
                        .toString()
                        .toRequestBody("application/json".toMediaType())
                    val request = Request.Builder()
                        .url("${serverUrl.trimEnd('/')}/api/briefing/articles/summarize_now")
                        .post(body)
                        .build()
                    client.newCall(request).execute().use { response ->
                        val responseBody = response.body?.string().orEmpty()
                        if (response.isSuccessful && responseBody.isNotEmpty()) {
                            val obj = JSONObject(responseBody)
                            val title = obj.optString("title", "")
                            val summary = obj.optString("summary", "")
                            if (summary.isNotEmpty()) Pair(title.ifEmpty { "Article" }, summary) else null
                        } else null
                    }
                }
            } catch (_: Exception) {
                null
            }

            withContext(Dispatchers.Main) {
                if (!isFinishing && !isDestroyed) progress.dismiss()
                if (result != null) {
                    startActivity(Intent(this@ShareReceiverActivity, SummaryReaderActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                        putExtra(SummaryReaderActivity.EXTRA_TITLE, result.first)
                        putExtra(SummaryReaderActivity.EXTRA_SUMMARY, result.second)
                        putExtra(SummaryReaderActivity.EXTRA_URL, url)
                    })
                } else {
                    Toast.makeText(appCtx, "Could not fetch or summarize this article", Toast.LENGTH_LONG).show()
                }
                finish()
            }
        }
    }

    /**
     * Send URL to the server's briefing queue. The server will extract
     * and summarize it in the background when the briefing runs.
     */
    private fun addToBriefing(url: String, saveCategory: String = "") {
        val appCtx = applicationContext
        val prefs = appCtx.getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        val progress = AlertDialog.Builder(this)
            .setTitle("Saving article")
            .setMessage(
                if (saveCategory.isNotBlank()) {
                    "Jane is queuing this article for $saveCategory..."
                } else {
                    "Jane is queuing this article..."
                }
            )
            .setNegativeButton("Cancel") { _, _ -> finish() }
            .setOnCancelListener { finish() }
            .show()

        ShareSummarizer.scope.launch {
            val success = try {
                withContext(Dispatchers.IO) {
                    val client = ApiClient.getOkHttpClient()
                    val body = JSONObject().apply {
                        put("url", url)
                        if (saveCategory.isNotBlank()) {
                            put("save_category", saveCategory)
                        }
                    }
                        .toString()
                        .toRequestBody("application/json".toMediaType())
                    val request = Request.Builder()
                        .url("${serverUrl.trimEnd('/')}/api/briefing/articles/submit")
                        .post(body)
                        .build()
                    client.newCall(request).execute().use { it.isSuccessful }
                }
            } catch (_: Exception) {
                false
            }

            withContext(Dispatchers.Main) {
                if (!isFinishing && !isDestroyed) progress.dismiss()
                Toast.makeText(
                    appCtx,
                    if (success && saveCategory.isNotBlank()) {
                        "Article queued and will be saved to $saveCategory"
                    } else if (success) {
                        "Article queued for briefing"
                    } else {
                        "Failed to queue article"
                    },
                    Toast.LENGTH_SHORT,
                ).show()
                finish()
            }
        }
    }
}

/**
 * App-scoped coroutine + notification helpers for share-to summarization.
 * Lives on the process, not on any activity, so work survives the share
 * activity being finished immediately after kickoff.
 */
object ShareSummarizer {

    val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private const val CHANNEL_ID = "jane_share_summary"
    private const val CHANNEL_NAME = "Article summaries"

    fun postSummaryReady(ctx: Context, url: String, title: String, summary: String) {
        ensureChannel(ctx)
        val appCtx = ctx.applicationContext
        // Tap-to-open a dedicated reader screen that shows the text and
        // auto-speaks it, with Stop/Close controls.
        val intent = Intent(appCtx, SummaryReaderActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(SummaryReaderActivity.EXTRA_TITLE, title)
            putExtra(SummaryReaderActivity.EXTRA_SUMMARY, summary)
            putExtra(SummaryReaderActivity.EXTRA_URL, url)
        }
        val pi = PendingIntent.getActivity(
            appCtx, url.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val contentText = summary.take(120).let { if (summary.length > 120) "$it…" else it }
        val notif = NotificationCompat.Builder(appCtx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .setContentTitle("Summary ready: $title")
            .setContentText(contentText)
            .setStyle(NotificationCompat.BigTextStyle().bigText(contentText))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .setContentIntent(pi)
            .build()
        val nm = appCtx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(300_000 + (url.hashCode() and 0xFFFF), notif)

        // Short spoken heads-up so the user hears something even if the
        // phone is in a pocket. Tapping the notification opens the reader
        // which auto-reads the full summary.
        speakHeadsUp(appCtx)
    }

    private fun speakHeadsUp(ctx: Context) {
        scope.launch {
            val audioMan = ctx.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
            val gotFocus = audioMan?.let { requestFocus(it) } ?: false
            try {
                getOrCreateTts(ctx).speak("Your article summary is ready.")
            } catch (e: Exception) {
                Log.w("ShareSummarizer", "heads-up TTS failed: ${e.message}")
            } finally {
                if (gotFocus) audioMan?.let { releaseFocus(it) }
            }
        }
    }

    @Volatile private var tts: AndroidTtsManager? = null
    @Volatile private var focusRequest: AudioFocusRequest? = null

    private fun getOrCreateTts(ctx: Context): AndroidTtsManager {
        tts?.let { return it }
        synchronized(this) {
            tts?.let { return it }
            val created = AndroidTtsManager(ctx.applicationContext)
            tts = created
            return created
        }
    }

    private fun buildFocusRequest(): AudioFocusRequest? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return null
        focusRequest?.let { return it }
        synchronized(this) {
            focusRequest?.let { return it }
            val built = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .build()
            focusRequest = built
            return built
        }
    }

    private suspend fun requestFocus(audioMan: AudioManager): Boolean {
        return withContext(Dispatchers.Main.immediate) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val req = buildFocusRequest() ?: return@withContext false
                audioMan.requestAudioFocus(req) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            } else {
                @Suppress("DEPRECATION")
                audioMan.requestAudioFocus(
                    null,
                    AudioManager.STREAM_MUSIC,
                    AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK,
                ) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            }
        }
    }

    private suspend fun releaseFocus(audioMan: AudioManager) {
        withContext(Dispatchers.Main.immediate) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                buildFocusRequest()?.let { audioMan.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                audioMan.abandonAudioFocus(null)
            }
        }
    }

    fun postSummaryFailed(ctx: Context, url: String) {
        ensureChannel(ctx)
        val notif = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentTitle("Could not summarize article")
            .setContentText(url.take(80))
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setAutoCancel(true)
            .build()
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(300_100 + (url.hashCode() and 0xFFFF), notif)
    }

    private fun ensureChannel(ctx: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Notifications when a shared article's summary is ready"
        }
        nm.createNotificationChannel(channel)
    }
}
