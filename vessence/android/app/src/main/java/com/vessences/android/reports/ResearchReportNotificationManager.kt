package com.vessences.android.reports

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.vessences.android.R
import com.vessences.android.ReportReaderActivity

data class ResearchReportNotification(
    val id: String,
    val title: String,
    val message: String,
    val url: String,
    val reportKind: String = "ra_research",
)

class ResearchReportNotificationManager(private val context: Context) {
    private val appContext = context.applicationContext
    private val notifications = NotificationManagerCompat.from(appContext)

    fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = appContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val soundUri = Settings.System.DEFAULT_NOTIFICATION_URI
        val audioAttributes = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .build()
        val channel = NotificationChannel(
            CHANNEL_REPORTS,
            "Research Reports",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Notifications when Jane publishes research reports"
            enableVibration(true)
            setSound(soundUri, audioAttributes)
        }
        manager.createNotificationChannel(channel)
    }

    fun notifyIfNew(report: ResearchReportNotification): Boolean {
        if (report.id.isBlank() || report.url.isBlank()) return false
        ensureChannel()
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val prefKey = lastSeenPrefKey(report.reportKind)
        if (prefs.getString(prefKey, "") == report.id) return false

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(appContext, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return false
        }

        val intent = Intent(appContext, ReportReaderActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(ReportReaderActivity.EXTRA_URL, report.url)
            putExtra(ReportReaderActivity.EXTRA_TITLE, report.title)
            putExtra(ReportReaderActivity.EXTRA_REPORT_ID, report.id)
        }
        val pendingIntent = PendingIntent.getActivity(
            appContext,
            report.id.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(appContext, CHANNEL_REPORTS)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(report.title)
            .setContentText(report.message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(report.message))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .build()

        notifications.notify(report.id.hashCode(), notification)
        prefs.edit().putString(prefKey, report.id).apply()
        return true
    }

    companion object {
        private const val CHANNEL_REPORTS = "research_reports"
        private const val PREFS_NAME = "research_report_notifications"

        fun lastSeenPrefKey(reportKind: String): String =
            "last_seen_${reportKind.ifBlank { "research_report" }}"
    }
}
