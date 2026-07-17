package com.vessences.android.photos

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CloudSync
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.vessences.android.data.api.ApiClient
import kotlinx.coroutines.flow.distinctUntilChanged

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val SlateBorder = Color(0xFF334155)
private val Violet500 = Color(0xFFA855F7)
private val SlateText = Color(0xFF94A3B8)
private val DangerText = Color(0xFFF87171)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PhotosScreen(
    onBack: () -> Unit,
    viewModel: PhotosViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    val imageLoader = remember { ApiClient.getAuthenticatedImageLoader(context) }
    var selectedPhoto by remember { mutableStateOf<GalleryPhoto?>(null) }
    var requestedInitialPhotoAccess by remember { mutableStateOf(false) }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) {
        viewModel.refreshPermissionState()
        CameraSyncScheduler.ensureScheduled(context)
        viewModel.syncNow()
    }

    LaunchedEffect(state.hasPhotoAccess, state.syncEnabled) {
        if (!state.hasPhotoAccess && state.syncEnabled && !requestedInitialPhotoAccess) {
            requestedInitialPhotoAccess = true
            permissionLauncher.launch(CameraMediaScanner.requiredPermissions())
        }
    }

    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                viewModel.refreshPermissionState()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    selectedPhoto?.let { photo ->
        PhotoPreview(
            photo = photo,
            imageLoader = imageLoader,
            onClose = { selectedPhoto = null },
        )
        return
    }

    Scaffold(
        containerColor = SlateBg,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Photos",
                        color = Color.White,
                        fontWeight = FontWeight.SemiBold,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                            tint = Color.White,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.refreshPhotos() }) {
                        Icon(Icons.Default.Refresh, "Refresh", tint = SlateText)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = SlateBg),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(SlateBg),
        ) {
            SyncPanel(
                state = state,
                onRequestPermission = {
                    permissionLauncher.launch(CameraMediaScanner.requiredPermissions())
                },
                onSyncEnabled = viewModel::setSyncEnabled,
                onWifiOnly = viewModel::setWifiOnly,
                onSyncNow = viewModel::syncNow,
            )
            SearchRow(
                query = state.searchQuery,
                onQueryChange = viewModel::setSearchQuery,
            )

            when {
                state.isLoading -> LoadingBody()
                state.error != null -> ErrorBody(state.error!!)
                state.filteredPhotos.isEmpty() -> EmptyBody(
                    hasPhotoAccess = state.hasPhotoAccess,
                    hasLoadedPhotos = state.photos.isNotEmpty(),
                    searchQuery = state.searchQuery,
                )
                else -> PhotoGrid(
                    photos = state.filteredPhotos,
                    imageLoader = imageLoader,
                    hasMorePhotos = state.hasMorePhotos,
                    isLoadingMore = state.isLoadingMore,
                    onLoadMore = viewModel::loadMorePhotos,
                    onOpenPhoto = { selectedPhoto = it },
                )
            }
        }
    }
}

@Composable
private fun SyncPanel(
    state: PhotosUiState,
    onRequestPermission: () -> Unit,
    onSyncEnabled: (Boolean) -> Unit,
    onWifiOnly: (Boolean) -> Unit,
    onSyncNow: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp),
        color = SlateCard,
        shape = RoundedCornerShape(8.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.CloudSync, null, tint = Violet500)
                Spacer(modifier = Modifier.size(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text("Camera sync", color = Color.White, fontWeight = FontWeight.SemiBold)
                    Text(
                        "Last: ${state.lastSyncLabel}",
                        color = SlateText,
                        fontSize = 12.sp,
                    )
                }
                Switch(
                    checked = state.syncEnabled,
                    onCheckedChange = onSyncEnabled,
                )
            }

            if (state.lastSyncMessage.isNotBlank()) {
                Text(
                    state.lastSyncMessage,
                    color = SlateText,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Wi-Fi only", color = SlateText, fontSize = 13.sp, modifier = Modifier.weight(1f))
                Switch(
                    checked = state.wifiOnly,
                    onCheckedChange = onWifiOnly,
                )
            }

            if (!state.hasPhotoAccess) {
                Button(
                    onClick = {
                        onRequestPermission()
                    },
                    enabled = state.syncEnabled && !state.isSyncing,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 10.dp),
                ) {
                    Text("Allow photos")
                }
            } else {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 10.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (!state.hasFullPhotoAccess) {
                        TextButton(onClick = onRequestPermission) {
                            Text("Photo access", color = Violet500)
                        }
                    }
                    Button(
                        onClick = onSyncNow,
                        enabled = state.syncEnabled && !state.isSyncing,
                    ) {
                        if (state.isSyncing) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                strokeWidth = 2.dp,
                                color = Color.White,
                            )
                        } else {
                            Text("Sync now")
                        }
                    }
                }
            }

            if (state.hasPhotoAccess && !state.hasFullPhotoAccess) {
                Text(
                    "Limited photo access",
                    color = DangerText,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
}

@Composable
private fun SearchRow(query: String, onQueryChange: (String) -> Unit) {
    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp),
        singleLine = true,
        leadingIcon = { Icon(Icons.Default.Search, null, tint = SlateText) },
        placeholder = { Text("Search photos", color = SlateText) },
        colors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = Color.White,
            unfocusedTextColor = Color.White,
            focusedBorderColor = Violet500,
            unfocusedBorderColor = SlateBorder,
            focusedContainerColor = SlateCard,
            unfocusedContainerColor = SlateCard,
        ),
    )
}

