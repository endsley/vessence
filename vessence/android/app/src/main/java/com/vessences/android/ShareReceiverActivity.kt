package com.vessences.android

import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.core.app.NotificationCompat
import com.vessences.android.data.api.ApiClient
import com.vessences.android.util.Constants
import com.vessences.android.voice.AndroidTtsManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/**
 * Transparent activity that handles shared URLs with a picker dialog:
 *   - "Summarize Now" — kicks off server summarization in the background and
 *     dismisses immediately; a notification appears when the summary is ready.
 *   - "Add to Briefing" — queues for daily briefing (existing behavior).
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

        try {
            ApiClient.getOkHttpClient()
        } catch (_: UninitializedPropertyAccessException) {
            ApiClient.init(applicationContext)
        }

        AlertDialog.Builder(this)
            .setTitle("Share Article")
            .setItems(arrayOf("Summarize Now", "Summarize Now v2 (WebView)", "Add to Briefing")) { _, which ->
                when (which) {
                    0 -> summarizeNow(url)
                    1 -> summarizeNowV2(url)
                    2 -> addToBriefing(url)
                }
            }
            .setOnCancelListener { finish() }
            .show()
    }

    private fun extractUrl(text: String): String? {
        val urlPattern = Regex("""https?://\S+""")
        return urlPattern.find(text)?.value
    }

    private fun summarizeNowV2(url: String) {
        startActivity(Intent(this, ArticleReaderV2Activity::class.java).apply {
            putExtra(ArticleReaderV2Activity.EXTRA_URL, url)
        })
        finish()
    }

    /**
     * Fire-and-forget summarization: kick off the request on an app-scoped
     * coroutine, dismiss the share UI immediately, post a notification when
     * the summary returns (or if it fails).
     */
    private fun summarizeNow(url: String) {
        val appCtx = applicationContext
        val prefs = appCtx.getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        Toast.makeText(
            appCtx,
            "Summarizing in background — Jane will ping you when ready.",
            Toast.LENGTH_SHORT,
        ).show()

        // Launch on an app-scoped coroutine so the work survives this
        // activity being finished. SupervisorJob keeps siblings independent.
        ShareSummarizer.scope.launch {
            val result = try {
                withContext(Dispatchers.IO) {
                    val client = ApiClient.getOkHttpClient()
                    val body = JSONObject().apply { put("url", url) }
                        .toString()
                        .toRequestBody("application/json".toMediaType())
                    val request = Request.Builder()
                        .url("${serverUrl.trimEnd('/')}/api/briefing/articles/summarize_now")
                        .post(body)
                        .build()
                    client.newCall(request).execute().use { response ->
                        val responseBody = response.body?.string().orEmpty()
                        if (response.isSuccessful && responseBody.isNotEmpty()) {
                            val obj = JSONObject(responseBody)
                            val title = obj.optString("title", "")
                            val summary = obj.optString("summary", "")
                            if (summary.isNotEmpty()) {
                                val combined = if (title.isNotEmpty()) "$title. $summary" else summary
                                Pair(title.ifEmpty { "Article" }, combined)
                            } else null
                        } else null
                    }
                }
            } catch (_: Exception) {
                null
            }

            if (result != null) {
                ShareSummarizer.postSummaryReady(appCtx, url, result.first, result.second)
            } else {
                ShareSummarizer.postSummaryFailed(appCtx, url)
            }
        }

        finish()
    }

    private fun addToBriefing(url: String) {
        val appCtx = applicationContext
        val prefs = appCtx.getSharedPreferences(Constants.PREFS_NAME, MODE_PRIVATE)
        val serverUrl = prefs.getString(Constants.PREF_JANE_URL, Constants.DEFAULT_JANE_BASE_URL)
            ?: Constants.DEFAULT_JANE_BASE_URL

        val client = ApiClient.getOkHttpClient()
        val json = JSONObject().apply { put("url", url) }
        val body = json.toString().toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${serverUrl.trimEnd('/')}/api/briefing/articles/submit")
            .post(body)
            .build()

        Toast.makeText(appCtx, "Queuing article for briefing…", Toast.LENGTH_SHORT).show()

        ShareSummarizer.scope.launch {
            val success = try {
                withContext(Dispatchers.IO) {
                    client.newCall(request).execute().use { it.isSuccessful }
                }
            } catch (_: Exception) {
                false
            }
            withContext(Dispatchers.Main) {
                Toast.makeText(
                    appCtx,
                    if (success) "Article queued for briefing" else "Failed to queue article",
                    Toast.LENGTH_SHORT,
                ).show()
            }
        }

        finish()
    }
}

