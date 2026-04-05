package com.vessences.android

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import com.vessences.android.data.api.ApiClient
import com.vessences.android.util.Constants
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/**
 * Transparent activity that silently handles shared URLs.
 * POSTs the URL to the briefing article submission endpoint and shows a toast.
 * If the shared text is not a URL, forwards the intent to MainActivity.
 */
class ShareReceiverActivity : ComponentActivity() {

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

        // Extract URL from shared text (Chrome often shares "Title\nURL")
        val url = extractUrl(sharedText)

        if (url == null) {
            // Not a URL — forward to MainActivity for normal share handling
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

        // Initialize ApiClient if needed (it may not be initialized if app wasn't running)
        try {
            ApiClient.getOkHttpClient()
        } catch (_: UninitializedPropertyAccessException) {
            ApiClient.init(applicationContext)
        }

        val prefs = getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        submitArticle(serverUrl, url)
    }

    private fun extractUrl(text: String): String? {
        // Look for an http:// or https:// URL anywhere in the text
        val urlPattern = Regex("""https?://\S+""")
        return urlPattern.find(text)?.value
    }

    private fun submitArticle(serverUrl: String, url: String) {
        val client = ApiClient.getOkHttpClient()
        val json = JSONObject().apply { put("url", url) }
        val body = json.toString().toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${serverUrl.trimEnd('/')}/api/briefing/articles/submit")
            .post(body)
            .header("User-Agent", Constants.USER_AGENT)
            .build()

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = client.newCall(request).execute()
                val success = response.isSuccessful
                response.close()
                runOnUiThread {
                    Toast.makeText(
                        this@ShareReceiverActivity,
                        if (success) "Article queued for briefing" else "Failed to queue article",
                        Toast.LENGTH_SHORT
                    ).show()
                }
            } catch (_: Exception) {
                runOnUiThread {
                    Toast.makeText(
                        this@ShareReceiverActivity,
                        "Failed to queue article",
                        Toast.LENGTH_SHORT
                    ).show()
                }
            }
        }

        // Finish immediately — the toast will persist after the activity is gone
        finish()
    }
}
