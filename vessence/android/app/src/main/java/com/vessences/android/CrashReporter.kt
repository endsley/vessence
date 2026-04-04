package com.vessences.android

import android.content.Context
import android.os.Build
import android.util.Log
import com.vessences.android.data.api.ApiClient
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Captures uncaught exceptions and sends them to the server for debugging.
 * Also saves locally so the crash can be reviewed on next launch.
 */
object CrashReporter {
    private const val TAG = "CrashReporter"
    private const val PREFS_NAME = "crash_reports"
    private const val KEY_LAST_CRASH = "last_crash"

    fun install(context: Context) {
        // First, upload any crash from the previous session
        uploadPendingCrash(context)

        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                val report = buildReport(context, thread, throwable)
                Log.e(TAG, "CRASH REPORT:\n$report")

                // Save locally — will be uploaded on next launch
                context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    .edit()
                    .putString(KEY_LAST_CRASH, report)
                    .commit()  // commit (sync) not apply (async) — app is dying
            } catch (_: Exception) {}

            // Call the default handler
            defaultHandler?.uncaughtException(thread, throwable)
        }
    }

    private fun uploadPendingCrash(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val report = prefs.getString(KEY_LAST_CRASH, null) ?: return
        Log.i(TAG, "Found pending crash report, uploading...")

        Thread {
            try {
                sendToServer(report)
                prefs.edit().remove(KEY_LAST_CRASH).apply()
                Log.i(TAG, "Crash report uploaded and cleared")
            } catch (e: Exception) {
                Log.w(TAG, "Failed to upload crash report: ${e.message}")
                // Keep it — will retry on next launch
            }
        }.start()
    }

    fun getLastCrash(context: Context): String? {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(KEY_LAST_CRASH, null)
    }

    fun clearLastCrash(context: Context) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit().remove(KEY_LAST_CRASH).apply()
    }

    private fun buildReport(context: Context, thread: Thread, throwable: Throwable): String {
        val sw = StringWriter()
        throwable.printStackTrace(PrintWriter(sw))
        val stackTrace = sw.toString()

        val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())
        val versionName = try {
            context.packageManager.getPackageInfo(context.packageName, 0).versionName
        } catch (_: Exception) { "unknown" }
        val versionCode = try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                context.packageManager.getPackageInfo(context.packageName, 0).longVersionCode
            } else {
                @Suppress("DEPRECATION")
                context.packageManager.getPackageInfo(context.packageName, 0).versionCode.toLong()
            }
        } catch (_: Exception) { -1L }

        return """
            |=== VESSENCE CRASH REPORT ===
            |Time: $timestamp
            |Version: $versionName (code $versionCode)
            |Device: ${Build.MANUFACTURER} ${Build.MODEL}
            |Android: ${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})
            |Thread: ${thread.name}
            |
            |Exception: ${throwable.javaClass.simpleName}: ${throwable.message}
            |
            |Stack trace:
            |$stackTrace
        """.trimMargin()
    }

    private fun sendToServer(report: String) {
        try {
            val url = java.net.URL("${ApiClient.getJaneBaseUrl()}/api/crash-report")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "text/plain")
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            conn.doOutput = true
            conn.outputStream.use { it.write(report.toByteArray()) }
            conn.responseCode // trigger the request
            conn.disconnect()
        } catch (_: Exception) {}
    }
}
