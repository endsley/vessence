package com.vessences.android.photos

import com.vessences.android.data.api.ApiClient
import com.vessences.android.data.model.DirectoryListing
import com.vessences.android.data.model.FileItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

data class CameraPhotoFolder(
    val path: String,
    val label: String,
    val fileCount: Int,
)

data class CameraPhotoPage(
    val photos: List<GalleryPhoto>,
    val nextOffset: Int,
    val hasMoreInFolder: Boolean,
)

class PhotoGalleryRepository {
    suspend fun loadCameraPhotos(): List<GalleryPhoto> {
        return withContext(Dispatchers.IO) {
            val photos = mutableListOf<GalleryPhoto>()
            val root = listOrThrow("images/camera")
            photos += root.files.filter { it.isImage }.map { it.toGalleryPhoto("Camera") }

            for (year in root.folders.sortedByDescending { it.name }) {
                val yearListing = listOrThrow(year.path)
                photos += yearListing.files.filter { it.isImage }.map { it.toGalleryPhoto(year.name) }
                for (month in yearListing.folders.sortedByDescending { it.name }) {
                    val monthListing = listOrThrow(month.path)
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

private fun ApiClient.initContextIfNeeded() {
    // ApiClient is initialized from MainActivity before Compose is mounted.
}
    suspend fun loadPhotoFolders(): List<CameraPhotoFolder> {
        return withContext(Dispatchers.IO) {
            val folders = mutableListOf<CameraPhotoFolder>()
            val root = listOrThrow("images/camera")
            val rootImageCount = root.files.count { it.isImage }
            if (rootImageCount > 0) {
                folders += CameraPhotoFolder(
                    path = "images/camera",
                    label = "Camera",
                    fileCount = rootImageCount,
                )
            }

            for (year in root.folders.sortedByDescending { it.name }) {
                val yearListing = listOrThrow(year.path)
                val yearImageCount = yearListing.files.count { it.isImage }
                if (yearImageCount > 0) {
                    folders += CameraPhotoFolder(
                        path = year.path,
                        label = year.name,
                        fileCount = yearImageCount,
                    )
                }

                for (month in yearListing.folders.sortedByDescending { it.name }) {
                    folders += CameraPhotoFolder(
                        path = month.path,
                        label = monthLabel(year.name, month.name),
                        fileCount = month.fileCount,
                    )
                }
            }
            folders
        }
    }

    suspend fun loadPhotoPage(
        folder: CameraPhotoFolder,
        offset: Int,
        limit: Int,
    ): CameraPhotoPage {
        return withContext(Dispatchers.IO) {
            val listing = listOrThrow(folder.path, offset = offset, limit = limit)
            val pagePhotos = listing.files
                .filter { it.isImage }
                .sortedByDescending { it.modified }
                .map { it.toGalleryPhoto(folder.label) }
            val totalFiles = listing.totalFiles ?: (offset + pagePhotos.size)
            val nextOffset = offset + listing.files.size
            CameraPhotoPage(
                photos = pagePhotos,
                nextOffset = nextOffset,
                hasMoreInFolder = nextOffset < totalFiles,
            )
        }
    }

    private suspend fun listOrThrow(
        path: String,
        offset: Int = 0,
        limit: Int = 0,
    ): DirectoryListing {
        val response = ApiClient.vaultApi.listDirectory(path, offset = offset, limit = limit)
        if (!response.isSuccessful) {
            throw IOException("Failed to load $path (${response.code()})")
        }
        val listing = response.body() ?: throw IOException("Empty listing for $path")
        return listing
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
