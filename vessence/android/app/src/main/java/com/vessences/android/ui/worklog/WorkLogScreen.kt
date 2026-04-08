package com.vessences.android.ui.worklog

import android.annotation.SuppressLint
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.vessences.android.data.api.ApiClient
import com.vessences.android.util.CookieStore
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

private val SlateBg = Color(0xFF0F172A)

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun WorkLogScreen(
    onBack: (() -> Unit)? = null,
) {
    val context = LocalContext.current
    val baseUrl = remember { ApiClient.getJaneBaseUrl() }
    val workLogUrl = "$baseUrl/worklog"

    // Sync OkHttp cookies to WebView CookieManager
    val cookieStore = remember { ApiClient.getCookieStore() }
    remember(workLogUrl) {
        syncCookiesToWebView(cookieStore, baseUrl)
        true
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg),
    ) {
        if (onBack != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        "Back",
                        tint = Color.White,
                    )
                }
                Text(
                    "Work Log",
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                WebView(ctx).apply {
                    layoutParams = ViewGroup.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT,
                    )
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.mediaPlaybackRequiresUserGesture = false
                    setBackgroundColor(0xFF0F172A.toInt())
                    webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(
                            view: WebView?,
                            request: WebResourceRequest?,
                        ): Boolean {
                            val url = request?.url?.toString() ?: return true
                            // Only allow navigation within the configured base URL
                            return !url.startsWith(baseUrl)
                        }
                    }
                    // Load with cookie header in case WebView cookie sync missed
                    val headers = mutableMapOf<String, String>()
                    try {
                        val url = baseUrl.toHttpUrlOrNull()
                        if (url != null) {
                            val cookies = cookieStore.loadForRequest(url)
                            val cookieHeader = cookies.joinToString("; ") { "${it.name}=${it.value}" }
                            if (cookieHeader.isNotEmpty()) {
                                headers["Cookie"] = cookieHeader
                            }
                        }
                    } catch (_: Exception) {}
                    loadUrl(workLogUrl, headers)
                }
            },
        )
    }
}

private fun syncCookiesToWebView(cookieStore: CookieStore, baseUrl: String) {
    try {
        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        // Sync cookies for both vault and jane base URLs
        for (url in listOf(ApiClient.getVaultBaseUrl(), ApiClient.getJaneBaseUrl(), baseUrl)) {
            val httpUrl = url.toHttpUrlOrNull() ?: continue
            val cookies = cookieStore.loadForRequest(httpUrl)
            for (cookie in cookies) {
                cookieManager.setCookie(url, cookie.toString())
            }
        }
        cookieManager.flush()
    } catch (_: Exception) {
        // Non-fatal
    }
}
