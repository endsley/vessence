package com.vessences.android.reports

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.vessences.android.data.api.ApiClient
import java.util.concurrent.TimeUnit

class ResearchReportWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        return try {
            ApiClient.init(applicationContext)
            val response = ApiClient.janeApi.getLatestRaReport()
            if (!response.isSuccessful) {
                return if (response.code() >= 500) Result.retry() else Result.success()
            }
            val body = response.body() ?: return Result.success()
            val report = body.toResearchReportNotification() ?: return Result.success()
            ResearchReportNotificationManager(applicationContext).notifyIfNew(report)
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }

    private fun Map<String, Any>.toResearchReportNotification(): ResearchReportNotification? {
        val reportId = stringValue("report_id") ?: stringValue("id") ?: return null
        val relativeUrl = stringValue("report_url") ?: stringValue("web_url") ?: return null
        val absoluteUrl = absoluteJaneUrl(relativeUrl)
        val title = stringValue("title") ?: "RA research update ready"
        val message = stringValue("message") ?: "Tap to read the latest RA research HTML report."
        val reportKind = stringValue("report_kind") ?: "ra_research"
        val notificationId = stringValue("id") ?: "ra_report_$reportId"
        return ResearchReportNotification(
            id = notificationId,
            title = title,
            message = message,
            url = absoluteUrl,
            reportKind = reportKind,
        )
    }

    private fun Map<String, Any>.stringValue(key: String): String? =
        (this[key] as? String)?.trim()?.takeIf { it.isNotBlank() }

    private fun absoluteJaneUrl(pathOrUrl: String): String {
        if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) return pathOrUrl
        val base = ApiClient.getJaneBaseUrl().trimEnd('/')
        val path = if (pathOrUrl.startsWith("/")) pathOrUrl else "/$pathOrUrl"
        return "$base$path"
    }
}

object ResearchReportScheduler {
    private const val PERIODIC_WORK = "research_report_periodic"
    private const val CHECK_NOW_WORK = "research_report_check_now"

    fun ensureScheduled(context: Context) {
        val request = PeriodicWorkRequestBuilder<ResearchReportWorker>(
            15,
            TimeUnit.MINUTES,
        )
            .setConstraints(networkConstraints())
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            PERIODIC_WORK,
            ExistingPeriodicWorkPolicy.UPDATE,
            request,
        )
    }

    fun checkNow(context: Context) {
        val request = OneTimeWorkRequestBuilder<ResearchReportWorker>()
            .setConstraints(networkConstraints())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(
            CHECK_NOW_WORK,
            ExistingWorkPolicy.REPLACE,
            request,
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_WORK)
        WorkManager.getInstance(context).cancelUniqueWork(CHECK_NOW_WORK)
    }

    private fun networkConstraints(): Constraints =
        Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
}
