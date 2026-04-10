package com.vessences.android

import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import com.vessences.android.data.api.ApiClient
import com.vessences.android.util.Constants
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/**
 * Transparent activity that handles shared URLs with a picker dialog:
 *   - "Summarize Now" — sends URL to Jane chat, gets immediate summary via TTS
 *   - "Add to Briefing" — queues for daily briefing (existing behavior)
 *
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

        // Initialize ApiClient if needed
        try {
            ApiClient.getOkHttpClient()
        } catch (_: UninitializedPropertyAccessException) {
            ApiClient.init(applicationContext)
        }

        // Show picker dialog
        AlertDialog.Builder(this)
            .setTitle("Share Article")
            .setItems(arrayOf("Summarize Now", "Add to Briefing")) { _, which ->
                when (which) {
                    0 -> summarizeNow(url)
                    1 -> addToBriefing(url)
                }
            }
            .setOnCancelListener { finish() }
            .show()
    }

    private fun extractUrl(text: String): String? {
        val urlPattern = Regex("""https?://\S+""")
        return urlPattern.find(text)?.value
    }

    /**
     * Send the URL to Jane's chat as a message. Jane will fetch, summarize,
     * and the response gets spoken via TTS on the chat screen.
     */
    private fun summarizeNow(url: String) {
        // Open the main chat with the URL as a pre-filled message
        val chatIntent = Intent(this, MainActivity::class.java).apply {
            action = Intent.ACTION_SEND
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, "Summarize this article for me: $url")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        startActivity(chatIntent)
        Toast.makeText(this, "Sending to Jane for summary...", Toast.LENGTH_SHORT).show()
        finish()
    }

    /**
     * Queue the URL for the daily briefing (existing behavior).
     */
    private fun addToBriefing(url: String) {
        val prefs = getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        val client = ApiClient.getOkHttpClient()
        val json = JSONObject().apply { put("url", url) }
        val body = json.toString().toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${serverUrl.trimEnd('/')}/api/briefing/articles/submit")
            .post(body)
            .build()

        lifecycleScope.launch {
            val success = try {
                withContext(Dispatchers.IO) {
                    val response = client.newCall(request).execute()
                    val ok = response.isSuccessful
                    response.close()
                    ok
                }
            } catch (_: Exception) {
                false
            }

            Toast.makeText(
                this@ShareReceiverActivity,
                if (success) "Article queued for briefing" else "Failed to queue article",
                Toast.LENGTH_SHORT
            ).show()

            finish()
        }
    }
}
