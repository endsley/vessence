package com.vessences.android.ui.briefing

import android.content.Intent
import android.net.Uri
import java.text.SimpleDateFormat
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.OpenInBrowser
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.BookmarkBorder
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.vessences.android.data.api.ApiClient
import com.vessences.android.data.model.BriefingArticle

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val SlateMuted = Color(0xFF94A3B8)
private val SlateSubtle = Color(0xFF334155)
private val Violet500 = Color(0xFFA855F7)
private val Violet700 = Color(0xFF7C3AED)

private val TopicColors = mapOf(
    "technology" to Color(0xFF3B82F6),
    "business" to Color(0xFF10B981),
    "science" to Color(0xFFF59E0B),
    "health" to Color(0xFFEF4444),
    "politics" to Color(0xFF8B5CF6),
    "sports" to Color(0xFFF97316),
    "entertainment" to Color(0xFFEC4899),
    "world" to Color(0xFF06B6D4),
)

@Composable
fun BriefingScreen(
    onBack: (() -> Unit)? = null,
    viewModel: BriefingViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    val filteredArticles = viewModel.getFilteredArticles()
    var bottomSheetArticle by remember { mutableStateOf<BriefingArticle?>(null) }
    var showHistorySheet by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // Top bar
            TopBar(
                onBack = if (state.viewingArchiveDate != null) { { viewModel.clearArchive() } } else onBack,
                lastUpdated = state.lastUpdated,
                isLoading = state.isLoading || state.isLoadingArchive,
                viewingArchive = state.viewingArchiveDate != null,
                onRefresh = { viewModel.refresh() },
                onShowHistory = { showHistorySheet = true },
            )

            // Category filter chips
            TopicChips(
                topics = run {
                    // Shared first (from backend), then All, then rest
                    val rest = state.categories.filter { it != "Shared" }
                    val tabs = mutableListOf<String>()
                    if ("Shared" in state.categories) tabs.add("Shared")
                    tabs.add("All")
                    tabs.addAll(rest)
                    tabs
                },
                selected = if (state.viewingSaved) "" else state.selectedCategory,
                onSelect = {
                    if (state.viewingSaved) viewModel.toggleSavedView()
                    viewModel.selectCategory(it)
                },
                trailingContent = {
                    // Saved chip
                    FilterChip(
                        selected = state.viewingSaved,
                        onClick = { viewModel.toggleSavedView() },
                        label = {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    if (state.viewingSaved) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                                    "Saved",
                                    modifier = Modifier.size(14.dp),
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Saved", fontSize = 12.sp)
                            }
                        },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = Color(0xFFF59E0B),
                            selectedLabelColor = Color.White,
                            containerColor = SlateCard,
                            labelColor = Color(0xFFF59E0B),
                        ),
                        border = FilterChipDefaults.filterChipBorder(
                            borderColor = Color(0xFFF59E0B).copy(alpha = 0.5f),
                            selectedBorderColor = Color(0xFFF59E0B),
                            enabled = true,
                            selected = state.viewingSaved,
                        ),
                    )
                },
            )

            // Saved articles view
            if (state.viewingSaved) {
                // Category filter for saved articles
                if (state.savedCategories.isNotEmpty()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState())
                            .padding(horizontal = 12.dp, vertical = 2.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        FilterChip(
                            selected = state.savedFilterCategory == null,
                            onClick = { viewModel.loadSavedArticles(null) },
                            label = { Text("All Saved", fontSize = 11.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = Color(0xFFF59E0B),
                                selectedLabelColor = Color.White,
                                containerColor = SlateCard,
                                labelColor = SlateMuted,
                            ),
                            border = FilterChipDefaults.filterChipBorder(
                                borderColor = SlateSubtle,
                                selectedBorderColor = Color(0xFFF59E0B),
                                enabled = true,
                                selected = state.savedFilterCategory == null,
                            ),
                        )
                        state.savedCategories.forEach { cat ->
                            FilterChip(
                                selected = state.savedFilterCategory == cat,
                                onClick = { viewModel.loadSavedArticles(cat) },
                                label = { Text(cat, fontSize = 11.sp) },
                                colors = FilterChipDefaults.filterChipColors(
                                    selectedContainerColor = Color(0xFFF59E0B),
                                    selectedLabelColor = Color.White,
                                    containerColor = SlateCard,
                                    labelColor = SlateMuted,
                                ),
                                border = FilterChipDefaults.filterChipBorder(
                                    borderColor = SlateSubtle,
                                    selectedBorderColor = Color(0xFFF59E0B),
                                    enabled = true,
                                    selected = state.savedFilterCategory == cat,
                                ),
                            )
                        }
                    }
                }

                if (state.savedArticles.isEmpty()) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(Icons.Default.BookmarkBorder, "No saved", tint = SlateMuted, modifier = Modifier.size(32.dp))
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("No saved articles yet", color = SlateMuted, fontSize = 14.sp)
                            Text("Tap the bookmark icon on any article to save it", color = SlateSubtle, fontSize = 11.sp)
                        }
                    }
                } else {
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(2),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(state.savedArticles, key = { it.articleId }) { saved ->
                            saved.article?.let { article ->
                                ArticleCard(
                                    article = article,
                                    imageUrl = viewModel.getImageUrl(article.id),
                                    isSaved = true,
                                    onExpand = { bottomSheetArticle = article },
                                    onSpeakBrief = { viewModel.speakArticle(article, "brief") },
                                    onSpeakFull = { viewModel.speakArticle(article, "full") },
                                    onDismiss = {},
                                    onSave = {},
                                    onUnsave = { viewModel.unsaveArticle(article.id) },
                                    savedCategories = emptyList(),
                                )
                            }
                        }
                    }
                }
            }
            // Error state
            else if (state.error != null && state.articles.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            state.error ?: "Error",
                            color = SlateMuted,
                            fontSize = 14.sp,
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            "Tap refresh to retry",
                            color = SlateSubtle,
                            fontSize = 12.sp,
                        )
                    }
                }
            }
            // Loading state (initial)
            else if ((state.isLoading || state.isLoadingArchive) && state.articles.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(color = Violet500)
                }
            }
            // Empty state
            else if (filteredArticles.isEmpty() && !state.isLoading && !state.isLoadingArchive) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        "No articles found",
                        color = SlateMuted,
                        fontSize = 14.sp,
                    )
                }
            }
            // Article grid
            else {
                ArticleGrid(
                    articles = filteredArticles,
                    viewModel = viewModel,
                    onExpand = { bottomSheetArticle = it },
                    onSpeakBrief = { viewModel.speakArticle(it, "brief") },
                    onSpeakFull = { viewModel.speakArticle(it, "full") },
                    onDismiss = { viewModel.dismissArticle(it.id) },
                )
            }
        }

        // FAB - Read All / Stop Audio
        var showReadMenu by remember { mutableStateOf(false) }
        Column(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp),
            horizontalAlignment = Alignment.End,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            // Expanded menu options
            if (showReadMenu && !state.isSpeaking) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFF1E293B),
                    shadowElevation = 8.dp,
                ) {
                    Column(modifier = Modifier.padding(4.dp)) {
                        Surface(
                            onClick = { showReadMenu = false; viewModel.readAll("full") },
                            shape = RoundedCornerShape(8.dp),
                            color = Color.Transparent,
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Icon(Icons.AutoMirrored.Filled.VolumeUp, "Full", tint = Color.White, modifier = Modifier.size(20.dp))
                                Text("Read All (Full)", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                            }
                        }
                        Surface(
                            onClick = { showReadMenu = false; viewModel.readAll("brief") },
                            shape = RoundedCornerShape(8.dp),
                            color = Color.Transparent,
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Icon(Icons.AutoMirrored.Filled.VolumeUp, "Brief", tint = Color(0xFF94A3B8), modifier = Modifier.size(20.dp))
                                Text("Read All (Brief)", color = Color(0xFF94A3B8), fontSize = 14.sp, fontWeight = FontWeight.Medium)
                            }
                        }
                    }
                }
            }
            FloatingActionButton(
                onClick = {
                    if (state.isSpeaking) { viewModel.stopSpeaking(); showReadMenu = false }
                    else showReadMenu = !showReadMenu
                },
                containerColor = if (state.isSpeaking) Color(0xFFDC2626) else Violet500,
                contentColor = Color.White,
            ) {
                if (state.isSpeaking) {
                    Icon(Icons.Default.Close, contentDescription = "Stop audio")
                } else {
                    Icon(Icons.Default.RecordVoiceOver, contentDescription = "Read all")
                }
            }
        }
    }

    // Bottom sheet for article detail
    if (bottomSheetArticle != null) {
        ArticleDetailSheet(
            article = bottomSheetArticle!!,
            viewModel = viewModel,
            onDismiss = { bottomSheetArticle = null },
        )
    }

    // History Bottom Sheet
    if (showHistorySheet) {
        HistorySheet(
            dates = state.archiveDates,
            onSelect = { viewModel.loadArchive(it); showHistorySheet = false },
            onDismiss = { showHistorySheet = false }
        )
    }
}

