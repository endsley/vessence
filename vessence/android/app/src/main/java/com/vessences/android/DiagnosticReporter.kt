package com.vessences.android

import android.content.Context
import android.util.Log
import com.vessences.android.data.api.ApiClient
import okhttp3.MediaType.Companion.toMediaTypeOrNull
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
 *
 * All sends are fire-and-forget on a background thread.
 */
object DiagnosticReporter {
    private const val TAG = "Diagnostics"
    private var appVersion: String = "unknown"
    private var versionCode: Long = -1

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
    }

    fun report(category: String, message: String, data: Map<String, Any?> = emptyMap()) {
        Thread {
            try {
                val payload = JSONObject().apply {
                    put("timestamp", SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).format(Date()))
                    put("category", category)
                    put("message", message)
                    put("app_version", appVersion)
                    put("version_code", versionCode)
                    for ((k, v) in data) {
                        put(k, v)
                    }
                }

                // Use the shared OkHttp client so the session cookie is included
                // (raw HttpURLConnection doesn't share the cookie jar → 401)
                val body = okhttp3.RequestBody.create(
                    "application/json".toMediaTypeOrNull(),
                    payload.toString()
                )
                val request = okhttp3.Request.Builder()
                    .url("${ApiClient.getJaneBaseUrl().trimEnd('/')}/api/device-diagnostics")
                    .post(body)
                    .build()
                ApiClient.getOkHttpClient().newCall(request).execute().close()
            } catch (e: Exception) {
                Log.d(TAG, "Failed to send diagnostic: ${e.message}")
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
