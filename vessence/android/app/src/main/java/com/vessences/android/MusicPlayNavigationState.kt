package com.vessences.android

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Observable state for music play navigation.
 * When Jane responds with [MUSIC_PLAY:playlist_id], ChatViewModel sets the playlist ID here.
 * VessencesApp observes and navigates to the Music Playlist screen.
 */
object MusicPlayNavigationState {
    private val _pendingPlaylist = MutableStateFlow<String?>(null)
    val pendingPlaylist: StateFlow<String?> = _pendingPlaylist

    fun requestPlay(playlistId: String) {
        _pendingPlaylist.value = playlistId
    }

    fun consume(): String? {
        val id = _pendingPlaylist.value
        _pendingPlaylist.value = null
        return id
    }
}
