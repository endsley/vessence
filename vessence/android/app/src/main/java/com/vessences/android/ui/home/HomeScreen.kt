package com.vessences.android.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.ui.layout.ContentScale
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Newspaper
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Work
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.vessences.android.data.api.AppVersion
import com.vessences.android.data.api.UpdateManager
import com.vessences.android.data.repository.FileRepository
import com.vessences.android.data.repository.VoiceSettingsRepository
import com.vessences.android.ui.essences.EssencesViewModel
import com.vessences.android.voice.AlwaysListeningService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val Violet500 = Color(0xFFA855F7)
private val Violet400 = Color(0xFFC084FC)
private val SlateMuted = Color(0xFF94A3B8)
private val SubtleText = Color(0xFF64748B)
private val SectionLabel = Color(0xFF94A3B8)

data class HomeEssenceCard(
    val name: String,
    val description: String,
    val icon: ImageVector,
    val iconTint: Color,
    val isProminent: Boolean = false,
)

@Composable
fun HomeScreen(
    onNavigateToJane: () -> Unit,
    onNavigateToEssenceView: (String) -> Unit,
    onNavigateToSettings: () -> Unit,
    onNavigateToSystemArchitecture: () -> Unit,
) {
    val essencesViewModel: EssencesViewModel = viewModel()
    val essencesState by essencesViewModel.state.collectAsState()

    // Update check
    var availableUpdate by remember { mutableStateOf<AppVersion?>(null) }
    var updateDismissed by remember { mutableStateOf(false) }
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        availableUpdate = UpdateManager.checkForUpdate(context)
    }

    // Prefetch vault root directory so Life Librarian loads instantly
    LaunchedEffect(Unit) {
        withContext(Dispatchers.IO) {
            try {
                FileRepository.getInstance().listDirectory("")
            } catch (_: Exception) { }
        }
    }

    // Built-in cards: Jane first, Work Log separated (always last)
    val builtInCards = listOf(
        HomeEssenceCard(
            name = "Jane",
            description = "Your personal genie",
            icon = Icons.Default.Psychology,
            iconTint = Violet500,
            isProminent = true,
        ),
        HomeEssenceCard(
            name = "Life Librarian",
            description = "Your files and documents",
            icon = Icons.Default.Description,
            iconTint = Color(0xFF3B82F6),
        ),
        HomeEssenceCard(
            name = "Music Playlist",
            description = "Your music collection",
            icon = Icons.Default.MusicNote,
            iconTint = Color(0xFF22C55E),
        ),
        HomeEssenceCard(
            name = "Daily Briefing",
            description = "Personalized news digest",
            icon = Icons.Default.Newspaper,
            iconTint = Color(0xFFF97316),
        ),
        HomeEssenceCard(
            name = "System Architecture",
            description = "Current models and memory",
            icon = Icons.Default.AutoAwesome,
            iconTint = Color(0xFFC084FC),
        ),
    )

    val workLogCard = HomeEssenceCard(
        name = "Work Log",
        description = "Activity feed",
        icon = Icons.Default.Work,
        iconTint = Color(0xFFF59E0B),
    )

    // API essences (exclude duplicates of built-in names + Work Log)
    val builtInNames = (builtInCards.map { it.name } + "Work Log").toSet()
    val apiEssences = essencesState.essences.filter { it.name !in builtInNames }

    val voiceSettings = remember { VoiceSettingsRepository(context) }
    var isListeningActive by remember { mutableStateOf(voiceSettings.isAlwaysListeningEnabled()) }

    Box(modifier = Modifier.fillMaxSize()) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg),
    ) {
        // Update banner
        if (availableUpdate != null && !updateDismissed) {
            UpdateBanner(
                version = availableUpdate!!,
                onInstall = {
                    UpdateManager.downloadAndInstall(
                        context,
                        availableUpdate!!.downloadUrl,
                        availableUpdate!!.versionName,
                    )
                },
                onDismiss = { updateDismissed = true },
            )
        }

        // Top bar: title + settings gear
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = "Vessence",
                    color = Color.White,
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(modifier = Modifier.width(6.dp))
                val versionName = try {
                    context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: ""
                } catch (_: Exception) { "" }
                if (versionName.isNotEmpty()) {
                    Text(
                        text = "v$versionName",
                        color = SlateMuted,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(bottom = 3.dp),
                    )
                }
            }
            IconButton(onClick = onNavigateToSettings) {
                Icon(
                    imageVector = Icons.Default.Settings,
                    contentDescription = "Settings",
                    tint = SlateMuted,
                )
            }
        }

        // Subtitle
        Text(
            text = "Your personal AI",
            color = SlateMuted,
            fontSize = 15.sp,
            modifier = Modifier.padding(horizontal = 16.dp),
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Split API items into tools and essences by type
        val apiTools = apiEssences.filter { it.type != "essence" }
        val apiEssenceItems = apiEssences.filter { it.type == "essence" }

        // Cards list
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // ── Jane (always first, prominent) ──
            item {
                ProminentEssenceCard(
                    card = builtInCards.first(), // Jane
                    onClick = { onNavigateToJane() },
                )
            }

            // ── Tools section ──
            item {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "TOOLS",
                    color = SectionLabel,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp,
                    modifier = Modifier.padding(vertical = 4.dp),
                )
            }

            // Built-in tool cards (Life Librarian, Music Playlist, Briefing, System Architecture)
            items(builtInCards.drop(1)) { card ->
                StandardEssenceCard(
                    card = card,
                    onClick = {
                        if (card.name == "System Architecture") onNavigateToSystemArchitecture()
                        else onNavigateToEssenceView(card.name)
                    },
                )
            }

            // API tools
            if (essencesState.isLoading) {
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(24.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(
                            color = Violet500,
                            modifier = Modifier.size(24.dp),
                        )
                    }
                }
            } else if (apiTools.isNotEmpty()) {
                items(apiTools) { tool ->
                    StandardEssenceCard(
                        card = HomeEssenceCard(
                            name = tool.name,
                            description = tool.roleTitle.ifBlank { tool.description },
                            icon = Icons.Default.Psychology,
                            iconTint = Violet500,
                        ),
                        onClick = { onNavigateToEssenceView(tool.name) },
                    )
                }
            }

            // ── Essences section (AI agents — violet accent) ──
            if (apiEssenceItems.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "ESSENCES",
                        color = Violet400,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp,
                        modifier = Modifier.padding(vertical = 4.dp),
                    )
                }

                items(apiEssenceItems) { essence ->
                    EssenceAgentCard(
                        card = HomeEssenceCard(
                            name = essence.name,
                            description = essence.roleTitle.ifBlank { essence.description },
                            icon = Icons.Default.AutoAwesome,
                            iconTint = Violet400,
                        ),
                        onClick = { onNavigateToEssenceView(essence.name) },
                    )
                }
            }

            // Work Log — always last
            item {
                StandardEssenceCard(
                    card = workLogCard,
                    onClick = { onNavigateToEssenceView("Work Log") },
                )
            }

            // Bottom spacing
            item { Spacer(modifier = Modifier.height(80.dp)) }
        }
    }

    // Stop-listening control lives in the chat view (bottom "Stop speaking" button).
    // No need for a separate FAB on the home screen.
    } // Box
}

