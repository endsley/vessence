package com.vessences.android.ui.music

import android.app.Application
import android.webkit.CookieManager
import androidx.annotation.OptIn
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import com.vessences.android.data.api.ApiClient
import com.vessences.android.data.model.Playlist
import com.vessences.android.data.model.Track
import com.vessences.android.data.repository.PlaylistRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

data class MusicUiState(
    val playlists: List<Playlist> = emptyList(),
    val activePlaylist: Playlist? = null,
    val currentTrackIndex: Int = 0,
    val isPlaying: Boolean = false,
    val progress: Float = 0f,
    val duration: Long = 0L,
    val position: Long = 0L,
    val shuffle: Boolean = false,
    val repeat: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,
)

@OptIn(UnstableApi::class)
class MusicViewModel(application: Application) : AndroidViewModel(application) {
    private val repo = PlaylistRepository()
    private val _state = MutableStateFlow(MusicUiState())
    val state: StateFlow<MusicUiState> = _state

    private var player: ExoPlayer? = null
    private var progressJob: kotlinx.coroutines.Job? = null

    init {
        // Sync OkHttp cookies to WebView CookieManager so ExoPlayer can use them
        syncCookiesForMedia()

        val audioAttributes = AudioAttributes.Builder()
            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
            .setUsage(C.USAGE_MEDIA)
            .build()

        // Build a data source factory that forwards cookies from CookieManager
        val httpDataSourceFactory = DefaultHttpDataSource.Factory()
            .setDefaultRequestProperties(buildCookieHeaders())

        player = ExoPlayer.Builder(application)
            .setMediaSourceFactory(DefaultMediaSourceFactory(httpDataSourceFactory))
            .setAudioAttributes(audioAttributes, /* handleAudioFocus= */ true)
            .build()
        player?.playWhenReady = false
        player?.addListener(object : Player.Listener {
            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                val p = player ?: return
                _state.value = _state.value.copy(currentTrackIndex = p.currentMediaItemIndex)
            }
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                _state.value = _state.value.copy(isPlaying = isPlaying)
                if (isPlaying) startProgressUpdates() else progressJob?.cancel()
            }
        })
        loadPlaylists()
    }

    fun loadPlaylists() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true)
            repo.getPlaylists().onSuccess { playlists ->
                _state.value = _state.value.copy(playlists = playlists, isLoading = false)
            }.onFailure { e ->
                _state.value = _state.value.copy(error = e.message, isLoading = false)
            }
        }
    }

    fun openPlaylist(playlistId: String) {
        viewModelScope.launch {
            repo.getPlaylist(playlistId).onSuccess { playlist ->
                _state.value = _state.value.copy(activePlaylist = playlist, currentTrackIndex = 0)
                preparePlaylist(playlist)
            }
        }
    }

    fun closePlaylist() {
        player?.stop()
        player?.clearMediaItems()
        progressJob?.cancel()
        _state.value = _state.value.copy(
            activePlaylist = null,
            isPlaying = false,
            progress = 0f,
        )
    }

    private fun preparePlaylist(playlist: Playlist) {
        val p = player ?: return
        p.stop()
        p.clearMediaItems()
        playlist.tracks.forEach { track ->
            val url = repo.getTrackUrl(track.path)
            p.addMediaItem(MediaItem.fromUri(url))
        }
        p.prepare()
    }

    fun playTrack(index: Int) {
        val p = player ?: return
        if (index < 0 || index >= (p.mediaItemCount)) return
        p.seekTo(index, 0)
        p.play()
        _state.value = _state.value.copy(currentTrackIndex = index, isPlaying = true)
        startProgressUpdates()
    }

    fun togglePlayPause() {
        val p = player ?: return
        if (p.isPlaying) {
            p.pause()
            _state.value = _state.value.copy(isPlaying = false)
            progressJob?.cancel()
        } else {
            p.play()
            _state.value = _state.value.copy(isPlaying = true)
            startProgressUpdates()
        }
    }

    fun next() {
        val p = player ?: return
        val tracks = _state.value.activePlaylist?.tracks ?: return
        val nextIndex = if (_state.value.shuffle) {
            (0 until tracks.size).random()
        } else {
            val next = _state.value.currentTrackIndex + 1
            if (next >= tracks.size) {
                if (_state.value.repeat) 0 else return
            } else next
        }
        playTrack(nextIndex)
    }

    fun previous() {
        val p = player ?: return
        val prevIndex = (_state.value.currentTrackIndex - 1).coerceAtLeast(0)
        playTrack(prevIndex)
    }

    fun seekTo(fraction: Float) {
        val p = player ?: return
        val pos = (fraction * p.duration).toLong()
        p.seekTo(pos)
    }

    fun toggleShuffle() {
        _state.value = _state.value.copy(shuffle = !_state.value.shuffle)
    }

    fun toggleRepeat() {
        _state.value = _state.value.copy(repeat = !_state.value.repeat)
    }

    private fun startProgressUpdates() {
        progressJob?.cancel()
        progressJob = viewModelScope.launch {
            while (true) {
                val p = player ?: break
                if (!p.isPlaying) break
                val duration = p.duration.coerceAtLeast(1)
                val position = p.currentPosition
                _state.value = _state.value.copy(
                    progress = position.toFloat() / duration.toFloat(),
                    duration = duration,
                    position = position,
                )

                // Check if track ended
                if (p.currentMediaItemIndex != _state.value.currentTrackIndex) {
                    _state.value = _state.value.copy(currentTrackIndex = p.currentMediaItemIndex)
                }

                delay(500)
            }
        }
    }

    private fun syncCookiesForMedia() {
        try {
            val cookieStore = ApiClient.getCookieStore()
            val baseUrl = ApiClient.getVaultBaseUrl()
            val cookieManager = CookieManager.getInstance()
            cookieManager.setAcceptCookie(true)
            val url = baseUrl.toHttpUrlOrNull() ?: return
            val cookies = cookieStore.loadForRequest(url)
            for (cookie in cookies) {
                cookieManager.setCookie(baseUrl, cookie.toString())
            }
            cookieManager.flush()
        } catch (_: Exception) {}
    }

    private fun buildCookieHeaders(): Map<String, String> {
        try {
            val cookieStore = ApiClient.getCookieStore()
            val baseUrl = ApiClient.getVaultBaseUrl()
            val url = baseUrl.toHttpUrlOrNull() ?: return emptyMap()
            val cookies = cookieStore.loadForRequest(url)
            if (cookies.isNotEmpty()) {
                val cookieHeader = cookies.joinToString("; ") { "${it.name}=${it.value}" }
                return mapOf("Cookie" to cookieHeader)
            }
        } catch (_: Exception) {}
        return emptyMap()
    }

    override fun onCleared() {
        super.onCleared()
        progressJob?.cancel()
        player?.release()
        player = null
    }
}
