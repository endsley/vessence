package com.vessences.android

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.vessences.android.data.api.ApiClient
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

class ReportReaderActivity : Activity() {
    companion object {
        const val EXTRA_URL = "report_reader_url"
        const val EXTRA_TITLE = "report_reader_title"
        const val EXTRA_REPORT_ID = "report_reader_id"
    }

    private lateinit var webView: WebView
    private lateinit var status: TextView
    private var reportUrl = ""

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
            ApiClient.getOkHttpClient()
        } catch (_: UninitializedPropertyAccessException) {
            ApiClient.init(applicationContext)
        }

        reportUrl = intent.getStringExtra(EXTRA_URL).orEmpty()
        if (reportUrl.isBlank()) {
            Toast.makeText(this, "No report URL found.", Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        val title = intent.getStringExtra(EXTRA_TITLE).orEmpty().ifBlank { "Research Report" }

        syncCookiesToWebView(reportUrl)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(0xFFF6F8FB.toInt())
        }
        val toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(12, 20, 12, 10)
            setBackgroundColor(0xFF0F172A.toInt())
        }
        val close = Button(this).apply {
            text = "Close"
            setOnClickListener { finish() }
        }
        val titleView = TextView(this).apply {
            text = title
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 18f
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
            setPadding(12, 0, 12, 0)
        }
        val reload = Button(this).apply {
            text = "Reload"
            setOnClickListener {
                status.visibility = View.VISIBLE
                status.text = "Reloading report..."
                webView.loadUrl(reportUrl, cookieHeaders(reportUrl))
            }
        }
        toolbar.addView(close, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        toolbar.addView(titleView, LinearLayout.LayoutParams(
            0,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            1f,
        ))
        toolbar.addView(reload, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))

        status = TextView(this).apply {
            text = "Loading report..."
            setTextColor(0xFF334155.toInt())
            textSize = 14f
            setPadding(16, 10, 16, 10)
            setBackgroundColor(0xFFEFF6FF.toInt())
        }
        webView = WebView(this).apply {
            settings.javaScriptEnabled = false
            settings.domStorageEnabled = false
            settings.loadsImagesAutomatically = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            setBackgroundColor(0xFFF6F8FB.toInt())
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    status.visibility = View.GONE
                }

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError,
                ) {
                    if (request.isForMainFrame) {
                        status.visibility = View.VISIBLE
                        status.text = "Could not load the report. Open Vessence and sign in, then try again."
                    }
                }

                override fun onReceivedHttpError(
                    view: WebView,
                    request: WebResourceRequest,
                    errorResponse: WebResourceResponse,
                ) {
                    if (request.isForMainFrame && errorResponse.statusCode in 400..599) {
                        status.visibility = View.VISIBLE
                        status.text = "Report access failed (${errorResponse.statusCode}). Open Vessence and sign in, then try again."
                    }
                }
            }
        }

        root.addView(toolbar, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        root.addView(status, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        root.addView(webView, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1f,
        ))
        setContentView(root)

        webView.loadUrl(reportUrl, cookieHeaders(reportUrl))
    }

    override fun onDestroy() {
        super.onDestroy()
        if (::webView.isInitialized) {
            webView.destroy()
        }
    }

    private fun syncCookiesToWebView(url: String) {
        try {
            val cookieManager = CookieManager.getInstance()
            cookieManager.setAcceptCookie(true)
            val cookieStore = ApiClient.getCookieStore()
            for (baseUrl in listOf(ApiClient.getVaultBaseUrl(), ApiClient.getJaneBaseUrl(), url)) {
                val parsed = baseUrl.toHttpUrlOrNull() ?: continue
                val origin = "${parsed.scheme}://${parsed.host}"
                for (cookie in cookieStore.loadForRequest(parsed)) {
                    cookieManager.setCookie(origin, cookie.toString())
                }
            }
            cookieManager.flush()
        } catch (_: Exception) {
        }
    }

    private fun cookieHeaders(url: String): Map<String, String> {
        return try {
            val parsed = url.toHttpUrlOrNull() ?: return emptyMap()
            val cookies = ApiClient.getCookieStore().loadForRequest(parsed)
            val cookieHeader = cookies.joinToString("; ") { "${it.name}=${it.value}" }
            if (cookieHeader.isBlank()) emptyMap() else mapOf("Cookie" to cookieHeader)
        } catch (_: Exception) {
            emptyMap()
        }
    }
}
