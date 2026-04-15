package com.vessences.android

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import com.vessences.android.data.api.ApiClient
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Sends diagnostic data to the server for debugging wake word, mic, TTS, etc.
 *
 * Categories:
 *   - wakeword: model load, detection scores, trigger events
 *   - mic: permission state, AudioRecord init, contention
 *   - tts: speech events, errors
 *   - service: lifecycle events (start/stop/crash)
 *   - error: non-fatal errors
 *   - chat_error: streaming chat exceptions (SocketException, etc.)
 *
 * All sends are fire-and-forget on a background thread. If the POST fails
 * (e.g., during the same network outage that triggered the report), the
 * payload is persisted to SharedPreferences as a bounded ring. Every
 * successful POST first drains that pending queue, so network-outage
 * reports actually land once connectivity resumes.
 */
object DiagnosticReporter {
    private const val TAG = "Diagnostics"
    private const val PREFS = "diagnostic_reporter"
    private const val PENDING_KEY = "pending_queue"
    private const val MAX_PENDING = 50
    private var appVersion: String = "unknown"
    private var versionCode: Long = -1
    @Volatile private var prefs: SharedPreferences? = null

    fun init(context: Context) {
        try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            appVersion = pInfo.versionName ?: "unknown"
            versionCode = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
                pInfo.longVersionCode
            } else {
                @Suppress("DEPRECATION")
                pInfo.versionCode.toLong()
            }
        } catch (_: Exception) {}
        try {
            prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        } catch (_: Exception) {}
    }

    private fun loadPending(): MutableList<String> {
        val p = prefs ?: return mutableListOf()
        val raw = p.getString(PENDING_KEY, null) ?: return mutableListOf()
        return try {
            val arr = JSONArray(raw)
            MutableList(arr.length()) { arr.getString(it) }
        } catch (_: Exception) {
            mutableListOf()
        }
    }

    private fun savePending(list: List<String>) {
        val p = prefs ?: return
        try {
            val arr = JSONArray()
            for (s in list) arr.put(s)
            p.edit().putString(PENDING_KEY, arr.toString()).apply()
        } catch (_: Exception) {}
    }

    @Synchronized
    private fun enqueue(payload: String) {
        val pending = loadPending()
        pending.add(payload)
        // Keep only the newest MAX_PENDING — drop oldest first.
        val trimmed = if (pending.size > MAX_PENDING)
            pending.takeLast(MAX_PENDING).toMutableList() else pending
        savePending(trimmed)
    }

    @Synchronized
    private fun drainPending(): List<String> {
        val pending = loadPending()
        if (pending.isEmpty()) return emptyList()
        savePending(emptyList())
        return pending
    }

    /** POST a single diagnostic payload. Returns true on 2xx. */
    private fun postOne(payload: String): Boolean {
        return try {
            val body = okhttp3.RequestBody.create(
                "application/json".toMediaTypeOrNull(),
                payload
            )
            val request = okhttp3.Request.Builder()
                .url("${ApiClient.getJaneBaseUrl().trimEnd('/')}/api/device-diagnostics")
                .post(body)
                .build()
            ApiClient.getOkHttpClient().newCall(request).execute().use { resp ->
                resp.isSuccessful
            }
        } catch (_: Exception) {
            false
        }
    }

    fun report(category: String, message: String, data: Map<String, Any?> = emptyMap()) {
        Thread {
            val payload = JSONObject().apply {
                put("timestamp", SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).format(Date()))
                put("category", category)
                put("message", message)
                put("app_version", appVersion)
                put("version_code", versionCode)
                for ((k, v) in data) {
                    put(k, v)
                }
            }.toString()

            // Try to POST this new event first. If it succeeds, also flush
            // any previously-buffered events. If it fails, buffer this one.
            if (postOne(payload)) {
                val backlog = drainPending()
                if (backlog.isNotEmpty()) {
                    var requeued: MutableList<String>? = null
                    for ((i, old) in backlog.withIndex()) {
                        if (!postOne(old)) {
                            // Network flaked again mid-drain — requeue the rest.
                            requeued = backlog.subList(i, backlog.size).toMutableList()
                            break
                        }
                    }
                    if (requeued != null && requeued.isNotEmpty()) {
                        for (p in requeued) enqueue(p)
                    } else {
                        Log.d(TAG, "Flushed ${backlog.size} pending diagnostic(s).")
                    }
                }
            } else {
                enqueue(payload)
                Log.d(TAG, "Buffered diagnostic (queue size ≤ $MAX_PENDING).")
            }
        }.start()
    }

    // ── Convenience methods ──────────────────────────────────────

    fun wakeWordModelLoaded(modelName: String, loadTimeMs: Long) {
        report("wakeword", "Model loaded: $modelName", mapOf(
            "model" to modelName,
            "load_time_ms" to loadTimeMs,
        ))
    }

    fun wakeWordModelFailed(modelName: String, error: String) {
        report("wakeword", "Model failed: $error", mapOf(
            "model" to modelName,
            "error" to error,
        ))
    }

    fun wakeWordDetected(score: Float) {
        report("wakeword", "Detected (score=$score)", mapOf("score" to score))
    }

    fun wakeWordScoreUpdate(score: Float, melFrames: Int, embeddings: Int) {
        report("wakeword", "Score: $score", mapOf(
            "score" to score,
            "mel_frames" to melFrames,
            "embeddings" to embeddings,
        ))
    }

    fun micPermissionState(granted: Boolean) {
        report("mic", "Permission ${if (granted) "granted" else "denied"}", mapOf(
            "granted" to granted,
        ))
    }

    fun micInitFailed(reason: String) {
        report("mic", "Init failed: $reason", mapOf("reason" to reason))
    }

    fun serviceEvent(service: String, event: String, details: String = "") {
        report("service", "$service: $event", mapOf(
            "service" to service,
            "event" to event,
            "details" to details,
        ))
    }

    fun nonFatalError(component: String, error: String, exception: Throwable? = null) {
        report("error", "$component: $error", mapOf(
            "component" to component,
            "error" to error,
            "exception" to (exception?.toString() ?: ""),
        ))
    }
}
