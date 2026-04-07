package com.vessences.android.ui.briefing

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.vessences.android.data.api.ApiClient
import com.vessences.android.data.model.BriefingArticle
import com.vessences.android.data.model.BriefingTopic
import com.vessences.android.voice.AndroidTtsManager
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class BriefingUiState(
    val articles: List<BriefingArticle> = emptyList(),
    val topics: List<BriefingTopic> = emptyList(),
    val categories: List<String> = emptyList(),
    val selectedCategory: String = "Shared",
    val isLoading: Boolean = false,
    val isLoadingArchive: Boolean = false,
    val error: String? = null,
    val lastUpdated: String? = null,
    val viewingArchiveDate: String? = null,
    val archiveDates: List<String> = emptyList(),
    val expandedArticleId: String? = null,
    val isSpeaking: Boolean = false,
    val readAllActive: Boolean = false,
    val savedArticleIds: Set<String> = emptySet(),
    val savedCategories: List<String> = emptyList(),
    val viewingSaved: Boolean = false,
    val savedArticles: List<com.vessences.android.data.model.SavedArticleEntry> = emptyList(),
    val savedFilterCategory: String? = null,
)

class BriefingViewModel(application: Application) : AndroidViewModel(application) {
    private val _state = MutableStateFlow(BriefingUiState())
    val state: StateFlow<BriefingUiState> = _state

    private val client = ApiClient.getOkHttpClient()
    private val baseUrl = ApiClient.getJaneBaseUrl()
    private val gson = Gson()
    private val tts = AndroidTtsManager(application)
    private var readAllJob: Job? = null

    private val appContext = application.applicationContext
    private val articlesCacheFile = File(application.filesDir, "briefing_articles_cache.json")

    init {
        // Cleanup old cached audio on startup
        com.vessences.android.util.BriefingAudioCache.cleanupOldFiles(appContext)
        // Load cached articles immediately so UI has content before network fetch
        loadCachedArticles()?.let { (articles, categories) ->
            val effectiveCategory = if ("Shared" in categories) "Shared" else "All"
            _state.value = _state.value.copy(
                articles = articles,
                categories = categories,
                selectedCategory = effectiveCategory,
                lastUpdated = "cached",
            )
        }
        refresh()
        fetchArchiveDates()
        fetchSavedArticleIds()
        fetchSavedCategories()
    }