@Composable
private fun TopBar(
    onBack: (() -> Unit)?,
    lastUpdated: String?,
    isLoading: Boolean,
    viewingArchive: Boolean,
    onRefresh: () -> Unit,
    onShowHistory: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (onBack != null) {
            IconButton(onClick = onBack) {
                Icon(
                    Icons.AutoMirrored.Filled.ArrowBack,
                    "Back",
                    tint = Color.White,
                )
            }
        } else {
            Spacer(modifier = Modifier.width(12.dp))
        }

        Column(modifier = Modifier.weight(1f)) {
            Text(
                if (viewingArchive) "Briefing Archive" else "Daily Briefing",
                color = Color.White,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
            )
            if (lastUpdated != null) {
                Text(
                    if (viewingArchive) "Archive for $lastUpdated" else "Updated $lastUpdated",
                    color = if (viewingArchive) Violet500 else SlateMuted,
                    fontSize = 11.sp,
                )
            }
        }

        if (isLoading) {
            CircularProgressIndicator(
                color = Violet500,
                modifier = Modifier.size(20.dp),
                strokeWidth = 2.dp,
            )
            Spacer(modifier = Modifier.width(12.dp))
        }

        IconButton(onClick = onShowHistory) {
            Icon(
                Icons.Default.History,
                "History",
                tint = if (viewingArchive) Violet500 else Color.White,
            )
        }

        IconButton(onClick = onRefresh) {
            Icon(
                Icons.Default.Refresh,
                "Refresh",
                tint = Color.White,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HistorySheet(
    dates: List<String>,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState()
    
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = SlateCard,
        contentColor = Color.White,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 32.dp),
        ) {
            Text(
                "Past Briefings",
                modifier = Modifier.padding(16.dp),
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
            
            HorizontalDivider(color = SlateSubtle)
            
            if (dates.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxWidth().height(100.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text("No archived briefings found", color = SlateMuted)
                }
            } else {
                dates.forEach { date ->
                    Surface(
                        onClick = { onSelect(date) },
                        color = Color.Transparent,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.History, null, tint = SlateMuted, modifier = Modifier.size(20.dp))
                            Spacer(modifier = Modifier.width(16.dp))
                            Text(date, color = Color.White, fontSize = 16.sp)
                        }
                    }
                    HorizontalDivider(color = SlateSubtle.copy(alpha = 0.5f), modifier = Modifier.padding(horizontal = 16.dp))
                }
            }
        }
    }
}