@Composable
private fun ProminentEssenceCard(
    card: HomeEssenceCard,
    onClick: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        color = SlateCard,
        shadowElevation = 4.dp,
    ) {
        Row(
            modifier = Modifier.padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Large icon — use Jane's photo for "Jane", icon circle for others
            if (card.name == "Jane") {
                val janeUrl = "${com.vessences.android.data.api.ApiClient.getJaneBaseUrl()}/api/files/serve/images/people/jane/jane1.png"
                val imgContext = LocalContext.current
                val imageLoader = remember { com.vessences.android.data.api.ApiClient.getAuthenticatedImageLoader(imgContext) }
                coil.compose.SubcomposeAsyncImage(
                    model = coil.request.ImageRequest.Builder(imgContext)
                        .data(janeUrl)
                        .crossfade(true)
                        .build(),
                    imageLoader = imageLoader,
                    contentDescription = "Jane",
                    modifier = Modifier
                        .size(52.dp)
                        .clip(CircleShape),
                    contentScale = ContentScale.Crop,
                    loading = {
                        Box(
                            modifier = Modifier.size(52.dp).clip(CircleShape)
                                .background(card.iconTint.copy(alpha = 0.15f)),
                            contentAlignment = Alignment.Center,
                        ) { Icon(card.icon, null, tint = card.iconTint, modifier = Modifier.size(28.dp)) }
                    },
                    error = {
                        Box(
                            modifier = Modifier.size(52.dp).clip(CircleShape)
                                .background(card.iconTint.copy(alpha = 0.15f)),
                            contentAlignment = Alignment.Center,
                        ) { Icon(card.icon, null, tint = card.iconTint, modifier = Modifier.size(28.dp)) }
                    },
                )
            } else {
                Box(
                    modifier = Modifier
                        .size(52.dp)
                        .clip(CircleShape)
                        .background(card.iconTint.copy(alpha = 0.15f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = card.icon,
                        contentDescription = null,
                        tint = card.iconTint,
                        modifier = Modifier.size(28.dp),
                    )
                }
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = card.name,
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = card.description,
                    color = SlateMuted,
                    fontSize = 14.sp,
                )
            }
        }
    }
}

@Composable
private fun StandardEssenceCard(
    card: HomeEssenceCard,
    onClick: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        color = SlateCard,
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(card.iconTint.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = card.icon,
                    contentDescription = null,
                    tint = card.iconTint,
                    modifier = Modifier.size(22.dp),
                )
            }
            Spacer(modifier = Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = card.name,
                    color = Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = card.description,
                    color = SubtleText,
                    fontSize = 13.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun EssenceAgentCard(
    card: HomeEssenceCard,
    onClick: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = Violet400.copy(alpha = 0.35f),
                shape = RoundedCornerShape(12.dp),
            )
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF1E1B2E), // Subtle violet-tinted dark card
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(Violet400.copy(alpha = 0.18f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = card.icon,
                    contentDescription = null,
                    tint = Violet400,
                    modifier = Modifier.size(22.dp),
                )
            }
            Spacer(modifier = Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = card.name,
                        color = Color.White,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "AI",
                        color = Violet400,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Text(
                    text = card.description,
                    color = SubtleText,
                    fontSize = 13.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun UpdateBanner(
    version: AppVersion,
    onInstall: () -> Unit,
    onDismiss: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onInstall),
        color = Color(0xFF1E3A5F),
        shape = RoundedCornerShape(0.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Update available: v${version.versionName}",
                    color = Color.White,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                if (version.changelog.isNotBlank()) {
                    Text(
                        text = version.changelog,
                        color = SlateMuted,
                        fontSize = 12.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            Text(
                text = "Tap to install",
                color = Violet500,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(start = 8.dp),
            )
            IconButton(
                onClick = onDismiss,
                modifier = Modifier.size(28.dp),
            ) {
                Icon(
                    Icons.Default.Close,
                    contentDescription = "Dismiss",
                    tint = SlateMuted,
                    modifier = Modifier.size(16.dp),
                )
            }
        }
    }
}
