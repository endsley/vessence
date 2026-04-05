package com.vessences.android.ui.music

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val Violet500 = Color(0xFFA855F7)
private val SlateText = Color(0xFF94A3B8)

@Composable
fun MusicScreen(
    onBack: (() -> Unit)? = null,
    viewModel: MusicViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    // Check for pending music play on every navigation (not just ViewModel init)
    LaunchedEffect(Unit) {
        viewModel.checkPendingPlay()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg),
    ) {
        if (onBack != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to Jane", tint = Color.White)
                }
                Text(
                    "Music Playlist",
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        Box(modifier = Modifier.weight(1f)) {
            if (state.activePlaylist != null) {
                PlayerScreen(state, viewModel)
            } else {
                PlaylistListScreen(state, viewModel)
            }
        }
    }
}

@Composable
private fun PlaylistListScreen(state: MusicUiState, viewModel: MusicViewModel) {
    var playlistToDelete by remember { mutableStateOf<com.vessences.android.data.model.Playlist?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg)
            .padding(16.dp),
    ) {
        Text(
            "Music",
            color = Color.White,
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 16.dp),
        )

        if (state.isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Violet500)
            }
        } else if (state.playlists.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No playlists yet", color = SlateText, fontSize = 16.sp)
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.playlists) { playlist ->
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        color = SlateCard,
                    ) {
                        Row(
                            modifier = Modifier
                                .clickable { viewModel.openPlaylist(playlist.id) }
                                .padding(start = 16.dp, top = 16.dp, bottom = 16.dp, end = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text("\uD83C\uDFB5", fontSize = 28.sp)
                            Spacer(modifier = Modifier.width(12.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(playlist.name, color = Color.White, fontWeight = FontWeight.SemiBold)
                                Text("${playlist.trackCount} tracks", color = SlateText, fontSize = 12.sp)
                            }
                            IconButton(onClick = { playlistToDelete = playlist }) {
                                Icon(Icons.Default.Delete, contentDescription = "Delete playlist", tint = Color(0xFFEF4444))
                            }
                            Icon(Icons.Default.ChevronRight, null, tint = SlateText)
                        }
                    }
                }
            }
        }
    }

    // Confirmation dialog
    if (playlistToDelete != null) {
        AlertDialog(
            onDismissRequest = { playlistToDelete = null },
            title = { Text("Delete playlist?", color = Color.White) },
            text = { Text("This will permanently delete \"${playlistToDelete?.name}\". This cannot be undone.", color = SlateText) },
            confirmButton = {
                TextButton(onClick = {
                    playlistToDelete?.let { viewModel.deletePlaylist(it.id) }
                    playlistToDelete = null
                }) {
                    Text("Delete", color = Color(0xFFEF4444))
                }
            },
            dismissButton = {
                TextButton(onClick = { playlistToDelete = null }) {
                    Text("Cancel", color = SlateText)
                }
            },
            containerColor = SlateCard,
        )
    }
}

@Composable
private fun PlayerScreen(state: MusicUiState, viewModel: MusicViewModel) {
    val playlist = state.activePlaylist ?: return
    val currentTrack = playlist.tracks.getOrNull(state.currentTrackIndex)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg),
    ) {
        // Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = { viewModel.closePlaylist() }) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = Color.White)
            }
            Text(
                playlist.name,
                color = Color.White,
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f),
            )
        }

        // Now playing
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("\uD83C\uDFB5", fontSize = 48.sp)
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = currentTrack?.title ?: "No track",
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            // Progress bar
            Spacer(modifier = Modifier.height(16.dp))
            Slider(
                value = state.progress,
                onValueChange = { viewModel.seekTo(it) },
                colors = SliderDefaults.colors(
                    thumbColor = Violet500,
                    activeTrackColor = Violet500,
                    inactiveTrackColor = Color(0xFF334155),
                ),
            )

            // Time display
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(formatTime(state.position), color = SlateText, fontSize = 12.sp)
                Text(formatTime(state.duration), color = SlateText, fontSize = 12.sp)
            }

            // Controls
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = { viewModel.toggleShuffle() }) {
                    Icon(
                        Icons.Default.Shuffle,
                        "Shuffle",
                        tint = if (state.shuffle) Violet500 else SlateText,
                    )
                }
                IconButton(onClick = { viewModel.previous() }) {
                    Icon(Icons.Default.SkipPrevious, "Previous", tint = Color.White, modifier = Modifier.size(32.dp))
                }
                IconButton(
                    onClick = { viewModel.togglePlayPause() },
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(Violet500),
                ) {
                    Icon(
                        if (state.isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                        "Play/Pause",
                        tint = Color.White,
                        modifier = Modifier.size(32.dp),
                    )
                }
                IconButton(onClick = { viewModel.next() }) {
                    Icon(Icons.Default.SkipNext, "Next", tint = Color.White, modifier = Modifier.size(32.dp))
                }
                IconButton(onClick = { viewModel.toggleRepeat() }) {
                    Icon(
                        Icons.Default.Repeat,
                        "Repeat",
                        tint = if (state.repeat) Violet500 else SlateText,
                    )
                }
            }
        }

        // Track list
        HorizontalDivider(color = Color(0xFF334155))
        LazyColumn(
            modifier = Modifier.weight(1f),
            contentPadding = PaddingValues(horizontal = 8.dp),
        ) {
            itemsIndexed(playlist.tracks) { index, track ->
                val isCurrent = index == state.currentTrackIndex
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .then(
                            if (isCurrent) Modifier.background(Color(0xFF1E1B4B).copy(alpha = 0.5f))
                            else Modifier
                        )
                        .clickable { viewModel.playTrack(index) }
                        .padding(horizontal = 12.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "${index + 1}",
                        color = if (isCurrent) Violet500 else SlateText,
                        fontSize = 14.sp,
                        modifier = Modifier.width(28.dp),
                    )
                    Text(
                        track.title,
                        color = if (isCurrent) Violet500 else Color.White,
                        fontSize = 14.sp,
                        fontWeight = if (isCurrent) FontWeight.SemiBold else FontWeight.Normal,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    if (isCurrent && state.isPlaying) {
                        Text("\uD83C\uDFB5", fontSize = 14.sp)
                    }
                }
            }
        }
    }
}

private fun formatTime(ms: Long): String {
    val totalSeconds = ms / 1000
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return "%d:%02d".format(minutes, seconds)
}
