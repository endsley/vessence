package com.vessences.android.photos

import android.Manifest
import android.content.ContentUris
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.provider.MediaStore
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object CameraMediaScanner {
    fun requiredPermissions(): Array<String> {
        return when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE -> arrayOf(
                Manifest.permission.READ_MEDIA_IMAGES,
                Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED,
            )
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU -> arrayOf(
                Manifest.permission.READ_MEDIA_IMAGES,
            )
            else -> arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
    }

    fun hasFullPhotoPermission(context: Context): Boolean {
        val permission = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            Manifest.permission.READ_MEDIA_IMAGES
        } else {
            Manifest.permission.READ_EXTERNAL_STORAGE
        }
        return ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED
    }

    fun hasAnyPhotoPermission(context: Context): Boolean {
        if (hasFullPhotoPermission(context)) return true
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) return false
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED,
        ) == PackageManager.PERMISSION_GRANTED
    }

    suspend fun loadCameraPhotos(context: Context, limit: Int = 500): List<CameraPhoto> {
        return withContext(Dispatchers.IO) {
            if (!hasAnyPhotoPermission(context)) return@withContext emptyList()

            val projection = buildList {
                add(MediaStore.Images.Media._ID)
                add(MediaStore.Images.Media.DISPLAY_NAME)
                add(MediaStore.Images.Media.MIME_TYPE)
                add(MediaStore.Images.Media.SIZE)
                add(MediaStore.Images.Media.DATE_TAKEN)
                add(MediaStore.Images.Media.DATE_ADDED)
                add(MediaStore.Images.Media.DATE_MODIFIED)
                add(MediaStore.Images.Media.WIDTH)
                add(MediaStore.Images.Media.HEIGHT)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    add(MediaStore.Images.Media.RELATIVE_PATH)
                } else {
                    add(MediaStore.Images.Media.BUCKET_DISPLAY_NAME)
                }
            }.toTypedArray()

            val selection: String
            val selectionArgs: Array<String>
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                selection = "${MediaStore.Images.Media.RELATIVE_PATH} LIKE ?"
                selectionArgs = arrayOf("DCIM/Camera/%")
            } else {
                selection = "${MediaStore.Images.Media.BUCKET_DISPLAY_NAME} = ?"
                selectionArgs = arrayOf("Camera")
            }

            val sortOrder = "${MediaStore.Images.Media.DATE_TAKEN} DESC, ${MediaStore.Images.Media.DATE_ADDED} DESC"
            val photos = mutableListOf<CameraPhoto>()
            context.contentResolver.query(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                projection,
                selection,
                selectionArgs,
                sortOrder,
            )?.use { cursor ->
                val idCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media._ID)
                val nameCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DISPLAY_NAME)
                val mimeCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.MIME_TYPE)
                val sizeCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.SIZE)
                val takenCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DATE_TAKEN)
                val addedCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DATE_ADDED)
                val modifiedCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DATE_MODIFIED)
                val widthCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.WIDTH)
                val heightCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.HEIGHT)
                val pathCol = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    cursor.getColumnIndexOrThrow(MediaStore.Images.Media.RELATIVE_PATH)
                } else {
                    cursor.getColumnIndexOrThrow(MediaStore.Images.Media.BUCKET_DISPLAY_NAME)
                }

                while (cursor.moveToNext() && photos.size < limit) {
                    val id = cursor.getLong(idCol)
                    val dateTaken = cursor.getLong(takenCol)
                    val dateAdded = cursor.getLong(addedCol)
                    val dateMillis = when {
                        dateTaken > 0L -> dateTaken
                        dateAdded > 0L -> dateAdded * 1000L
                        else -> System.currentTimeMillis()
                    }
                    val displayName = cursor.getString(nameCol).orEmpty()
                        .ifBlank { "camera_$id.jpg" }
                    val mime = cursor.getString(mimeCol).orEmpty()
                        .ifBlank { "image/jpeg" }
                    val uri = ContentUris.withAppendedId(
                        MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                        id,
                    )
                    photos.add(
                        CameraPhoto(
                            id = id,
                            uri = uri,
                            displayName = displayName,
                            mimeType = mime,
                            size = cursor.getLong(sizeCol),
                            dateMillis = dateMillis,
                            dateModifiedSeconds = cursor.getLong(modifiedCol),
                            relativePath = cursor.getString(pathCol).orEmpty(),
                            width = cursor.getInt(widthCol),
                            height = cursor.getInt(heightCol),
                        )
                    )
                }
            }
            photos
        }
    }
}