@Composable
private fun PhotoGrid(
    photos: List<GalleryPhoto>,
    imageLoader: coil.ImageLoader,
    hasMorePhotos: Boolean,
    isLoadingMore: Boolean,
    onLoadMore: () -> Unit,
    onOpenPhoto: (GalleryPhoto) -> Unit,
) {
    val gridState = rememberLazyGridState()

    LaunchedEffect(gridState, photos.size, hasMorePhotos, isLoadingMore) {
        snapshotFlow { gridState.isNearEnd() && hasMorePhotos && !isLoadingMore }
            .distinctUntilChanged()
            .collect { shouldLoad ->
                if (shouldLoad) onLoadMore()
            }
    }

    val grouped = photos.groupBy { it.monthLabel }
    LazyVerticalGrid(
        columns = GridCells.Adaptive(minSize = 112.dp),
        state = gridState,
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 8.dp, end = 8.dp, top = 4.dp, bottom = 96.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        grouped.forEach { (month, monthPhotos) ->
            item(span = { GridItemSpan(maxLineSpan) }) {
                Text(
                    text = month,
                    color = SlateText,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 8.dp),
                )
            }
            items(monthPhotos, key = { it.path }) { photo ->
                PhotoTile(
                    photo = photo,
                    imageLoader = imageLoader,
                    onOpen = { onOpenPhoto(photo) },
                )
            }
        }
        if (isLoadingMore) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(22.dp),
                        strokeWidth = 2.dp,
                        color = Violet500,
                    )
                }
            }
        }
    }
}

private fun LazyGridState.isNearEnd(): Boolean {
    val lastVisible = layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: return false
    val total = layoutInfo.totalItemsCount
    return total > 0 && lastVisible >= total - 6
}

@Composable
private fun PhotoTile(
    photo: GalleryPhoto,
    imageLoader: coil.ImageLoader,
    onOpen: () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(1f)
            .clip(RoundedCornerShape(6.dp))
            .background(SlateCard)
            .clickable(onClick = onOpen),
    ) {
        AsyncImage(
            model = ImageRequest.Builder(LocalContext.current)
                .data(photo.thumbnailUrl)
                .crossfade(true)
                .build(),
            imageLoader = imageLoader,
            contentDescription = photo.name,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PhotoPreview(
    photo: GalleryPhoto,
    imageLoader: coil.ImageLoader,
    onClose: () -> Unit,
) {
    Scaffold(
        containerColor = Color.Black,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        photo.name,
                        color = Color.White,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onClose) {
                        Icon(Icons.Default.Close, "Close", tint = Color.White)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Black),
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentAlignment = Alignment.Center,
        ) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(photo.serveUrl)
                    .crossfade(true)
                    .build(),
                imageLoader = imageLoader,
                contentDescription = photo.name,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Fit,
            )
        }
    }
}

@Composable
private fun LoadingBody() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(color = Violet500)
    }
}

@Composable
private fun EmptyBody(
    hasPhotoAccess: Boolean,
    hasLoadedPhotos: Boolean,
    searchQuery: String,
) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Default.Image, null, tint = SlateText, modifier = Modifier.size(44.dp))
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                when {
                    !hasPhotoAccess -> "Photo access needed"
                    searchQuery.isNotBlank() && hasLoadedPhotos -> "No loaded photos match"
                    else -> "No synced photos yet"
                },
                color = SlateText,
            )
        }
    }
}

@Composable
private fun ErrorBody(message: String) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text(message, color = DangerText)
    }
}
