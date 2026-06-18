package com.vessences.android.photos

import android.content.Context
import com.vessences.android.data.api.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object CameraSyncManager {
    suspend fun syncBatch(
        context: Context,
        maxUploads: Int = 40,
        scanLimit: Int = 500,
    ): CameraSyncResult {
        return withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            ApiClient.init(appContext)
            val settings = CameraSyncSettings(appContext)
            if (!settings.isEnabled()) {
                val result = CameraSyncResult(0, 0, 0, 0, "Camera sync is off")
                settings.recordResult(result)
                return@withContext result
            }
            if (!CameraMediaScanner.hasAnyPhotoPermission(appContext)) {
                val result = CameraSyncResult(0, 0, 0, 0, "Photo access is not granted")
                settings.recordResult(result)
                return@withContext result
            }

            val synced = settings.syncedKeys().toMutableSet()
            val photos = CameraMediaScanner.loadCameraPhotos(appContext, limit = scanLimit)
            val uploader = CameraUploader(appContext.contentResolver)
            var uploaded = 0
            var skipped = 0
            var failed = 0

            for (photo in photos) {
                if (photo.syncKey in synced) {
                    skipped += 1
                    continue
                }
                if (uploaded >= maxUploads) break
                val ok = runCatching { uploader.upload(photo) }.getOrDefault(false)
                if (ok) {
                    uploaded += 1
                    synced.add(photo.syncKey)
                    settings.markSynced(photo.syncKey)
                } else {
                    failed += 1
                }
            }

            val remaining = (photos.size - skipped - uploaded - failed).coerceAtLeast(0)
            val message = when {
                uploaded > 0 -> "Uploaded $uploaded photo${if (uploaded == 1) "" else "s"}"
                remaining > 0 -> "Waiting to upload $remaining photo${if (remaining == 1) "" else "s"}"
                failed > 0 -> "$failed photo${if (failed == 1) "" else "s"} failed"
                else -> "Camera library is up to date"
            }
            CameraSyncResult(
                scanned = photos.size,
                uploaded = uploaded,
                skipped = skipped,
                failed = failed,
                message = message,
            ).also { settings.recordResult(it) }
        }
    }
}
