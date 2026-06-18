package com.vessences.android

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.text.method.ScrollingMovementMethod
import android.view.Gravity
import android.view.ViewGroup
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.vessences.android.data.api.ApiClient
import com.vessences.android.util.Constants
import com.vessences.android.voice.HybridTtsManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

class ArticleReaderV2Activity : Activity() {

    companion object {
        const val EXTRA_URL = "article_reader_v2_url"
        const val EXTRA_MODE = "article_reader_v2_mode"
        const val MODE_SUMMARIZE = "summarize"
        const val MODE_BRIEFING = "briefing"
        private const val MAX_ARTICLE_CHARS = 40_000
        private const val TTS_CHUNK_CHARS = 2_800
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private lateinit var tts: HybridTtsManager
    private lateinit var status: TextView
    private lateinit var preview: TextView
    private lateinit var webView: WebView
    private var extracted = false
    private var extractionInProgress = false
    private var mode = MODE_SUMMARIZE
    private var articleUrl = ""

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        tts = HybridTtsManager(applicationContext)
        mode = intent.getStringExtra(EXTRA_MODE) ?: MODE_SUMMARIZE

        try {
            ApiClient.getOkHttpClient()
        } catch (_: UninitializedPropertyAccessException) {
            ApiClient.init(applicationContext)
        }

        val url = intent.getStringExtra(EXTRA_URL)
        if (url.isNullOrBlank()) {
            Toast.makeText(this, "No article URL found.", Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        articleUrl = url

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(28, 36, 28, 24)
            setBackgroundColor(0xFF0F172A.toInt())
        }
        status = TextView(this).apply {
            text = "Loading article locally..."
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 18f
        }
        preview = TextView(this).apply {
            text = "Complete any proof or login if the site asks, then tap Extract."
            setTextColor(0xFFCBD5E1.toInt())
            textSize = 14f
            setPadding(0, 18, 0, 18)
            movementMethod = ScrollingMovementMethod()
            isVerticalScrollBarEnabled = true
        }
        val extract = Button(this).apply {
            text = "Extract"
            setOnClickListener {
                status.text = "Extracting readable text..."
                extractAndSpeak(webView)
            }
        }
        val stop = Button(this).apply {
            text = "Stop and close"
            setOnClickListener {
                tts.stop()
                finish()
            }
        }
        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.loadsImagesAutomatically = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.userAgentString = settings.userAgentString.replace("; wv", "")
        }
        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            addView(extract, LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1f,
            ))
            addView(stop, LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1f,
            ))
        }

        root.addView(status, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        root.addView(preview, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        root.addView(webView, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1f,
        ))
        root.addView(actions, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        setContentView(root)

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, loadedUrl: String) {
                if (extracted) return
                status.text = "Article loaded. Extracting readable text..."
                scope.launch {
                    delay(1_500)
                    if (!extracted) extractAndSpeak(view, automatic = true)
                }
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                if (request.isForMainFrame) {
                    status.text = "Could not load this article in WebView."
                }
            }
        }
        webView.loadUrl(url)
    }

    private fun extractAndSpeak(view: WebView, automatic: Boolean = false) {
        if (extracted || extractionInProgress) return
        extractionInProgress = true
        val readabilityJs = readAsset("Readability.js")
        if (readabilityJs.isBlank()) {
            status.text = "Error: Readability.js asset not found."
            extractionInProgress = false
            return
        }

        val scriptToEvaluate = "$readabilityJs\n${articleExtractionJs()}"

        view.evaluateJavascript(scriptToEvaluate) { encoded ->
            val parsed = parseJsString(encoded)
            val obj = runCatching { JSONObject(parsed) }.getOrNull()
            val title = obj?.optString("title").orEmpty().trim()
            val raw = obj?.optString("textContent").orEmpty()
            val cleaned = cleanArticleText(title, raw)
            if (cleaned.length < 150) {
                status.text = if (automatic) {
                    "Waiting for article text..."
                } else {
                    "I could not extract enough article text from this page."
                }
                preview.text = "Complete any proof or login if the site asks, wait for the article text to appear, then tap Extract."
                extractionInProgress = false
                return@evaluateJavascript
            }

            extracted = true
            extractionInProgress = false
            when (mode) {
                MODE_BRIEFING -> submitToBriefing(title, cleaned)
                else -> summarizeViaServer(title, cleaned)
            }
        }
    }

    private fun summarizeViaServer(title: String, text: String) {
        status.text = "Sending to Jane for summarization..."
        preview.text = text.take(3_000)

        val prefs = applicationContext.getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        scope.launch {
            val result = try {
                withContext(Dispatchers.IO) {
                    val client = ApiClient.getOkHttpClient()
                    val body = JSONObject().apply {
                        put("title", title)
                        put("text", text)
                        put("url", articleUrl)
                    }.toString().toRequestBody("application/json".toMediaType())
                    val request = Request.Builder()
                        .url("${serverUrl.trimEnd('/')}/api/briefing/articles/summarize_text")
                        .post(body)
                        .build()
                    client.newCall(request).execute().use { response ->
                        val responseBody = response.body?.string().orEmpty()
                        if (response.isSuccessful && responseBody.isNotEmpty()) {
                            val obj = JSONObject(responseBody)
                            val summaryTitle = obj.optString("title", title)
                            val summary = obj.optString("summary", "")
                            if (summary.isNotEmpty()) Pair(summaryTitle, summary) else null
                        } else null
                    }
                }
            } catch (_: Exception) {
                null
            }

            if (result != null) {
                startActivity(Intent(this@ArticleReaderV2Activity, SummaryReaderActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    putExtra(SummaryReaderActivity.EXTRA_TITLE, result.first)
                    putExtra(SummaryReaderActivity.EXTRA_SUMMARY, result.second)
                    putExtra(SummaryReaderActivity.EXTRA_URL, articleUrl)
                })
                finish()
            } else {
                status.text = "Server unavailable — reading raw article instead..."
                scope.launch {
                    for (chunk in splitForTts(text)) {
                        tts.speak(chunk)
                    }
                    status.text = "Finished reading."
                }
            }
        }
    }

    private fun submitToBriefing(title: String, text: String) {
        status.text = "Submitting to daily briefing..."

        val prefs = applicationContext.getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        scope.launch {
            val success = try {
                withContext(Dispatchers.IO) {
                    val client = ApiClient.getOkHttpClient()
                    val body = JSONObject().apply {
                        put("url", articleUrl)
                        put("title", title)
                        put("text", text)
                    }.toString().toRequestBody("application/json".toMediaType())
                    val request = Request.Builder()
                        .url("${serverUrl.trimEnd('/')}/api/briefing/articles/submit")
                        .post(body)
                        .build()
                    client.newCall(request).execute().use { it.isSuccessful }
                }
            } catch (_: Exception) {
                false
            }

            Toast.makeText(
                applicationContext,
                if (success) "Article queued for briefing" else "Failed to queue article",
                Toast.LENGTH_SHORT,
            ).show()
            finish()
        }
    }

    private fun readAsset(filename: String): String {
        return try {
            assets.open(filename).bufferedReader().use { it.readText() }
        } catch (e: Exception) {
            ""
        }
    }

    private fun parseJsString(encoded: String?): String {
        if (encoded.isNullOrBlank() || encoded == "null") return "{}"
        return runCatching { JSONArray("[$encoded]").getString(0) }.getOrElse { "{}" }
    }

    private fun cleanArticleText(title: String, raw: String): String {
        val body = raw
            .replace('\u00A0', ' ')
            .replace(Regex("[ \\t]+"), " ")
            .lines()
            .map { it.trim() }
            .filter { it.isNotBlank() }
            .joinToString("\n\n")
            .replace(Regex("\n{3,}"), "\n\n")
            .take(MAX_ARTICLE_CHARS)
            .trim()
        return listOf(title.takeIf { it.isNotBlank() }, body)
            .filterNotNull()
            .joinToString("\n\n")
            .trim()
    }

    private fun splitForTts(text: String): List<String> {
        val chunks = mutableListOf<String>()
        val paragraphs = text.split(Regex("\n{2,}"))
        var current = StringBuilder()
        fun flush() {
            val s = current.toString().trim()
            if (s.isNotBlank()) chunks += s
            current = StringBuilder()
        }
        for (p in paragraphs) {
            if (p.length > TTS_CHUNK_CHARS) {
                flush()
                p.chunked(TTS_CHUNK_CHARS).forEach { chunks += it.trim() }
            } else if (current.length + p.length + 2 > TTS_CHUNK_CHARS) {
                flush()
                current.append(p)
            } else {
                if (current.isNotEmpty()) current.append("\n\n")
                current.append(p)
            }
        }
        flush()
        return chunks
    }

    private fun articleExtractionJs(): String = """
        (() => {
            var article = new Readability(document).parse();
            return JSON.stringify(article);
        })();
    """.trimIndent()

    override fun onDestroy() {
        super.onDestroy()
        webView.stopLoading()
        webView.destroy()
        tts.stop()
        tts.shutdown()
        scope.cancel()
    }
}
