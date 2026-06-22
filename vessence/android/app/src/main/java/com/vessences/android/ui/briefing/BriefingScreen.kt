package com.vessences.android.ui.briefing

import android.content.Intent
import android.net.Uri
import java.text.SimpleDateFormat
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
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
import com.vessences.android.data.model.MarketplaceListing
import com.vessences.android.data.model.MarketplaceSearchCard
import java.text.NumberFormat

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

private const val SavedCategorySeparator = " > "

private fun savedCategoryPath(raw: String): String =
    raw.ifBlank { "Uncategorized" }

private fun savedCategoryLabel(path: String): String =
    path.substringAfterLast(SavedCategorySeparator).ifBlank { path }

private fun savedCategoryRoot(path: String): String =
    path.substringBefore(SavedCategorySeparator).ifBlank { "Uncategorized" }

private fun savedParentCategoryPath(path: String): String? {
    val index = path.lastIndexOf(SavedCategorySeparator)
    return if (index > 0) path.substring(0, index) else null
}

private fun savedChildCategoryPath(parent: String, path: String): String? {
    if (path == parent) return null
    val prefix = "$parent$SavedCategorySeparator"
    if (!path.startsWith(prefix)) return null
    val child = path.removePrefix(prefix)
        .substringBefore(SavedCategorySeparator)
        .trim()
    if (child.isBlank()) return null
    return "$parent$SavedCategorySeparator$child"
}

