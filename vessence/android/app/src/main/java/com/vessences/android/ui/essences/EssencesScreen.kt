package com.vessences.android.ui.essences

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.vessences.android.data.model.Essence

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val Violet500 = Color(0xFFA855F7)
private val SlateText = Color(0xFF94A3B8)
private val SubtleText = Color(0xFF64748B)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EssencesScreen(
    onOpenEssenceView: (String) -> Unit = {},
    viewModel: EssencesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    if (state.selectedEssence != null) {
        EssenceDetailView(
            essence = state.selectedEssence!!,
            actionInProgress = state.actionInProgress,
            onBack = { viewModel.selectEssence(null) },
            onDelete = { viewModel.deleteEssence(it) },
            onOpen = { onOpenEssenceView(it) },
        )
        return
    }

    Scaffold(containerColor = SlateBg) { padding ->
        Column(modifier = Modifier.padding(padding)) {
            // Header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Essences",
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(modifier = Modifier.weight(1f))
                IconButton(onClick = { viewModel.loadEssences() }) {
                    Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = SlateText)
                }
            }

            when {
                state.isLoading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = Violet500)
                    }
                }
                state.error != null -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(state.error!!, color = Color(0xFFF87171), fontSize = 14.sp)
                            Spacer(modifier = Modifier.height(12.dp))
                            TextButton(onClick = { viewModel.loadEssences() }) {
                                Text("Retry", color = Violet500)
                            }
                        }
                    }
                }
                state.essences.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("No essences available", color = SubtleText, fontSize = 14.sp)
                    }
                }
                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(state.essences) { essence ->
                            EssenceListItem(
                                essence = essence,
                                onClick = { viewModel.selectEssence(essence) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EssenceListItem(essence: Essence, onClick: () -> Unit) {
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
            // Installed indicator dot
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .clip(CircleShape)
                    .background(Violet500),
            )
            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = essence.name,
                    color = Color.White,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = essence.roleTitle,
                    color = Violet500,
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = essence.description,
                    color = SubtleText,
                    fontSize = 12.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            Spacer(modifier = Modifier.width(8.dp))

            // Installed badge
            Surface(
                shape = RoundedCornerShape(6.dp),
                color = Violet500.copy(alpha = 0.15f),
            ) {
                Text(
                    text = "Installed",
                    color = Violet500,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EssenceDetailView(
    essence: Essence,
    actionInProgress: String?,
    onBack: () -> Unit,
    onDelete: (String) -> Unit,
    onOpen: (String) -> Unit,
) {
    var showDeleteDialog by remember { mutableStateOf(false) }

    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("Delete Essence") },
            text = { Text("Are you sure you want to delete \"${essence.name}\"?") },
            confirmButton = {
                TextButton(onClick = {
                    showDeleteDialog = false
                    onDelete(essence.name)
                }) {
                    Text("Delete", color = Color(0xFFF87171))
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteDialog = false }) {
                    Text("Cancel")
                }
            },
        )
    }

    Scaffold(
        containerColor = SlateBg,
        topBar = {
            TopAppBar(
                title = { Text(essence.name, color = Color.White) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
                    }
                },
                actions = {
                    IconButton(onClick = { showDeleteDialog = true }) {
                        Icon(Icons.Default.Delete, contentDescription = "Delete", tint = Color(0xFFF87171))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = SlateBg),
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Role & description
            item {
                Surface(shape = RoundedCornerShape(12.dp), color = SlateCard) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(essence.roleTitle, color = Violet500, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(essence.description, color = SlateText, fontSize = 14.sp)
                        Spacer(modifier = Modifier.height(8.dp))
                        Text("UI Type: ${essence.uiType}", color = SubtleText, fontSize = 12.sp)
                    }
                }
            }

            // Open essence view (primary action)
            item {
                Button(
                    onClick = { onOpen(essence.name) },
                    colors = ButtonDefaults.buttonColors(containerColor = Violet500),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                ) {
                    Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null, tint = Color.White)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Open ${essence.name}", color = Color.White)
                }
            }

            // Capabilities
            item {
                Surface(shape = RoundedCornerShape(12.dp), color = SlateCard) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Capabilities", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Spacer(modifier = Modifier.height(10.dp))

                        Text("Provides", color = Violet500, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                        Spacer(modifier = Modifier.height(4.dp))
                        if (essence.capabilities.provides.isEmpty()) {
                            Text("None", color = SubtleText, fontSize = 13.sp)
                        } else {
                            essence.capabilities.provides.forEach { cap ->
                                ChipRow(text = cap)
                            }
                        }

                        Spacer(modifier = Modifier.height(10.dp))
                        Text("Consumes", color = Violet500, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                        Spacer(modifier = Modifier.height(4.dp))
                        if (essence.capabilities.consumes.isEmpty()) {
                            Text("None", color = SubtleText, fontSize = 13.sp)
                        } else {
                            essence.capabilities.consumes.forEach { cap ->
                                ChipRow(text = cap)
                            }
                        }
                    }
                }
            }

            // Permissions
            item {
                Surface(shape = RoundedCornerShape(12.dp), color = SlateCard) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Permissions", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Spacer(modifier = Modifier.height(8.dp))
                        if (essence.permissions.isEmpty()) {
                            Text("No special permissions", color = SubtleText, fontSize = 13.sp)
                        } else {
                            essence.permissions.forEach { perm ->
                                ChipRow(text = perm)
                            }
                        }
                    }
                }
            }

            // Preferred model
            item {
                Surface(shape = RoundedCornerShape(12.dp), color = SlateCard) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Preferred Model", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(essence.preferredModel.modelId, color = Violet500, fontSize = 14.sp)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(essence.preferredModel.reasoning, color = SubtleText, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun ChipRow(text: String) {
    Row(
        modifier = Modifier.padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(5.dp)
                .clip(CircleShape)
                .background(Violet500),
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(text, color = SlateText, fontSize = 13.sp)
    }
}