/**
 * App-scoped coroutine + notification helpers for share-to summarization.
 * Lives on the process, not on any activity, so work survives the share
 * activity being finished immediately after kickoff.
 */
object ShareSummarizer {

    val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private const val CHANNEL_ID = "jane_share_summary"
    private const val CHANNEL_NAME = "Article summaries"

    fun postSummaryReady(ctx: Context, url: String, title: String, summary: String) {
        ensureChannel(ctx)
        val appCtx = ctx.applicationContext
        // Tap-to-open a dedicated reader screen that shows the text and
        // auto-speaks it, with Stop/Close controls.
        val intent = Intent(appCtx, SummaryReaderActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(SummaryReaderActivity.EXTRA_TITLE, title)
            putExtra(SummaryReaderActivity.EXTRA_SUMMARY, summary)
            putExtra(SummaryReaderActivity.EXTRA_URL, url)
        }
        val pi = PendingIntent.getActivity(
            appCtx, url.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val contentText = summary.take(120).let { if (summary.length > 120) "$it…" else it }
        val notif = NotificationCompat.Builder(appCtx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .setContentTitle("Summary ready: $title")
            .setContentText(contentText)
            .setStyle(NotificationCompat.BigTextStyle().bigText(contentText))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .setContentIntent(pi)
            .build()
        val nm = appCtx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(300_000 + (url.hashCode() and 0xFFFF), notif)

        // Short spoken heads-up so the user hears something even if the
        // phone is in a pocket. Tapping the notification opens the reader
        // which auto-reads the full summary.
        speakHeadsUp(appCtx)
    }

    private fun speakHeadsUp(ctx: Context) {
        scope.launch {
            val audioMan = ctx.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
            val gotFocus = audioMan?.let { requestFocus(it) } ?: false
            try {
                getOrCreateTts(ctx).speak("Your article summary is ready.")
            } catch (e: Exception) {
                Log.w("ShareSummarizer", "heads-up TTS failed: ${e.message}")
            } finally {
                if (gotFocus) audioMan?.let { releaseFocus(it) }
            }
        }
    }

    @Volatile private var tts: AndroidTtsManager? = null
    @Volatile private var focusRequest: AudioFocusRequest? = null

    private fun getOrCreateTts(ctx: Context): AndroidTtsManager {
        tts?.let { return it }
        synchronized(this) {
            tts?.let { return it }
            val created = AndroidTtsManager(ctx.applicationContext)
            tts = created
            return created
        }
    }

    private fun buildFocusRequest(): AudioFocusRequest? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return null
        focusRequest?.let { return it }
        synchronized(this) {
            focusRequest?.let { return it }
            val built = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .build()
            focusRequest = built
            return built
        }
    }

    private suspend fun requestFocus(audioMan: AudioManager): Boolean {
        return withContext(Dispatchers.Main.immediate) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val req = buildFocusRequest() ?: return@withContext false
                audioMan.requestAudioFocus(req) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            } else {
                @Suppress("DEPRECATION")
                audioMan.requestAudioFocus(
                    null,
                    AudioManager.STREAM_MUSIC,
                    AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK,
                ) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            }
        }
    }

    private suspend fun releaseFocus(audioMan: AudioManager) {
        withContext(Dispatchers.Main.immediate) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                buildFocusRequest()?.let { audioMan.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                audioMan.abandonAudioFocus(null)
            }
        }
    }

    fun postSummaryFailed(ctx: Context, url: String) {
        ensureChannel(ctx)
        val notif = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentTitle("Could not summarize article")
            .setContentText(url.take(80))
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setAutoCancel(true)
            .build()
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(300_100 + (url.hashCode() and 0xFFFF), notif)
    }

    private fun ensureChannel(ctx: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Notifications when a shared article's summary is ready"
        }
        nm.createNotificationChannel(channel)
    }
}
