package com.vessences.android.ui.chat

import android.content.Context
import android.net.Uri
import android.widget.Toast
import androidx.core.content.FileProvider
import com.vessences.android.DiagnosticReporter
import java.io.File

internal fun createCameraAttachmentUri(context: Context): Uri {
    val appContext = context.applicationContext
    val photoDir = File(appContext.cacheDir, "camera_attachments").apply {
        if (!exists() && !mkdirs()) {
            throw IllegalStateException("Could not create camera attachment cache")
        }
    }
    val photoFile = File.createTempFile("ticket_photo_", ".jpg", photoDir)
    return FileProvider.getUriForFile(
        appContext,
        "${appContext.packageName}.fileprovider",
        photoFile,
    )
}

internal fun reportCameraLaunchFailure(context: Context, component: String, error: Throwable) {
    DiagnosticReporter.nonFatalError(component, "camera_launch_failed", error)
    Toast.makeText(
        context,
        "Could not open camera: ${error.message ?: error.javaClass.simpleName}",
        Toast.LENGTH_LONG,
    ).show()
}
