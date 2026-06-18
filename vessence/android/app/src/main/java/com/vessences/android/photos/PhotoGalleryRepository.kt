package com.vessences.android.photos

import com.vessences.android.data.api.ApiClient
import com.vessences.android.data.model.DirectoryListing
import com.vessences.android.data.model.FileItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

class PhotoGalleryRepository {
    suspend fun loadCameraPhotos(): List<GalleryPhoto> {
        return withContext(Dispatchers.IO) {
            ApiClient.initContextIfNeeded()
            val photos = mutableListOf<GalleryPhoto>()
            val root = list("images/camera")
            photos += root.files.filter { it.isImage }.map { it.toGalleryPhoto("Camera") }

            for (year in root.folders.sortedByDescending { it.name }) {
                val yearListing = list(year.path)
                photos += yearListing.files.filter { it.isImage }.map { it.toGalleryPhoto(year.name) }
                for (month in yearListing.folders.sortedByDescending { it.name }) {
                    val monthListing = list(month.path)
                    val monthLabel = monthLabel(year.name, month.name)
                    photos += monthListing.files
                        .filter { it.isImage }
                        .sortedByDescending { it.modified }
                        .map { it.toGalleryPhoto(monthLabel) }
                }
            }
            photos
        }
    }

    private suspend fun list(path: String): DirectoryListing {
        return runCatching {
            val response = ApiClient.vaultApi.listDirectory(path)
            if (response.isSuccessful) response.body() ?: DirectoryListing(path = path)
            else DirectoryListing(path = path)
        }.getOrElse { DirectoryListing(path = path) }
    }

    private fun FileItem.toGalleryPhoto(monthLabel: String): GalleryPhoto {
        return GalleryPhoto(
            name = name,
            path = path,
            thumbnailUrl = "${ApiClient.getVaultBaseUrl()}/api/files/thumbnail/$path",
            serveUrl = "${ApiClient.getVaultBaseUrl()}/api/files/serve/$path",
            monthLabel = monthLabel,
            sizeHuman = sizeHuman,
            modifiedHuman = modifiedHuman,
            description = description,
        )
    }

    private fun monthLabel(yearText: String, monthText: String): String {
        val year = yearText.toIntOrNull() ?: return "$monthText $yearText"
        val month = monthText.toIntOrNull() ?: return "$monthText $yearText"
        val calendar = Calendar.getInstance().apply {
            set(Calendar.YEAR, year)
            set(Calendar.MONTH, (month - 1).coerceIn(0, 11))
            set(Calendar.DAY_OF_MONTH, 1)
        }
        return SimpleDateFormat("MMMM yyyy", Locale.US).format(calendar.time)
    }
}

private fun ApiClient.initContextIfNeeded() {
    // ApiClient is initialized from MainActivity before Compose is mounted.
}
