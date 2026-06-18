package com.vessences.android.photos

import android.net.Uri
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class CameraPhoto(
    val id: Long,
    val uri: Uri,
    val displayName: String,
    val mimeType: String,
    val size: Long,
    val dateMillis: Long,
    val dateModifiedSeconds: Long,
    val relativePath: String,
    val width: Int,
    val height: Int,
) {
    val syncKey: String = "$id:$dateModifiedSeconds:$size"

    val destination: String
        get() = "images/camera/${format("yyyy/MM")}"

    val description: String
        get() = "Camera photo ${format("yyyy-MM-dd HH:mm:ss")} original $displayName"

    private fun format(pattern: String): String {
        return SimpleDateFormat(pattern, Locale.US).format(Date(dateMillis))
    }
}

data class CameraSyncResult(
    val scanned: Int,
    val uploaded: Int,
    val skipped: Int,
    val failed: Int,
    val message: String,
)

data class GalleryPhoto(
    val name: String,
    val path: String,
    val thumbnailUrl: String,
    val serveUrl: String,
    val monthLabel: String,
    val sizeHuman: String,
    val modifiedHuman: String,
    val description: String,
)
