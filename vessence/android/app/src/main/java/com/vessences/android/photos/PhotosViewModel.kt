package com.vessences.android.photos

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class PhotosUiState(
    val photos: List<GalleryPhoto> = emptyList(),
    val searchQuery: String = "",
    val isLoading: Boolean = false,
    val isSyncing: Boolean = false,
    val syncEnabled: Boolean = true,
    val wifiOnly: Boolean = true,
    val hasPhotoAccess: Boolean = false,
    val hasFullPhotoAccess: Boolean = false,
    val lastSyncLabel: String = "",
    val lastSyncMessage: String = "",
    val error: String? = null,
) {
    val filteredPhotos: List<GalleryPhoto>
        get() {
            val query = searchQuery.trim().lowercase()
            if (query.isBlank()) return photos
            return photos.filter {
                it.name.lowercase().contains(query) ||
                    it.path.lowercase().contains(query) ||
                    it.monthLabel.lowercase().contains(query)
            }
        }
}

class PhotosViewModel(application: Application) : AndroidViewModel(application) {
    private val settings = CameraSyncSettings(application)
    private val gallery = PhotoGalleryRepository()
    private val _state = MutableStateFlow(PhotosUiState())
    val state: StateFlow<PhotosUiState> = _state

    init {
        refreshPermissionState()
        CameraSyncScheduler.ensureScheduled(getApplication())
        refreshPhotos()
    }

    fun refreshPermissionState() {
        val context = getApplication<Application>()
        _state.value = _state.value.copy(
            syncEnabled = settings.isEnabled(),
            wifiOnly = settings.isWifiOnly(),
            hasPhotoAccess = CameraMediaScanner.hasAnyPhotoPermission(context),
            hasFullPhotoAccess = CameraMediaScanner.hasFullPhotoPermission(context),
            lastSyncLabel = formatLastSync(settings.lastRunMillis()),
            lastSyncMessage = settings.lastMessage(),
        )
    }

    fun setSearchQuery(query: String) {
        _state.value = _state.value.copy(searchQuery = query)
    }

    fun setSyncEnabled(enabled: Boolean) {
        settings.setEnabled(enabled)
        if (enabled) CameraSyncScheduler.ensureScheduled(getApplication())
        else CameraSyncScheduler.cancel(getApplication())
        refreshPermissionState()
    }

    fun setWifiOnly(wifiOnly: Boolean) {
        settings.setWifiOnly(wifiOnly)
        CameraSyncScheduler.ensureScheduled(getApplication())
        refreshPermissionState()
    }

    fun refreshPhotos() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            runCatching { gallery.loadCameraPhotos() }
                .onSuccess { photos ->
                    _state.value = _state.value.copy(
                        photos = photos,
                        isLoading = false,
                    )
                }
                .onFailure { error ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = error.message,
                    )
                }
        }
    }

    fun syncNow() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isSyncing = true, error = null)
            val result = runCatching {
                CameraSyncManager.syncBatch(getApplication(), maxUploads = 60)
            }
            result
                .onSuccess {
                    _state.value = _state.value.copy(
                        isSyncing = false,
                        lastSyncMessage = it.message,
                        lastSyncLabel = formatLastSync(System.currentTimeMillis()),
                    )
                    refreshPermissionState()
                    refreshPhotos()
                }
                .onFailure { error ->
                    _state.value = _state.value.copy(
                        isSyncing = false,
                        error = error.message,
                    )
                }
        }
    }

    private fun formatLastSync(millis: Long): String {
        if (millis <= 0L) return "Never"
        return SimpleDateFormat("MMM d, h:mm a", Locale.US).format(Date(millis))
    }
}
