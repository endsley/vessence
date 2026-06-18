package com.vessences.android.photos

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
import java.util.concurrent.TimeUnit

class CameraSyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val result = CameraSyncManager.syncBatch(applicationContext)
        return if (result.failed > 0 && result.uploaded == 0) Result.retry() else Result.success()
    }
}

object CameraSyncScheduler {
    private const val PERIODIC_WORK = "camera_sync_periodic"
    private const val NOW_WORK = "camera_sync_now"

    fun ensureScheduled(context: Context) {
        val settings = CameraSyncSettings(context)
        if (!settings.isEnabled()) {
            cancel(context)
            return
        }
        if (!CameraMediaScanner.hasAnyPhotoPermission(context)) {
            cancel(context)
            return
        }
        val request = PeriodicWorkRequestBuilder<CameraSyncWorker>(
            15,
            TimeUnit.MINUTES,
        )
            .setConstraints(constraints(settings))
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            PERIODIC_WORK,
            ExistingPeriodicWorkPolicy.UPDATE,
            request,
        )
    }

    fun syncNow(context: Context) {
        val settings = CameraSyncSettings(context)
        val request = OneTimeWorkRequestBuilder<CameraSyncWorker>()
            .setConstraints(constraints(settings))
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(
            NOW_WORK,
            ExistingWorkPolicy.REPLACE,
            request,
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_WORK)
        WorkManager.getInstance(context).cancelUniqueWork(NOW_WORK)
    }

    private fun constraints(settings: CameraSyncSettings): Constraints {
        val networkType = if (settings.isWifiOnly()) {
            NetworkType.UNMETERED
        } else {
            NetworkType.CONNECTED
        }
        return Constraints.Builder()
            .setRequiredNetworkType(networkType)
            .setRequiresBatteryNotLow(true)
            .build()
    }
}