@Composable
fun BriefingScreen(
    onBack: (() -> Unit)? = null,
    viewModel: BriefingViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    val filteredArticles = viewModel.getFilteredArticles()
    val showingMarketplace = state.selectedTab == "Marketplace" && !state.viewingSaved
    var bottomSheetArticle by remember { mutableStateOf<BriefingArticle?>(null) }
    var showHistorySheet by remember { mutableStateOf(false) }

    // When a category filter yields zero loaded matches but more pages exist on the server,
    // eagerly fetch more so the user isn't stuck on a misleading "No articles found".
    LaunchedEffect(state.selectedCategory, filteredArticles.size, state.hasMoreArticles, state.isLoadingMore) {
        if (
            state.selectedCategory != "All" &&
            filteredArticles.isEmpty() &&
            state.hasMoreArticles &&
            !state.isLoadingMore &&
            !state.viewingSaved &&
            state.viewingArchiveDate == null
        ) {
            viewModel.loadMoreArticles()
        }
    }

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
                isLoading = state.isLoading || state.isLoadingArchive || state.isLoadingMarketplace,
                viewingArchive = state.viewingArchiveDate != null,
                onRefresh = { viewModel.refresh(force = true) },
                onShowHistory = { if (!showingMarketplace) showHistorySheet = true },
                showHistory = !showingMarketplace,
            )

            // Top-level modes inside Daily Briefing
            TopicChips(
                topics = listOf("News", "Marketplace"),
                selected = if (state.viewingSaved) "" else state.selectedTab,
                onSelect = {
                    if (state.viewingSaved) viewModel.toggleSavedView()
                    viewModel.selectTab(it)
                    if (it == "News") viewModel.selectCategory("All")
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

            // Saved articles view — two levels: categories grid, then articles in category
            if (state.viewingSaved) {
                if (state.savedFilterCategory == null) {
                    // Level 1: category browser
                    val groups = state.savedArticles
                        .groupBy { savedCategoryRoot(savedCategoryPath(it.category)) }
                        .toList()
                        .sortedByDescending { it.second.size }
                    if (groups.isEmpty()) {
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
                            items(groups, key = { it.first }) { (cat, items) ->
                                Surface(
                                    onClick = { viewModel.openSavedCategory(cat) },
                                    color = SlateCard,
                                    shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp),
                                    border = androidx.compose.foundation.BorderStroke(1.dp, SlateSubtle),
                                    modifier = Modifier.fillMaxWidth(),
                                ) {
                                    Column(modifier = Modifier.padding(16.dp)) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Icon(
                                                Icons.Default.Bookmark,
                                                "Folder",
                                                tint = Color(0xFFF59E0B),
                                                modifier = Modifier.size(18.dp),
                                            )
                                            Spacer(modifier = Modifier.width(6.dp))
                                            Text(
                                                savedCategoryLabel(cat),
                                                color = Color.White,
                                                fontSize = 13.sp,
                                                maxLines = 1,
                                            )
                                        }
                                        Spacer(modifier = Modifier.height(8.dp))
                                        Text(
                                            "${items.size}",
                                            color = Color(0xFFF59E0B),
                                            fontSize = 22.sp,
                                        )
                                        Text(
                                            if (items.size == 1) "article" else "articles",
                                            color = SlateSubtle,
                                            fontSize = 10.sp,
                                        )
                                    }
                                }
                            }
                        }
                    }
                } else {
                    // Level 2+: subcategories and direct articles in the chosen category.
                    val selectedSavedCategory = state.savedFilterCategory ?: ""
                    val childGroups = state.savedArticles
                        .mapNotNull { saved ->
                            val path = savedCategoryPath(saved.category)
                            savedChildCategoryPath(selectedSavedCategory, path)?.let { it to saved }
                        }
                        .groupBy({ it.first }, { it.second })
                        .toList()
                        .sortedByDescending { it.second.size }
                    val directArticles = state.savedArticles.filter {
                        savedCategoryPath(it.category) == selectedSavedCategory
                    }
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        IconButton(onClick = {
                            viewModel.openSavedCategory(savedParentCategoryPath(selectedSavedCategory))
                        }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = Color(0xFFF59E0B))
                        }
                        Text(
                            selectedSavedCategory,
                            color = Color.White,
                            fontSize = 14.sp,
                        )
                    }
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(2),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(childGroups, key = { it.first }) { (cat, items) ->
                            Surface(
                                onClick = { viewModel.openSavedCategory(cat) },
                                color = SlateCard,
                                shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp),
                                border = androidx.compose.foundation.BorderStroke(1.dp, SlateSubtle),
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Column(modifier = Modifier.padding(16.dp)) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(
                                            Icons.Default.Bookmark,
                                            "Folder",
                                            tint = Color(0xFFF59E0B),
                                            modifier = Modifier.size(18.dp),
                                        )
                                        Spacer(modifier = Modifier.width(6.dp))
                                        Text(
                                            savedCategoryLabel(cat),
                                            color = Color.White,
                                            fontSize = 13.sp,
                                            maxLines = 1,
                                        )
                                    }
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Text(
                                        "${items.size}",
                                        color = Color(0xFFF59E0B),
                                        fontSize = 22.sp,
                                    )
                                    Text(
                                        if (items.size == 1) "article" else "articles",
                                        color = SlateSubtle,
                                        fontSize = 10.sp,
                                    )
                                }
                            }
                        }
                        items(directArticles, key = { it.articleId }) { saved ->
                            saved.article?.let { article ->
                                ArticleCard(
                                    article = article,
                                    imageUrl = viewModel.getImageUrl(article.id),
                                    isSaved = true,
                                    onExpand = { bottomSheetArticle = article },
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
            else if (showingMarketplace) {
                when {
                    state.marketplaceError != null && state.marketplaceSearches.isEmpty() -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center,
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(
                                    state.marketplaceError ?: "Marketplace unavailable",
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
                    state.isLoadingMarketplace && state.marketplaceSearches.isEmpty() -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center,
                        ) {
                            CircularProgressIndicator(color = Violet500)
                        }
                    }
                    state.marketplaceSearches.isEmpty() -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center,
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(
                                    "No marketplace searches yet",
                                    color = SlateMuted,
                                    fontSize = 14.sp,
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    "Create a saved Marketplace search first",
                                    color = SlateSubtle,
                                    fontSize = 12.sp,
                                )
                            }
                        }
                    }
                    else -> {
                        MarketplaceGrid(
                            cards = state.marketplaceSearches,
                            viewModel = viewModel,
                        )
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
                    onSpeakFull = { viewModel.speakArticle(it, "full") },
                    onDismiss = { viewModel.dismissArticle(it.id) },
                )
            }
        }

        // FAB - Read All / Stop Audio
        if (!showingMarketplace) {
            Column(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(16.dp),
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FloatingActionButton(
                    onClick = {
                        if (state.isSpeaking) viewModel.stopSpeaking()
                        else viewModel.readAll()
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
    showHistory: Boolean,
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

        if (showHistory) {
            IconButton(onClick = onShowHistory) {
                Icon(
                    Icons.Default.History,
                    "History",
                    tint = if (viewingArchive) Violet500 else Color.White,
                )
            }
        } else {
            Spacer(modifier = Modifier.width(48.dp))
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
private fun MarketplaceGrid(
    cards: List<MarketplaceSearchCard>,
    viewModel: BriefingViewModel,
) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(1),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        items(cards, key = { it.search.name }) { card ->
            MarketplaceSearchPanel(
                card = card,
                viewModel = viewModel,
            )
        }
    }
}

@Composable
private fun MarketplaceSearchPanel(
    card: MarketplaceSearchCard,
    viewModel: BriefingViewModel,
) {
    val context = LocalContext.current
    val listings = card.listings.take(4)
    val refreshTint = when (card.refreshStatus.state) {
        "running" -> Color(0xFFF59E0B)
        "error" -> Color(0xFFEF4444)
        else -> SlateMuted
    }

    Surface(
        shape = RoundedCornerShape(16.dp),
        color = SlateCard,
        shadowElevation = 2.dp,
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = card.search.label.ifBlank { card.search.name },
                        color = Color.White,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "${card.search.passedCount} matches · ${formatMarketplaceTimestamp(card.search.lastRefreshed)}",
                        color = SlateMuted,
                        fontSize = 11.sp,
                    )
                }
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = refreshTint.copy(alpha = 0.15f),
                ) {
                    Text(
                        text = card.refreshStatus.state.replace('_', ' '),
                        color = refreshTint,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                    )
                }
            }

            if (card.search.queries.isNotEmpty()) {
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    modifier = Modifier.horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    card.search.queries.forEach { query ->
                        Surface(
                            shape = RoundedCornerShape(999.dp),
                            color = Violet500.copy(alpha = 0.12f),
                        ) {
                            Text(
                                text = query,
                                color = Color(0xFFD8B4FE),
                                fontSize = 11.sp,
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = card.summary?.summary?.takeIf { !it.isNullOrBlank() }
                    ?: "No AI brief yet. Pull Marketplace data to generate one.",
                color = Color(0xFFE2E8F0),
                fontSize = 13.sp,
                lineHeight = 19.sp,
            )

            if (!card.refreshStatus.error.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = card.refreshStatus.error ?: "",
                    color = Color(0xFFFCA5A5),
                    fontSize = 11.sp,
                )
            }

            if (listings.isNotEmpty()) {
                Spacer(modifier = Modifier.height(14.dp))
                Text(
                    text = "Top Listings",
                    color = Color.White,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(8.dp))
                listings.forEachIndexed { index, listing ->
                    MarketplaceListingRow(
                        searchName = card.search.name,
                        listing = listing,
                        imageUrl = viewModel.getMarketplaceImageUrl(card.search.name, listing),
                        onClick = {
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(listing.url)))
                        },
                    )
                    if (index != listings.lastIndex) {
                        HorizontalDivider(
                            color = SlateSubtle.copy(alpha = 0.5f),
                            modifier = Modifier.padding(vertical = 8.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun MarketplaceListingRow(
    searchName: String,
    listing: MarketplaceListing,
    imageUrl: String?,
    onClick: () -> Unit,
) {
    val context = LocalContext.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
            .padding(2.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(width = 92.dp, height = 72.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(SlateSubtle),
        ) {
            if (imageUrl != null) {
                AsyncImage(
                    model = ImageRequest.Builder(context)
                        .data(imageUrl)
                        .crossfade(true)
                        .build(),
                    imageLoader = ApiClient.getAuthenticatedImageLoader(context),
                    contentDescription = "${listing.title} photo",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            } else {
                Text(
                    text = searchName.replaceFirstChar { it.uppercase() },
                    color = SlateMuted,
                    fontSize = 12.sp,
                    modifier = Modifier.align(Alignment.Center),
                )
            }
        }

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = formatMarketplacePrice(listing.price),
                color = Color(0xFFFDE68A),
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = listing.title,
                color = Color.White,
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = formatMarketplaceMeta(listing),
                color = SlateMuted,
                fontSize = 10.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (!listing.location.isBlank()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = listing.location,
                    color = SlateSubtle,
                    fontSize = 10.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Icon(
            Icons.Default.OpenInBrowser,
            contentDescription = "Open listing",
            tint = SlateMuted,
            modifier = Modifier.size(16.dp),
        )
    }
}

@Composable
private fun ArticleGrid(
    articles: List<BriefingArticle>,
    viewModel: BriefingViewModel,
    onExpand: (BriefingArticle) -> Unit,
    onSpeakFull: (BriefingArticle) -> Unit,
    onDismiss: (BriefingArticle) -> Unit,
) {
    val gridState = rememberLazyGridState()
    val state by viewModel.state.collectAsState()

    LaunchedEffect(gridState, articles.size, state.hasMoreArticles) {
        snapshotFlow {
            val last = gridState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: -1
            last >= articles.size - 6
        }
            .distinctUntilChanged()
            .collectLatest { nearEnd ->
                if (nearEnd && state.hasMoreArticles && !state.isLoadingMore) {
                    viewModel.loadMoreArticles()
                }
            }
    }

    LazyVerticalGrid(
        state = gridState,
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

                // Full summary audio
                Surface(
                    onClick = onSpeakFull,
                    shape = RoundedCornerShape(6.dp),
                    color = SlateSubtle,
                    modifier = Modifier.fillMaxWidth(),
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
    var detailArticle by remember(article.id) { mutableStateOf(article) }
    var loadingFullSummary by remember(article.id) { mutableStateOf(article.fullSummary.isNullOrBlank()) }
    var detailError by remember(article.id) { mutableStateOf<String?>(null) }

    LaunchedEffect(article.id) {
        if (article.fullSummary.isNullOrBlank()) {
            loadingFullSummary = true
            detailError = null
            runCatching { viewModel.getArticleDetail(article) }
                .onSuccess { detailArticle = it }
                .onFailure { detailError = "Full summary unavailable." }
            loadingFullSummary = false
        }
    }

    val shownArticle = detailArticle
    val topicColor = TopicColors[shownArticle.topic.lowercase()] ?: Violet500

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = SlateCard,
        contentColor = Color.White,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
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
                        .data(viewModel.getImageUrl(shownArticle.id))
                        .crossfade(true)
                        .build(),
                    imageLoader = ApiClient.getAuthenticatedImageLoader(context),
                    contentDescription = shownArticle.title,
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
                        text = shownArticle.topic,
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
                text = shownArticle.title,
                color = Color.White,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                lineHeight = 26.sp,
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Source + time
            Text(
                text = formatSourceLine(shownArticle.source, shownArticle.published),
                color = SlateMuted,
                fontSize = 12.sp,
            )

            Spacer(modifier = Modifier.height(16.dp))

            when {
                loadingFullSummary -> {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        CircularProgressIndicator(
                            color = Violet500,
                            strokeWidth = 2.dp,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            text = "Loading full summary...",
                            color = SlateMuted,
                            fontSize = 14.sp,
                        )
                    }
                }
                shownArticle.fullSummary.isNullOrBlank() -> {
                    Text(
                        text = detailError ?: "Full summary unavailable.",
                        color = SlateMuted,
                        fontSize = 14.sp,
                        lineHeight = 22.sp,
                    )
                }
                else -> {
                    Text(
                        text = shownArticle.fullSummary ?: "",
                        color = Color(0xFFE2E8F0),
                        fontSize = 14.sp,
                        lineHeight = 22.sp,
                    )
                }
            }

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
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(shownArticle.url))
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
                            "Source",
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
                        .clickable { viewModel.speakArticle(shownArticle, "full") },
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

private fun formatMarketplacePrice(price: Int?): String {
    if (price == null || price <= 0) return "Price unavailable"
    return NumberFormat.getCurrencyInstance().format(price)
}

private fun formatMarketplaceMeta(listing: MarketplaceListing): String {
    val parts = buildList {
        listing.year?.takeIf { it > 0 }?.let { add(it.toString()) }
        listing.miles?.takeIf { it > 0 }?.let { add("${NumberFormat.getIntegerInstance().format(it)} mi") }
        listing.query?.takeIf { it.isNotBlank() }?.let { add(it) }
    }
    return parts.joinToString(" · ")
}

private fun formatMarketplaceTimestamp(raw: String?): String {
    if (raw.isNullOrBlank()) return "not refreshed yet"
    return "updated ${formatTimeAgo(raw)}"
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