@Composable
private fun TopicChips(
    topics: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
    trailingContent: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 12.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        topics.forEach { topic ->
            val isSelected = topic == selected
            FilterChip(
                selected = isSelected,
                onClick = { onSelect(topic) },
                label = {
                    Text(
                        topic,
                        fontSize = 12.sp,
                    )
                },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = Violet500,
                    selectedLabelColor = Color.White,
                    containerColor = SlateCard,
                    labelColor = SlateMuted,
                ),
                border = FilterChipDefaults.filterChipBorder(
                    borderColor = SlateSubtle,
                    selectedBorderColor = Violet500,
                    enabled = true,
                    selected = isSelected,
                ),
            )
        }
        trailingContent?.invoke()
    }
}

@Composable
private fun ArticleGrid(
    articles: List<BriefingArticle>,
    viewModel: BriefingViewModel,
    onExpand: (BriefingArticle) -> Unit,
    onSpeakBrief: (BriefingArticle) -> Unit,
    onSpeakFull: (BriefingArticle) -> Unit,
    onDismiss: (BriefingArticle) -> Unit,
) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(articles, key = { it.id }) { article ->
            ArticleCard(
                article = article,
                imageUrl = viewModel.getImageUrl(article.id),
                isSaved = viewModel.isArticleSaved(article.id),
                onExpand = { onExpand(article) },
                onSpeakBrief = { onSpeakBrief(article) },
                onSpeakFull = { onSpeakFull(article) },
                onDismiss = { onDismiss(article) },
                onSave = { viewModel.saveArticle(article.id, it) },
                onUnsave = { viewModel.unsaveArticle(article.id) },
                savedCategories = viewModel.state.value.savedCategories,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ArticleCard(
    article: BriefingArticle,
    imageUrl: String,
    isSaved: Boolean = false,
    onExpand: () -> Unit,
    onSpeakBrief: () -> Unit,
    onSpeakFull: () -> Unit,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit = {},
    onUnsave: () -> Unit = {},
    savedCategories: List<String> = emptyList(),
) {
    val context = LocalContext.current
    val topicColor = TopicColors[article.topic.lowercase()] ?: Violet500
    val dimmed = article.dismissed

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = SlateCard,
        shadowElevation = 2.dp,
        modifier = if (dimmed) Modifier.graphicsLayer(alpha = 0.5f) else Modifier,
    ) {
        Column {
            // Image area with topic badge
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(16f / 10f)
                    .clip(RoundedCornerShape(topStart = 12.dp, topEnd = 12.dp)),
            ) {
                AsyncImage(
                    model = ImageRequest.Builder(context)
                        .data(imageUrl)
                        .crossfade(true)
                        .build(),
                    imageLoader = ApiClient.getAuthenticatedImageLoader(context),
                    contentDescription = article.title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(
                            Brush.verticalGradient(
                                colors = listOf(Color.Transparent, SlateBg.copy(alpha = 0.7f)),
                                startY = 0f, endY = Float.MAX_VALUE,
                            ),
                        ),
                )
                // Topic badge
                Surface(
                    shape = RoundedCornerShape(4.dp),
                    color = topicColor.copy(alpha = 0.9f),
                    modifier = Modifier.padding(6.dp).align(Alignment.TopStart),
                ) {
                    Text(article.topic, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                }
                // Dismissed badge
                if (dimmed) {
                    Surface(
                        shape = RoundedCornerShape(4.dp),
                        color = Color(0xFF475569).copy(alpha = 0.9f),
                        modifier = Modifier.padding(6.dp).align(Alignment.TopEnd),
                    ) {
                        Text("Archived", color = Color.White, fontSize = 9.sp,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                    }
                }
            }

            // Text content
            Column(modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp)) {
                Text(article.title, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                    maxLines = 2, overflow = TextOverflow.Ellipsis, lineHeight = 17.sp)
                Spacer(modifier = Modifier.height(4.dp))
                Text(formatSourceLine(article.source, article.published), color = SlateMuted, fontSize = 10.sp,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)

                if (article.tags.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                        Text("${article.tagCount}", color = Violet500, fontSize = 9.sp, fontWeight = FontWeight.Bold,
                            modifier = Modifier.background(Violet500.copy(alpha = 0.15f), RoundedCornerShape(4.dp))
                                .padding(horizontal = 4.dp, vertical = 1.dp))
                        for (tag in article.tags.take(4)) {
                            Text(tag, color = Color(0xFFA78BFA), fontSize = 9.sp,
                                modifier = Modifier.background(Color(0xFF7C3AED).copy(alpha = 0.1f), RoundedCornerShape(4.dp))
                                    .padding(horizontal = 4.dp, vertical = 1.dp), maxLines = 1)
                        }
                        if (article.tags.size > 4) {
                            Text("+${article.tags.size - 4}", color = SlateMuted, fontSize = 9.sp)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(4.dp))
                Text(article.briefSummary, color = Color(0xFFCBD5E1), fontSize = 11.sp,
                    maxLines = 3, overflow = TextOverflow.Ellipsis, lineHeight = 15.sp)
                Spacer(modifier = Modifier.height(8.dp))

                // Audio buttons row: Brief | Full
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Surface(
                        onClick = onSpeakBrief,
                        shape = RoundedCornerShape(6.dp),
                        color = SlateSubtle,
                        modifier = Modifier.weight(1f),
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.Center,
                        ) {
                            Icon(Icons.AutoMirrored.Filled.VolumeUp, "Brief", tint = SlateMuted, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Brief", color = SlateMuted, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                        }
                    }
                    Surface(
                        onClick = onSpeakFull,
                        shape = RoundedCornerShape(6.dp),
                        color = SlateSubtle,
                        modifier = Modifier.weight(1f),
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.Center,
                        ) {
                            Icon(Icons.AutoMirrored.Filled.VolumeUp, "Full", tint = Color.White, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Full", color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                // Action row: Open in browser | Expand | Save | Archive
                var showSaveMenu by remember { mutableStateOf(false) }
                var newGroupName by remember { mutableStateOf("") }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    IconButton(
                        onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(article.url))) },
                        modifier = Modifier.size(28.dp),
                    ) {
                        Icon(Icons.Default.OpenInBrowser, "Read article", tint = SlateMuted, modifier = Modifier.size(16.dp))
                    }
                    IconButton(onClick = onExpand, modifier = Modifier.size(28.dp)) {
                        Icon(Icons.Default.ExpandMore, "Expand", tint = SlateMuted, modifier = Modifier.size(16.dp))
                    }
                    Box {
                        IconButton(
                            onClick = { if (isSaved) onUnsave() else showSaveMenu = true },
                            modifier = Modifier.size(28.dp),
                        ) {
                            Icon(
                                if (isSaved) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                                if (isSaved) "Unsave" else "Save",
                                tint = if (isSaved) Color(0xFFF59E0B) else SlateMuted,
                                modifier = Modifier.size(16.dp),
                            )
                        }
                        androidx.compose.material3.DropdownMenu(
                            expanded = showSaveMenu,
                            onDismissRequest = { showSaveMenu = false; newGroupName = "" },
                        ) {
                            savedCategories.forEach { cat ->
                                androidx.compose.material3.DropdownMenuItem(
                                    text = { Text(cat, fontSize = 13.sp) },
                                    onClick = { onSave(cat); showSaveMenu = false },
                                )
                            }
                            HorizontalDivider(color = SlateSubtle.copy(alpha = 0.5f))
                            Row(
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                OutlinedTextField(
                                    value = newGroupName,
                                    onValueChange = { newGroupName = it },
                                    placeholder = { Text("New group...", fontSize = 12.sp) },
                                    singleLine = true,
                                    modifier = Modifier.width(120.dp).height(40.dp),
                                    textStyle = androidx.compose.ui.text.TextStyle(fontSize = 12.sp, color = Color.White),
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedBorderColor = Violet500,
                                        unfocusedBorderColor = SlateSubtle,
                                        cursorColor = Violet500,
                                    ),
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                TextButton(
                                    onClick = {
                                        if (newGroupName.isNotBlank()) {
                                            onSave(newGroupName.trim())
                                            showSaveMenu = false
                                            newGroupName = ""
                                        }
                                    },
                                    enabled = newGroupName.isNotBlank(),
                                ) {
                                    Text("+", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }
                    IconButton(onClick = onDismiss, modifier = Modifier.size(28.dp)) {
                        Icon(
                            if (dimmed) Icons.Default.Refresh else Icons.Default.Close,
                            if (dimmed) "Restore" else "Archive",
                            tint = if (dimmed) Violet500 else SlateMuted,
                            modifier = Modifier.size(16.dp),
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ArticleDetailSheet(
    article: BriefingArticle,
    viewModel: BriefingViewModel,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val topicColor = TopicColors[article.topic.lowercase()] ?: Violet500

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = SlateCard,
        contentColor = Color.White,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp),
        ) {
            // Image
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(200.dp)
                    .clip(RoundedCornerShape(12.dp)),
            ) {
                AsyncImage(
                    model = ImageRequest.Builder(context)
                        .data(viewModel.getImageUrl(article.id))
                        .crossfade(true)
                        .build(),
                    imageLoader = ApiClient.getAuthenticatedImageLoader(context),
                    contentDescription = article.title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )

                // Topic badge
                Surface(
                    shape = RoundedCornerShape(4.dp),
                    color = topicColor.copy(alpha = 0.9f),
                    modifier = Modifier
                        .padding(8.dp)
                        .align(Alignment.TopStart),
                ) {
                    Text(
                        text = article.topic,
                        color = Color.White,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Headline
            Text(
                text = article.title,
                color = Color.White,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                lineHeight = 26.sp,
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Source + time
            Text(
                text = formatSourceLine(article.source, article.published),
                color = SlateMuted,
                fontSize = 12.sp,
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Full summary (or brief if full not available)
            Text(
                text = article.fullSummary ?: article.briefSummary,
                color = Color(0xFFE2E8F0),
                fontSize = 14.sp,
                lineHeight = 22.sp,
            )

            Spacer(modifier = Modifier.height(20.dp))

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                // Read source
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = Violet500,
                    modifier = Modifier
                        .weight(1f)
                        .clickable {
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(article.url))
                            context.startActivity(intent)
                        },
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            Icons.Default.OpenInBrowser,
                            "Open source",
                            tint = Color.White,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "Read Source",
                            color = Color.White,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }

                // Brief audio
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = SlateSubtle,
                    modifier = Modifier
                        .weight(1f)
                        .clickable { viewModel.speakArticle(article, "brief") },
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.VolumeUp,
                            "Brief summary",
                            tint = Color.White,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            "Brief",
                            color = Color.White,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }

                // Full audio
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = SlateSubtle,
                    modifier = Modifier
                        .weight(1f)
                        .clickable { viewModel.speakArticle(article, "full") },
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.VolumeUp,
                            "Full summary",
                            tint = Color.White,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            "Full",
                            color = Color.White,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
            }
        }
    }
}

private fun formatSourceLine(source: String, published: String): String {
    if (source.isBlank() && published.isBlank()) return ""
    if (published.isBlank()) return source
    val timeAgo = formatTimeAgo(published)
    return if (source.isBlank()) timeAgo else "$source · $timeAgo"
}

private fun formatTimeAgo(published: String): String {
    return try {
        // Try ISO 8601 format
        val formats = listOf(
            SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US),
            SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssZ", java.util.Locale.US),
            SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US),
        )
        var date: java.util.Date? = null
        for (fmt in formats) {
            try {
                date = fmt.parse(published)
                if (date != null) break
            } catch (_: Exception) { }
        }
        if (date == null) return published

        val diffMs = System.currentTimeMillis() - date.time
        val diffMin = diffMs / 60_000
        val diffHours = diffMin / 60
        val diffDays = diffHours / 24

        when {
            diffMin < 1 -> "just now"
            diffMin < 60 -> "${diffMin}m ago"
            diffHours < 24 -> "${diffHours}h ago"
            diffDays < 7 -> "${diffDays}d ago"
            else -> published.take(10)
        }
    } catch (_: Exception) {
        published
    }
}

