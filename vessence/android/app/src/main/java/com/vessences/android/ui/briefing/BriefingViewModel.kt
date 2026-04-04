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
import okhttp3.Request
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class BriefingUiState(
    val articles: List<BriefingArticle> = emptyList(),
    val topics: List<BriefingTopic> = emptyList(),
    val categories: List<String> = emptyList(),
    val selectedCategory: String = "All",
    val isLoading: Boolean = false,
    val error: String? = null,
    val lastUpdated: String? = null,
    val expandedArticleId: String? = null,
    val isSpeaking: Boolean = false,
    val readAllActive: Boolean = false,
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

    init {
        // Cleanup old cached audio on startup
        com.vessences.android.util.BriefingAudioCache.cleanupOldFiles(appContext)
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            try {
                val (articles, categories) = fetchArticles()
                val topics = fetchTopics()
                val timestamp = SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date())
                _state.value = _state.value.copy(
                    articles = articles,
                    topics = topics,
                    categories = categories,
                    isLoading = false,
                    lastUpdated = timestamp,
                )
                // WiFi: prefetch all audio in background
                if (com.vessences.android.util.BriefingAudioCache.isOnWifi(appContext) && articles.isNotEmpty()) {
                    launch {
                        com.vessences.android.util.BriefingAudioCache.prefetchAll(
                            appContext,
                            articles.map { it.id },
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
                        .post(okhttp3.RequestBody.create(null, ByteArray(0)))
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
    }

    fun readAll() {
        readAllJob?.cancel()
        readAllJob = viewModelScope.launch {
            _state.value = _state.value.copy(readAllActive = true, isSpeaking = true)
            val articles = getFilteredArticles()
            for (article in articles) {
                if (!_state.value.readAllActive) break
                tts.speak("${article.title}. ${article.briefSummary}")
            }
            _state.value = _state.value.copy(readAllActive = false, isSpeaking = false)
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

    override fun onCleared() {
        super.onCleared()
        readAllJob?.cancel()
        tts.shutdown()
    }
}
