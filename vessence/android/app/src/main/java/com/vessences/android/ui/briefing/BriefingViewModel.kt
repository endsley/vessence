package com.vessences.android.ui.briefing

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.vessences.android.data.api.ApiClient
import com.vessences.android.data.model.BriefingArticle
import com.vessences.android.data.model.BriefingTopic
import com.vessences.android.data.model.MarketplaceAiSummary
import com.vessences.android.data.model.MarketplaceListing
import com.vessences.android.data.model.MarketplaceRefreshStatus
import com.vessences.android.data.model.MarketplaceSearch
import com.vessences.android.data.model.MarketplaceSearchCard
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
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class BriefingUiState(
    val selectedTab: String = "News",
    val articles: List<BriefingArticle> = emptyList(),
    val topics: List<BriefingTopic> = emptyList(),
    val categories: List<String> = emptyList(),
    val selectedCategory: String = "All",
    val isLoading: Boolean = false,
    val isLoadingMore: Boolean = false,
    val hasMoreArticles: Boolean = false,
    val isLoadingArchive: Boolean = false,
    val isLoadingMarketplace: Boolean = false,
    val error: String? = null,
    val marketplaceError: String? = null,
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
    val marketplaceSearches: List<MarketplaceSearchCard> = emptyList(),
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
        // Hydrate every state field that has a cache: instant first paint with no network.
        hydrateFromCache()
        // Decide whether to actually hit the network. refresh(force=false) gates
        // on WiFi vs cellular and on cache freshness.
        refresh(force = false)
    }

    /** Pull every available cache file into _state in one shot. */
    private fun hydrateFromCache() {
        com.vessences.android.util.BriefingCache.loadArticlesJson(appContext)?.let { json ->
            runCatching {
                val parsed = gson.fromJson(json, com.google.gson.JsonObject::class.java)
                val cardsArray = parsed.getAsJsonArray("articles")
                val categoriesArray = parsed.getAsJsonArray("categories")
                val articles: List<BriefingArticle> = if (cardsArray != null) {
                    gson.fromJson(cardsArray, object : TypeToken<List<BriefingArticle>>() {}.type)
                } else emptyList()
                val categories: List<String> = if (categoriesArray != null) {
                    gson.fromJson(categoriesArray, object : TypeToken<List<String>>() {}.type)
                } else emptyList()
                _state.value = _state.value.copy(
                    articles = articles,
                    categories = categories,
                    selectedCategory = "All",
                    lastUpdated = "cached",
                )
            }
        }
        com.vessences.android.util.BriefingCache.loadTopicsJson(appContext)?.let { json ->
            runCatching {
                val topics: List<BriefingTopic> = gson.fromJson(
                    json, object : TypeToken<List<BriefingTopic>>() {}.type,
                )
                _state.value = _state.value.copy(topics = topics)
            }
        }
        com.vessences.android.util.BriefingCache.loadMarketplaceJson(appContext)?.let { json ->
            runCatching {
                val cards: List<MarketplaceSearchCard> = gson.fromJson(
                    json, object : TypeToken<List<MarketplaceSearchCard>>() {}.type,
                )
                _state.value = _state.value.copy(marketplaceSearches = cards)
            }
        }
        com.vessences.android.util.BriefingCache.loadSavedArticlesJson(appContext)?.let { json ->
            runCatching {
                val ids: Set<String> = gson.fromJson(
                    json, object : TypeToken<Set<String>>() {}.type,
                )
                _state.value = _state.value.copy(savedArticleIds = ids)
            }
        }
        com.vessences.android.util.BriefingCache.loadSavedCategoriesJson(appContext)?.let { json ->
            runCatching {
                val cats: List<String> = gson.fromJson(
                    json, object : TypeToken<List<String>>() {}.type,
                )
                _state.value = _state.value.copy(savedCategories = cats)
            }
        }
        com.vessences.android.util.BriefingCache.loadArchiveDatesJson(appContext)?.let { json ->
            runCatching {
                val dates: List<String> = gson.fromJson(
                    json, object : TypeToken<List<String>>() {}.type,
                )
                _state.value = _state.value.copy(archiveDates = dates)
            }
        }
    }

    /**
     * Refresh policy:
     *   force=true              → always fetch (pull-to-refresh, post-action reload)
     *   online + stale + WiFi   → fetch + prefetch images
     *   online + stale + cell   → render cache; user must pull-to-refresh to spend data
     *   online + fresh-today    → render cache, no fetch
     *   no cache yet + online   → bootstrap fetch regardless of transport
     *   offline                 → render whatever cache exists; no fetch
     */
    fun refresh(force: Boolean = false) {
        if (_state.value.viewingArchiveDate != null) {
            loadArchive(_state.value.viewingArchiveDate!!)
            return
        }

        val online = com.vessences.android.util.BriefingCache.isOnline(appContext)
        val onWifi = com.vessences.android.util.BriefingCache.isOnWifi(appContext)
        val fresh = com.vessences.android.util.BriefingCache.isFreshForToday(appContext)
        val haveAnyCache = _state.value.articles.isNotEmpty()

        val shouldFetch = when {
            !online -> false
            force -> true
            !haveAnyCache -> true   // first-ever launch — bootstrap on whatever transport
            !fresh && onWifi -> true
            else -> false
        }

        if (shouldFetch) {
            doNetworkRefresh()
        }
    }

    private fun doNetworkRefresh() {
        refreshMarketplace()
        viewModelScope.launch { fetchArchiveDates() }
        viewModelScope.launch { fetchSavedArticleIds() }
        viewModelScope.launch { fetchSavedCategories() }
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            try {
                val previousIds = _state.value.articles.map { it.id }.toSet()

                val page = fetchArticles()
                val articles = page.articles
                val categories = page.categories
                val topics = fetchTopics()
                val timestamp = SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date())
                _state.value = _state.value.copy(
                    articles = articles,
                    topics = topics,
                    categories = categories,
                    selectedCategory = "All",
                    hasMoreArticles = page.hasMore,
                    isLoading = false,
                    lastUpdated = timestamp,
                )
                // Persist articles + topics for the day, then purge yesterday.
                writeArticlesCache(articles, categories)
                com.vessences.android.util.BriefingCache.saveTopicsJson(appContext, gson.toJson(topics))
                com.vessences.android.util.BriefingCache.stamp(appContext)
                com.vessences.android.util.BriefingCache.purgeOldDays(appContext)

                // WiFi: prefetch audio + images for new articles.
                if (com.vessences.android.util.BriefingCache.isOnWifi(appContext)) {
                    val newArticleIds = articles.map { it.id }.filter { it !in previousIds }
                    if (newArticleIds.isNotEmpty()) {
                        launch {
                            com.vessences.android.util.BriefingAudioCache.prefetchAll(
                                appContext,
                                newArticleIds,
                            )
                        }
                    }
                    // Prefetch every article image for today (cache survives across screen opens).
                    launch {
                        val items = articles.map { article ->
                            article.id to "$baseUrl/api/briefing/image/${article.id}"
                        }
                        com.vessences.android.util.BriefingCache.prefetchImages(appContext, items)
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

    private fun writeArticlesCache(articles: List<BriefingArticle>, categories: List<String>) {
        runCatching {
            val obj = com.google.gson.JsonObject().apply {
                add("articles", gson.toJsonTree(articles))
                add("categories", gson.toJsonTree(categories))
            }
            com.vessences.android.util.BriefingCache.saveArticlesJson(appContext, gson.toJson(obj))
        }
    }

    fun selectTab(tab: String) {
        _state.value = _state.value.copy(
            selectedTab = tab,
            viewingSaved = false,
            savedFilterCategory = null,
            viewingArchiveDate = if (tab == "Marketplace") null else _state.value.viewingArchiveDate,
        )
        if (tab == "Marketplace" && _state.value.marketplaceSearches.isEmpty() && !_state.value.isLoadingMarketplace) {
            refreshMarketplace()
        }
    }

    fun refreshMarketplace() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoadingMarketplace = true, marketplaceError = null)
            try {
                val searches = fetchMarketplaceSearchCards()
                _state.value = _state.value.copy(
                    marketplaceSearches = searches,
                    isLoadingMarketplace = false,
                )
                // Persist marketplace JSON into today's cache directory.
                runCatching {
                    com.vessences.android.util.BriefingCache.saveMarketplaceJson(
                        appContext, gson.toJson(searches),
                    )
                }
                // WiFi: prefetch every visible listing thumbnail.
                if (com.vessences.android.util.BriefingCache.isOnWifi(appContext)) {
                    launch {
                        val refs = mutableListOf<com.vessences.android.util.BriefingCache.MarketplaceImageRef>()
                        for (card in searches) {
                            for (listing in card.listings) {
                                val photoName = listing.thumb ?: listing.photos.firstOrNull() ?: continue
                                val querySlug = listing.querySlug ?: continue
                                val url = "$baseUrl/marketplace-image/${card.search.name}/$querySlug/${listing.id}/$photoName"
                                refs += com.vessences.android.util.BriefingCache.MarketplaceImageRef(
                                    searchName = card.search.name,
                                    querySlug = querySlug,
                                    listingId = listing.id,
                                    photoName = photoName,
                                    serverUrl = url,
                                )
                            }
                        }
                        if (refs.isNotEmpty()) {
                            com.vessences.android.util.BriefingCache.prefetchMarketplaceImages(
                                appContext, refs,
                            )
                        }
                    }
                }
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoadingMarketplace = false,
                    marketplaceError = e.message ?: "Failed to load marketplace",
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
                        runCatching {
                            com.vessences.android.util.BriefingCache.saveArchiveDatesJson(
                                appContext, gson.toJson(dates),
                            )
                        }
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
        val serverUrl = "$baseUrl/api/briefing/image/$articleId"
        // Return file:// URI when the image is in today's cache; Coil handles
        // both file URIs and http URLs transparently.
        return com.vessences.android.util.BriefingCache.resolveImageUrl(
            appContext, articleId, serverUrl,
        )
    }

    suspend fun getArticleDetail(article: BriefingArticle): BriefingArticle {
        if (!article.fullSummary.isNullOrBlank()) return article
        val detail = fetchArticleDetail(article.id)
        val merged = mergeArticleDetail(article, detail)
        cacheArticleDetail(merged)
        return merged
    }

    private suspend fun fetchArticleDetail(articleId: String): BriefingArticle = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$baseUrl/api/briefing/article/$articleId")
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw Exception("HTTP ${response.code}")
            val body = response.body?.string() ?: "{}"
            val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
            val status = parsed.get("status")?.takeIf { !it.isJsonNull }?.asString
            if (status == "error") {
                throw Exception(parsed.get("message")?.takeIf { !it.isJsonNull }?.asString ?: "Article not found")
            }
            gson.fromJson(parsed, BriefingArticle::class.java)
        }
    }

    private fun mergeArticleDetail(base: BriefingArticle, detail: BriefingArticle): BriefingArticle {
        return base.copy(
            title = detail.title.ifBlank { base.title },
            source = detail.source.ifBlank { base.source },
            url = detail.url.ifBlank { base.url },
            published = detail.published.ifBlank { base.published },
            topic = detail.topic.ifBlank { base.topic },
            imagePath = detail.imagePath?.takeIf { it.isNotBlank() } ?: base.imagePath,
            briefSummary = detail.briefSummary.ifBlank { base.briefSummary },
            fullSummary = detail.fullSummary?.takeIf { it.isNotBlank() } ?: base.fullSummary,
        )
    }

    private fun cacheArticleDetail(article: BriefingArticle) {
        val current = _state.value
        val hasLoadedArticle = current.articles.any { it.id == article.id }
        val updatedArticles = current.articles.map {
            if (it.id == article.id) mergeArticleDetail(it, article) else it
        }
        val updatedSavedArticles = current.savedArticles.map { saved ->
            val savedArticle = saved.article
            if (savedArticle?.id == article.id) {
                saved.copy(article = mergeArticleDetail(savedArticle, article))
            } else {
                saved
            }
        }
        _state.value = current.copy(
            articles = updatedArticles,
            savedArticles = updatedSavedArticles,
        )
        if (hasLoadedArticle) {
            writeArticlesCache(updatedArticles, current.categories)
        }
    }

    fun getMarketplaceImageUrl(searchName: String, listing: MarketplaceListing): String? {
        val photoName = listing.thumb ?: listing.photos.firstOrNull() ?: return null
        val querySlug = listing.querySlug ?: return null
        val serverUrl = "$baseUrl/marketplace-image/$searchName/$querySlug/${listing.id}/$photoName"
        return com.vessences.android.util.BriefingCache.resolveMarketplaceImageUrl(
            appContext, searchName, querySlug, listing.id, photoName, serverUrl,
        )
    }

    private var mediaPlayer: android.media.MediaPlayer? = null

    fun speakArticle(article: BriefingArticle, summaryType: String = "full") {
        viewModelScope.launch {
            _state.value = _state.value.copy(isSpeaking = true)
            // Pause always-listen during audio playback
            com.vessences.android.voice.WakeWordBridge.sttActive = true
            com.vessences.android.voice.AlwaysListeningService.stop(appContext)

            // Use device TTS directly — server-side audio generation removed
            val articleForSpeech = if (summaryType == "full") {
                runCatching { getArticleDetail(article) }.getOrDefault(article)
            } else {
                article
            }
            val summary = if (summaryType == "full") {
                articleForSpeech.fullSummary?.takeIf { it.isNotBlank() } ?: articleForSpeech.briefSummary
            } else {
                articleForSpeech.briefSummary
            }
            val text = "${articleForSpeech.title}. $summary"
            tts.speak(text)
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

    fun readAll(summaryType: String = "full") {
        readAllJob?.cancel()
        readAllJob = viewModelScope.launch {
            _state.value = _state.value.copy(readAllActive = true, isSpeaking = true)
            // Pause always-listen during read-all
            com.vessences.android.voice.WakeWordBridge.sttActive = true
            com.vessences.android.voice.AlwaysListeningService.stop(appContext)
            val articles = getFilteredArticles()
            for (article in articles) {
                if (!_state.value.readAllActive) break
                val articleForSpeech = if (summaryType == "full") {
                    runCatching { getArticleDetail(article) }.getOrDefault(article)
                } else {
                    article
                }
                val summary = if (summaryType == "full") {
                    articleForSpeech.fullSummary?.takeIf { it.isNotBlank() } ?: articleForSpeech.briefSummary
                } else {
                    articleForSpeech.briefSummary
                }
                val text = "${articleForSpeech.title}. $summary"
                tts.speak(text)
            }
            _state.value = _state.value.copy(readAllActive = false, isSpeaking = false)
        }
    }

    data class ArticlesPage(
        val articles: List<BriefingArticle>,
        val categories: List<String>,
        val hasMore: Boolean,
    )

    private suspend fun fetchArticles(
        limit: Int = PAGE_SIZE,
        offset: Int = 0,
    ): ArticlesPage = withContext(Dispatchers.IO) {
        val url = "$baseUrl/api/briefing/articles?limit=$limit&offset=$offset"
        val request = Request.Builder().url(url).build()
        val response = client.newCall(request).execute()
        if (!response.isSuccessful) throw Exception("HTTP ${response.code}")
        val body = response.body?.string() ?: "{}"
        val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
        val cardsArray = parsed.getAsJsonArray("cards")
            ?: return@withContext ArticlesPage(emptyList(), emptyList(), false)
        val articlesType = object : TypeToken<List<BriefingArticle>>() {}.type
        val articles: List<BriefingArticle> = gson.fromJson(cardsArray, articlesType)
        val categoriesArray = parsed.getAsJsonArray("categories")
        val categories: List<String> = if (categoriesArray != null) {
            val catType = object : TypeToken<List<String>>() {}.type
            gson.fromJson(categoriesArray, catType)
        } else emptyList()
        val hasMore = parsed.get("has_more")?.takeIf { !it.isJsonNull }?.asBoolean ?: false
        ArticlesPage(articles, categories, hasMore)
    }

    fun loadMoreArticles() {
        val s = _state.value
        if (s.isLoadingMore || !s.hasMoreArticles || s.viewingArchiveDate != null) return
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoadingMore = true)
            try {
                val page = fetchArticles(limit = PAGE_SIZE, offset = _state.value.articles.size)
                val existingIds = _state.value.articles.map { it.id }.toSet()
                val merged = _state.value.articles + page.articles.filter { it.id !in existingIds }
                _state.value = _state.value.copy(
                    articles = merged,
                    hasMoreArticles = page.hasMore,
                    isLoadingMore = false,
                )
            } catch (e: Exception) {
                android.util.Log.w("BriefingViewModel", "loadMoreArticles failed", e)
                _state.value = _state.value.copy(isLoadingMore = false)
            }
        }
    }

    companion object {
        private const val PAGE_SIZE = 50
    }

    private suspend fun fetchMarketplaceSearchCards(): List<MarketplaceSearchCard> = withContext(Dispatchers.IO) {
        val searchesRequest = Request.Builder()
            .url("$baseUrl/api/marketplace/searches")
            .build()
        val searchesResponse = client.newCall(searchesRequest).execute()
        if (!searchesResponse.isSuccessful) {
            throw Exception("HTTP ${searchesResponse.code}")
        }
        val searchesBody = searchesResponse.body?.string() ?: "{}"
        searchesResponse.close()
        val searchesParsed = gson.fromJson(searchesBody, com.google.gson.JsonObject::class.java)
        val searchesArray = searchesParsed.getAsJsonArray("searches")
            ?: return@withContext emptyList()
        val searchesType = object : TypeToken<List<MarketplaceSearch>>() {}.type
        val searches: List<MarketplaceSearch> = gson.fromJson(searchesArray, searchesType)

        searches.map { search ->
            val detail = runCatching { fetchMarketplaceDetail(search.name) }.getOrDefault(emptyList())
            val summary = runCatching { fetchMarketplaceSummary(search.name) }.getOrNull()
            val refreshStatus = runCatching { fetchMarketplaceStatus(search.name) }
                .getOrDefault(MarketplaceRefreshStatus())
            MarketplaceSearchCard(
                search = search,
                summary = summary,
                refreshStatus = refreshStatus,
                listings = detail,
            )
        }
    }

    private fun fetchMarketplaceDetail(searchName: String): List<MarketplaceListing> {
        val request = Request.Builder()
            .url("$baseUrl/api/marketplace/search/$searchName")
            .build()
        val response = client.newCall(request).execute()
        if (!response.isSuccessful) {
            response.close()
            throw Exception("Marketplace search $searchName returned HTTP ${response.code}")
        }
        val body = response.body?.string() ?: "{}"
        response.close()
        val parsed = gson.fromJson(body, com.google.gson.JsonObject::class.java)
        val listingsArray = parsed.getAsJsonArray("listings") ?: return emptyList()
        val listingsType = object : TypeToken<List<MarketplaceListing>>() {}.type
        return gson.fromJson(listingsArray, listingsType)
    }

    private fun fetchMarketplaceSummary(searchName: String): MarketplaceAiSummary? {
        val request = Request.Builder()
            .url("$baseUrl/api/marketplace/summary/$searchName")
            .build()
        val response = client.newCall(request).execute()
        if (!response.isSuccessful) {
            response.close()
            return null
        }
        val body = response.body?.string() ?: "{}"
        response.close()
        return gson.fromJson(body, MarketplaceAiSummary::class.java)
    }

    private fun fetchMarketplaceStatus(searchName: String): MarketplaceRefreshStatus {
        val request = Request.Builder()
            .url("$baseUrl/api/marketplace/refresh/$searchName")
            .build()
        val response = client.newCall(request).execute()
        if (!response.isSuccessful) {
            response.close()
            return MarketplaceRefreshStatus()
        }
        val body = response.body?.string() ?: "{}"
        response.close()
        return gson.fromJson(body, MarketplaceRefreshStatus::class.java)
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
        _state.value = _state.value.copy(viewingSaved = newVal, savedFilterCategory = null)
        if (newVal) loadSavedArticles(null)
    }

    fun openSavedCategory(category: String?) {
        _state.value = _state.value.copy(savedFilterCategory = category)
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
                        runCatching {
                            com.vessences.android.util.BriefingCache.saveSavedArticlesJson(
                                appContext, gson.toJson(ids),
                            )
                        }
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
                        runCatching {
                            com.vessences.android.util.BriefingCache.saveSavedCategoriesJson(
                                appContext, gson.toJson(merged),
                            )
                        }
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