    fun refresh() {
        if (_state.value.viewingArchiveDate != null) {
            loadArchive(_state.value.viewingArchiveDate!!)
            return
        }
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            try {
                // Remember previously cached IDs before fetching
                val previousIds = _state.value.articles.map { it.id }.toSet()

                val (articles, categories) = fetchArticles()
                val topics = fetchTopics()
                val timestamp = SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date())
                // Fall back to All if Shared has no articles
                val effectiveCategory = if (_state.value.selectedCategory == "Shared" && "Shared" !in categories) "All" else _state.value.selectedCategory
                _state.value = _state.value.copy(
                    articles = articles,
                    topics = topics,
                    categories = categories,
                    selectedCategory = effectiveCategory,
                    isLoading = false,
                    lastUpdated = timestamp,
                )
                // Save fresh articles to disk cache
                saveCachedArticles(articles, categories)
                // WiFi: prefetch audio only for NEW articles (not already cached)
                val newArticleIds = articles.map { it.id }.filter { it !in previousIds }
                if (com.vessences.android.util.BriefingAudioCache.isOnWifi(appContext) && newArticleIds.isNotEmpty()) {
                    launch {
                        com.vessences.android.util.BriefingAudioCache.prefetchAll(
                            appContext,
                            newArticleIds,
                        )
                    }
                }
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = e.message ?: "Failed to load briefing",
                )
            }
        }
    }

    fun fetchArchiveDates() {
        viewModelScope.launch {
            try {
                val request = Request.Builder().url("$baseUrl/api/briefing/archive").build()
                val response = withContext(Dispatchers.IO) { client.newCall(request).execute() }
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
                    val datesArray = parsed.getAsJsonArray("dates")
                    if (datesArray != null) {
                        val dates: List<String> = gson.fromJson(datesArray, object : TypeToken<List<String>>() {}.type)
                        _state.value = _state.value.copy(archiveDates = dates)
                    }
                }
                response.close()
            } catch (e: Exception) {
                // Ignore archive list failures
            }
        }
    }

    fun loadArchive(date: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoadingArchive = true, error = null)
            try {
                val request = Request.Builder().url("$baseUrl/api/briefing/archive/$date").build()
                val response = withContext(Dispatchers.IO) { client.newCall(request).execute() }
                if (!response.isSuccessful) throw Exception("Archive not found")
                
                val body = response.body?.string() ?: "{}"
                val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
                val cardsArray = parsed.getAsJsonArray("cards")
                val articles: List<BriefingArticle> = gson.fromJson(cardsArray, object : TypeToken<List<BriefingArticle>>() {}.type)
                val categoriesArray = parsed.getAsJsonArray("categories")
                val categories: List<String> = gson.fromJson(categoriesArray, object : TypeToken<List<String>>() {}.type)
                
                _state.value = _state.value.copy(
                    articles = articles,
                    categories = categories,
                    viewingArchiveDate = date,
                    isLoadingArchive = false,
                    lastUpdated = date,
                )
                response.close()
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoadingArchive = false,
                    error = "Failed to load archive for $date",
                )
            }
        }
    }

    fun clearArchive() {
        _state.value = _state.value.copy(viewingArchiveDate = null)
        refresh()
    }

    fun selectCategory(category: String) {
        _state.value = _state.value.copy(selectedCategory = category)
    }

    fun toggleArticleExpanded(articleId: String) {
        val current = _state.value.expandedArticleId
        _state.value = _state.value.copy(
            expandedArticleId = if (current == articleId) null else articleId,
        )
    }

    fun getFilteredArticles(): List<BriefingArticle> {
        val s = _state.value
        val byCategory = if (s.selectedCategory == "All") {
            s.articles
        } else {
            s.articles.filter { s.selectedCategory in it.categories }
        }
        // Non-dismissed first, dismissed at the end
        return byCategory.sortedBy { it.dismissed }
    }

    fun dismissArticle(articleId: String) {
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    val request = Request.Builder()
                        .url("$baseUrl/api/briefing/article/$articleId/dismiss")
                        .post(ByteArray(0).toRequestBody(null))
                        .build()
                    client.newCall(request).execute().close()
                }
                // Update local state
                _state.value = _state.value.copy(
                    articles = _state.value.articles.map {
                        if (it.id == articleId) it.copy(dismissed = !it.dismissed)
                        else it
                    }
                )
            } catch (e: Exception) {
                // Silently ignore dismiss failures
            }
        }
    }

    fun getImageUrl(articleId: String): String {
        return "$baseUrl/api/briefing/image/$articleId"
    }

    private var mediaPlayer: android.media.MediaPlayer? = null

    fun speakArticle(article: BriefingArticle, summaryType: String = "brief") {
        viewModelScope.launch {
            _state.value = _state.value.copy(isSpeaking = true)
            // Pause always-listen during audio playback
            com.vessences.android.voice.WakeWordBridge.sttActive = true
            com.vessences.android.voice.AlwaysListeningService.stop(appContext)

            // Priority: 1) local cache, 2) stream from server, 3) device TTS
            val cachedFile = com.vessences.android.util.BriefingAudioCache.getCachedFile(appContext, article.id, summaryType)
            val played = if (cachedFile != null) {
                // Play from local cache (instant, no network)
                playAudioFile(cachedFile.absolutePath)
            } else {
                // Stream from server
                val audioUrl = "$baseUrl/api/briefing/audio/${article.id}/$summaryType"
                tryPlayServerAudio(audioUrl)
            }

            if (!played) {
                // Fallback to device TTS
                val text = if (summaryType == "full" && article.fullSummary != null) {
                    "${article.title}. ${article.fullSummary}"
                } else {
                    "${article.title}. ${article.briefSummary}"
                }
                tts.speak(text)
            }
            _state.value = _state.value.copy(isSpeaking = false)
            // Resume always-listen after audio finishes
            com.vessences.android.voice.WakeWordBridge.sttActive = false
            val voiceSettings = com.vessences.android.data.repository.VoiceSettingsRepository(appContext)
            if (voiceSettings.isAlwaysListeningEnabled()) {
                com.vessences.android.voice.AlwaysListeningService.start(appContext)
            }
        }
    }

    private suspend fun playAudioFile(path: String): Boolean = withContext(Dispatchers.Main) {
        suspendCancellableCoroutine { continuation ->
            try {
                mediaPlayer?.release()
                val mp = android.media.MediaPlayer()
                mediaPlayer = mp
                mp.setDataSource(path)
                mp.setOnPreparedListener { it.start() }
                mp.setOnCompletionListener {
                    it.release()
                    mediaPlayer = null
                    continuation.resume(true)
                }
                mp.setOnErrorListener { _, _, _ ->
                    mp.release()
                    mediaPlayer = null
                    continuation.resume(false)
                    true
                }
                continuation.invokeOnCancellation {
                    mp.release()
                    mediaPlayer = null
                }
                mp.prepare()  // Sync prepare for local files (instant)
                mp.start()
            } catch (e: Exception) {
                continuation.resume(false)
            }
        }
    }

    private suspend fun tryPlayServerAudio(url: String): Boolean = withContext(Dispatchers.IO) {
        try {
            // Check if audio exists (HEAD request)
            val checkRequest = Request.Builder().url(url).head().build()
            val checkResponse = client.newCall(checkRequest).execute()
            if (!checkResponse.isSuccessful) {
                checkResponse.close()
                return@withContext false
            }
            checkResponse.close()

            // Play via MediaPlayer (streaming)
            withContext(Dispatchers.Main) {
                suspendCancellableCoroutine<Boolean> { continuation ->
                    try {
                        mediaPlayer?.release()
                        val mp = android.media.MediaPlayer()
                        mediaPlayer = mp
                        mp.setDataSource(url)
                        mp.setOnPreparedListener { it.start() }
                        mp.setOnCompletionListener {
                            it.release()
                            mediaPlayer = null
                            continuation.resume(true)
                        }
                        mp.setOnErrorListener { _, _, _ ->
                            mp.release()
                            mediaPlayer = null
                            continuation.resume(false)
                            true
                        }
                        continuation.invokeOnCancellation {
                            mp.release()
                            mediaPlayer = null
                        }
                        mp.prepareAsync()
                    } catch (e: Exception) {
                        continuation.resume(false)
                    }
                }
            }
        } catch (e: Exception) {
            false
        }
    }

    fun stopSpeaking() {
        readAllJob?.cancel()
        tts.stop()
        mediaPlayer?.let {
            try { it.stop(); it.release() } catch (_: Exception) {}
            mediaPlayer = null
        }
        _state.value = _state.value.copy(isSpeaking = false, readAllActive = false)
        // Resume always-listen
        com.vessences.android.voice.WakeWordBridge.sttActive = false
        val voiceSettings = com.vessences.android.data.repository.VoiceSettingsRepository(appContext)
        if (voiceSettings.isAlwaysListeningEnabled()) {
            com.vessences.android.voice.AlwaysListeningService.start(appContext)
        }
    }

    fun readAll(summaryType: String = "brief") {
        readAllJob?.cancel()
        readAllJob = viewModelScope.launch {
            _state.value = _state.value.copy(readAllActive = true, isSpeaking = true)
            // Pause always-listen during read-all
            com.vessences.android.voice.WakeWordBridge.sttActive = true
            com.vessences.android.voice.AlwaysListeningService.stop(appContext)
            val articles = getFilteredArticles()
            for (article in articles) {
                if (!_state.value.readAllActive) break
                val text = if (summaryType == "full" && article.fullSummary != null) {
                    "${article.title}. ${article.fullSummary}"
                } else {
                    "${article.title}. ${article.briefSummary}"
                }
                tts.speak(text)
            }
            _state.value = _state.value.copy(readAllActive = false, isSpeaking = false)
        }
    }

    private fun loadCachedArticles(): Pair<List<BriefingArticle>, List<String>>? {
        return try {
            if (!articlesCacheFile.exists()) return null
            val json = articlesCacheFile.readText()
            val parsed = gson.fromJson(json, com.google.gson.JsonObject::class.java)
            val cardsArray = parsed.getAsJsonArray("articles") ?: return null
            val articles: List<BriefingArticle> = gson.fromJson(
                cardsArray, object : TypeToken<List<BriefingArticle>>() {}.type
            )
            val categoriesArray = parsed.getAsJsonArray("categories")
            val categories: List<String> = if (categoriesArray != null) {
                gson.fromJson(categoriesArray, object : TypeToken<List<String>>() {}.type)
            } else emptyList()
            if (articles.isEmpty()) null else Pair(articles, categories)
        } catch (e: Exception) {
            null
        }
    }

    private fun saveCachedArticles(articles: List<BriefingArticle>, categories: List<String>) {
        try {
            val obj = com.google.gson.JsonObject()
            obj.add("articles", gson.toJsonTree(articles))
            obj.add("categories", gson.toJsonTree(categories))
            articlesCacheFile.writeText(gson.toJson(obj))
        } catch (e: Exception) {
            // Silently ignore cache write failures
        }
    }

    private suspend fun fetchArticles(): Pair<List<BriefingArticle>, List<String>> = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$baseUrl/api/briefing/articles")
            .build()
        val response = client.newCall(request).execute()
        if (!response.isSuccessful) throw Exception("HTTP ${response.code}")
        val body = response.body?.string() ?: "{}"
        // API returns {"status": "ok", "cards": [...], "card_count": N, "categories": [...]}
        val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
        val cardsArray = parsed.getAsJsonArray("cards") ?: return@withContext Pair(emptyList(), emptyList())
        val articlesType = object : TypeToken<List<BriefingArticle>>() {}.type
        val articles: List<BriefingArticle> = gson.fromJson(cardsArray, articlesType)
        val categoriesArray = parsed.getAsJsonArray("categories")
        val categories: List<String> = if (categoriesArray != null) {
            val catType = object : TypeToken<List<String>>() {}.type
            gson.fromJson(categoriesArray, catType)
        } else emptyList()
        Pair(articles, categories)
    }

    private suspend fun fetchTopics(): List<BriefingTopic> = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$baseUrl/api/briefing/topics")
            .build()
        val response = client.newCall(request).execute()
        if (!response.isSuccessful) return@withContext emptyList()
        val body = response.body?.string() ?: "{}"
        // API returns {"status": "ok", "count": N, "topics": [...]}
        val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
        val topicsArray = parsed.getAsJsonArray("topics") ?: return@withContext emptyList()
        val type = object : TypeToken<List<BriefingTopic>>() {}.type
        gson.fromJson(topicsArray, type)
    }

    fun saveArticle(articleId: String, category: String) {
        viewModelScope.launch {
            try {
                val json = gson.toJson(mapOf("article_id" to articleId, "category" to category))
                val body = okhttp3.RequestBody.create(
                    "application/json".toMediaTypeOrNull(), json
                )
                withContext(Dispatchers.IO) {
                    val request = Request.Builder()
                        .url("$baseUrl/api/briefing/saved")
                        .post(body)
                        .build()
                    client.newCall(request).execute().close()
                }
                _state.value = _state.value.copy(
                    savedArticleIds = _state.value.savedArticleIds + articleId,
                )
                // Add category if new
                if (category !in _state.value.savedCategories) {
                    _state.value = _state.value.copy(
                        savedCategories = _state.value.savedCategories + category,
                    )
                }
            } catch (_: Exception) {}
        }
    }

    fun unsaveArticle(articleId: String) {
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    val request = Request.Builder()
                        .url("$baseUrl/api/briefing/saved/$articleId")
                        .delete()
                        .build()
                    client.newCall(request).execute().close()
                }
                _state.value = _state.value.copy(
                    savedArticleIds = _state.value.savedArticleIds - articleId,
                    savedArticles = _state.value.savedArticles.filter { it.articleId != articleId },
                )
            } catch (_: Exception) {}
        }
    }

    fun isArticleSaved(articleId: String): Boolean = articleId in _state.value.savedArticleIds

    fun toggleSavedView() {
        val newVal = !_state.value.viewingSaved
        _state.value = _state.value.copy(viewingSaved = newVal)
        if (newVal) loadSavedArticles()
    }

    fun loadSavedArticles(category: String? = null) {
        viewModelScope.launch {
            try {
                val url = if (category != null) {
                    "$baseUrl/api/briefing/saved?category=${java.net.URLEncoder.encode(category, "UTF-8")}"
                } else {
                    "$baseUrl/api/briefing/saved"
                }
                val request = Request.Builder().url(url).build()
                val response = withContext(Dispatchers.IO) { client.newCall(request).execute() }
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
                    val articlesArray = parsed.getAsJsonArray("articles")
                    if (articlesArray != null) {
                        val type = object : TypeToken<List<com.vessences.android.data.model.SavedArticleEntry>>() {}.type
                        val saved: List<com.vessences.android.data.model.SavedArticleEntry> = gson.fromJson(articlesArray, type)
                        _state.value = _state.value.copy(
                            savedArticles = saved,
                            savedFilterCategory = category,
                        )
                    }
                }
                response.close()
            } catch (_: Exception) {}
        }
    }

    private fun fetchSavedArticleIds() {
        viewModelScope.launch {
            try {
                val request = Request.Builder().url("$baseUrl/api/briefing/saved").build()
                val response = withContext(Dispatchers.IO) { client.newCall(request).execute() }
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
                    val articlesArray = parsed.getAsJsonArray("articles")
                    if (articlesArray != null) {
                        val ids = articlesArray.map {
                            it.asJsonObject.get("article_id")?.asString ?: ""
                        }.filter { it.isNotEmpty() }.toSet()
                        _state.value = _state.value.copy(savedArticleIds = ids)
                    }
                }
                response.close()
            } catch (_: Exception) {}
        }
    }

    private fun fetchSavedCategories() {
        viewModelScope.launch {
            try {
                val request = Request.Builder().url("$baseUrl/api/briefing/saved/categories").build()
                val response = withContext(Dispatchers.IO) { client.newCall(request).execute() }
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
                    val catsArray = parsed.getAsJsonArray("categories")
                    if (catsArray != null) {
                        val serverCats: List<String> = gson.fromJson(catsArray, object : TypeToken<List<String>>() {}.type)
                        val merged = serverCats.distinct()
                        _state.value = _state.value.copy(savedCategories = merged)
                    }
                }
                response.close()
            } catch (_: Exception) {}
        }
    }

    override fun onCleared() {
        super.onCleared()
        readAllJob?.cancel()
        tts.shutdown()
    }
}
