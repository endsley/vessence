package com.vessences.android

import android.app.AlertDialog
import android.app.ProgressDialog
import android.content.Intent
import android.os.Bundle
import android.speech.tts.TextToSpeech
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
import java.util.Locale

/**
 * Transparent activity that handles shared URLs with a picker dialog:
 *   - "Summarize Now" — fetches & summarizes via server, speaks result via device TTS
 *   - "Add to Briefing" — queues for daily briefing (existing behavior)
 *
 * If the shared text is not a URL, forwards the intent to MainActivity.
 */
class ShareReceiverActivity : ComponentActivity(), TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var pendingSpeech: String? = null

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

        // Initialize TTS engine early so it's ready when we need it
        tts = TextToSpeech(this, this)

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

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.US
            // Speak any text that arrived before TTS was ready
            pendingSpeech?.let { text ->
                pendingSpeech = null
                speakAndFinish(text)
            }
        }
    }

    private fun speakAndFinish(text: String) {
        val engine = tts
        if (engine == null) {
            pendingSpeech = text
            return
        }
        engine.setOnUtteranceProgressListener(object : android.speech.tts.UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) { finish() }
            override fun onError(utteranceId: String?) { finish() }
        })
        engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "summarize_now")
    }

    private fun extractUrl(text: String): String? {
        val urlPattern = Regex("""https?://\S+""")
        return urlPattern.find(text)?.value
    }

    /**
     * Call the server's summarize_now endpoint, get back summary text,
     * and speak it immediately via device TTS.
     */
    @Suppress("DEPRECATION")
    private fun summarizeNow(url: String) {
        val prefs = getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        val progress = ProgressDialog(this).apply {
            setMessage("Summarizing article…")
            setCancelable(false)
            show()
        }

        val client = ApiClient.getOkHttpClient()
        val json = JSONObject().apply { put("url", url) }
        val body = json.toString().toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${serverUrl.trimEnd('/')}/api/briefing/articles/summarize_now")
            .post(body)
            .build()

        lifecycleScope.launch {
            val result = try {
                withContext(Dispatchers.IO) {
                    val response = client.newCall(request).execute()
                    val responseBody = response.body?.string() ?: ""
                    response.close()
                    if (response.isSuccessful && responseBody.isNotEmpty()) {
                        val obj = JSONObject(responseBody)
                        val title = obj.optString("title", "")
                        val summary = obj.optString("summary", "")
                        if (summary.isNotEmpty()) {
                            if (title.isNotEmpty()) "$title. $summary" else summary
                        } else null
                    } else null
                }
            } catch (_: Exception) {
                null
            }

            progress.dismiss()

            if (result != null) {
                // Hand off to MainActivity: bring app to focus, post the summary
                // into chat, and trigger main TTS path. Do NOT speak from this
                // share activity — keep all TTS routed through the main app so
                // the user can stop, replay, or interact with it normally.
                val mainIntent = Intent(this@ShareReceiverActivity, MainActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                    putExtra("shared_summary_text", result)
                    putExtra("shared_summary_url", url)
                    putExtra("shared_summary_speak", true)
                }
                startActivity(mainIntent)
                finish()
            } else {
                Toast.makeText(this@ShareReceiverActivity, "Could not summarize article", Toast.LENGTH_SHORT).show()
                finish()
            }
        }
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

    override fun onDestroy() {
        tts?.stop()
        tts?.shutdown()
        super.onDestroy()
    }
}
