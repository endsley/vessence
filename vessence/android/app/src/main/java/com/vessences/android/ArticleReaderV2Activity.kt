package com.vessences.android

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
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
import com.vessences.android.voice.HybridTtsManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

/**
 * Summarize Now v2: local Android WebView article reader.
 *
 * This intentionally does not call or modify the existing server-side
 * ShareReceiverActivity.summarizeNow() v1 path. It loads the shared URL on
 * the phone, extracts rendered page text with JavaScript, cleans it locally,
 * and sends that text straight to Android TTS.
 */
class ArticleReaderV2Activity : Activity() {

    companion object {
        const val EXTRA_URL = "article_reader_v2_url"
        private const val MAX_ARTICLE_CHARS = 40_000
        private const val TTS_CHUNK_CHARS = 2_800
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private lateinit var tts: HybridTtsManager
    private lateinit var status: TextView
    private lateinit var preview: TextView
    private lateinit var webView: WebView
    private var extracted = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        tts = HybridTtsManager(applicationContext)

        val url = intent.getStringExtra(EXTRA_URL)
        if (url.isNullOrBlank()) {
            Toast.makeText(this, "No article URL found.", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

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
            text = url
            setTextColor(0xFFCBD5E1.toInt())
            textSize = 14f
            setPadding(0, 18, 0, 18)
        }
        val stop = Button(this).apply {
            text = "Stop and close"
            setOnClickListener {
                tts.stop()
                finish()
            }
        }
        webView = WebView(this).apply {
            layoutParams = LinearLayout.LayoutParams(1, 1)
            visibility = android.view.View.INVISIBLE
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.loadsImagesAutomatically = false
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.userAgentString = settings.userAgentString.replace("; wv", "")
        }

        root.addView(status, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        root.addView(preview, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1f,
        ))
        root.addView(stop, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        root.addView(webView)
        setContentView(root)

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, loadedUrl: String) {
                if (extracted) return
                extracted = true
                status.text = "Extracting readable text..."
                scope.launch {
                    delay(1_500)
                    extractAndSpeak(view)
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

    private fun extractAndSpeak(view: WebView) {
        view.evaluateJavascript(articleExtractionJs()) { encoded ->
            val parsed = parseJsString(encoded)
            val obj = runCatching { JSONObject(parsed) }.getOrNull()
            val title = obj?.optString("title").orEmpty().trim()
            val raw = obj?.optString("text").orEmpty()
            val cleaned = cleanArticleText(title, raw)
            if (cleaned.length < 300) {
                status.text = "I could not extract enough article text from this page."
                preview.text = "This page may require login, block WebView, or render text in a way Android cannot read."
                return@evaluateJavascript
            }

            status.text = "Reading article..."
            preview.text = cleaned.take(3_000)
            scope.launch {
                for (chunk in splitForTts(cleaned)) {
                    tts.speak(chunk)
                }
                status.text = "Finished reading."
            }
        }
    }

    private fun parseJsString(encoded: String?): String {
        if (encoded.isNullOrBlank() || encoded == "null") return "{}"
        return runCatching { JSONArray("[$encoded]").getString(0) }.getOrElse { "{}" }
    }

    private fun cleanArticleText(title: String, raw: String): String {
        val junk = listOf(
            "advertisement", "subscribe", "sign in", "sign up", "cookie",
            "privacy policy", "terms of service", "all rights reserved",
            "share this article", "follow us", "enable javascript",
        )
        val lines = raw
            .replace('\u00A0', ' ')
            .replace(Regex("[ \\t]+"), " ")
            .lines()
            .map { it.trim() }
            .filter { it.length >= 20 }
            .filter { line -> junk.none { line.contains(it, ignoreCase = true) } }

        val collapsed = mutableListOf<String>()
        for (line in lines) {
            if (collapsed.lastOrNull() != line) collapsed += line
        }

        val body = collapsed.joinToString("\n\n")
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
          const bad = 'script,style,noscript,nav,footer,header,aside,form,button,svg,canvas,iframe';
          document.querySelectorAll(bad).forEach(el => el.remove());
          const candidates = [
            document.querySelector('article'),
            document.querySelector('main'),
            document.querySelector('[role="main"]'),
            document.querySelector('[itemprop="articleBody"]'),
            document.body
          ].filter(Boolean);
          let best = candidates[0] || document.body;
          for (const el of candidates) {
            if ((el.innerText || '').length > (best.innerText || '').length) best = el;
          }
          return JSON.stringify({
            title: document.title || '',
            text: (best && best.innerText) || document.body.innerText || ''
          });
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
