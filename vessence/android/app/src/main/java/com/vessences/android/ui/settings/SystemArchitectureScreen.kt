package com.vessences.android.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mikepenz.markdown.m3.Markdown
import com.vessences.android.data.api.DocsApi
import com.vessences.android.data.model.ModelTier
import com.vessences.android.data.repository.DocsCache
import kotlinx.coroutines.launch

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val SlateDark = Color(0xFF020617)
private val Violet400 = Color(0xFFC084FC)
private val SlateMuted = Color(0xFF94A3B8)

/**
 * System Architecture screen — a live hub for Vessence's canonical docs.
 *
 * Replaces the previous 574-line hardcoded Compose content with a pair
 * of screens backed by `/api/docs` and `/api/docs/<slug>`:
 *   - Hub lists docs server-side (title + size + mtime).
 *   - Detail renders the fetched markdown with `compose-markdown`.
 *
 * Doc bodies are cached per APK `versionCode` via [DocsCache] — one
 * network round-trip per doc per app version, instant re-opens until
 * the next bump.
 *
 * The live "LLM Tiers" table is kept as a non-doc section on the hub;
 * it pulls runtime model config from `/api/settings/models` via the
 * existing [SettingsViewModel] rather than a static markdown file.
 */
@Composable
fun SystemArchitectureScreen(
    viewModel: SettingsViewModel,
    onBack: () -> Unit,
) {
    var openSlug by remember { mutableStateOf<String?>(null) }
    val slug = openSlug
    if (slug == null) {
        ArchitectureHub(
            viewModel = viewModel,
            onBack = onBack,
            onOpenDoc = { openSlug = it },
        )
    } else {
        DocDetailPage(
            slug = slug,
            onBack = { openSlug = null },
        )
    }
}

// ── Hub ──────────────────────────────────────────────────────────────────────

@Composable
private fun ArchitectureHub(
    viewModel: SettingsViewModel,
    onBack: () -> Unit,
    onOpenDoc: (String) -> Unit,
) {
    val ctx = LocalContext.current
    val cache = remember(ctx) { DocsCache(ctx) }
    val scope = rememberCoroutineScope()
    var docs by remember { mutableStateOf<List<DocsApi.DocSummary>?>(cache.getList()) }
    var loading by remember { mutableStateOf(docs == null) }
    var error by remember { mutableStateOf<String?>(null) }

    fun refresh(force: Boolean) {
        // Never skip the network call — the list is the freshness signal
        // clients rely on to detect `configs/*.md` edits between APK bumps.
        // Local cache only suppresses the empty-state spinner while we wait.
        loading = docs == null
        error = null
        scope.launch {
            DocsApi.list().fold(
                onSuccess = { fetched ->
                    docs = fetched
                    cache.putList(fetched)
                    // Invalidate cached doc bodies whose server lastModified
                    // has advanced. Next DocDetailPage open will refetch the
                    // stale one(s) — others keep serving from cache.
                    fetched.forEach { summary ->
                        val cached = cache.getDoc(summary.slug) ?: return@forEach
                        if (cached.lastModified != summary.lastModified) {
                            cache.invalidateDoc(summary.slug)
                        }
                    }
                    loading = false
                },
                onFailure = { e ->
                    // Keep any stale cached list; only surface error if we have nothing.
                    if (docs == null) error = e.message ?: "Could not load docs"
                    loading = false
                },
            )
        }
    }

    LaunchedEffect(Unit) { refresh(force = false) }

    val settingsState by viewModel.state.collectAsState()

    Column(modifier = Modifier.fillMaxSize().background(SlateBg)) {
        TopBar("System Architecture", onBack = onBack, trailing = {
            IconButton(onClick = { refresh(force = true) }) {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = Color.White)
            }
        })

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Text(
                    "Canonical docs pulled live from the server. Edit a configs/*.md file — both Android and web reflect it on next open.",
                    color = SlateMuted,
                    fontSize = 13.sp,
                    lineHeight = 19.sp,
                    modifier = Modifier.padding(bottom = 4.dp),
                )
            }

            // Live LLM Tiers — runtime data, not a markdown doc.
            item {
                LlmTiersCard(modelTiers = settingsState.modelTiers)
            }

            item { SectionHeader("DOCUMENTATION") }

            when {
                loading && docs == null -> item { LoadingRow() }
                error != null && docs == null -> item {
                    ErrorRow(message = error!!, onRetry = { refresh(force = true) })
                }
                else -> {
                    items(docs.orEmpty()) { d ->
                        DocRow(doc = d, onClick = { onOpenDoc(d.slug) })
                    }
                }
            }
        }
    }
}

// ── Detail ───────────────────────────────────────────────────────────────────

@Composable
private fun DocDetailPage(
    slug: String,
    onBack: () -> Unit,
) {
    val ctx = LocalContext.current
    val cache = remember(ctx) { DocsCache(ctx) }
    val scope = rememberCoroutineScope()

    var doc by remember(slug) { mutableStateOf<DocsApi.DocBody?>(cache.getDoc(slug)) }
    var loading by remember(slug) { mutableStateOf(doc == null) }
    var error by remember(slug) { mutableStateOf<String?>(null) }

    fun refresh(force: Boolean) {
        if (!force && doc != null) return
        loading = true
        error = null
        scope.launch {
            DocsApi.fetch(slug).fold(
                onSuccess = {
                    doc = it
                    cache.putDoc(it)
                    loading = false
                },
                onFailure = { e ->
                    if (doc == null) error = e.message ?: "Could not load doc"
                    loading = false
                },
            )
        }
    }

    LaunchedEffect(slug) { refresh(force = false) }

    val title = doc?.title ?: slug.replaceFirstChar { it.uppercase() }

    Column(modifier = Modifier.fillMaxSize().background(SlateBg)) {
        TopBar(title, onBack = onBack, trailing = {
            IconButton(onClick = { refresh(force = true) }) {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = Color.White)
            }
        })

        when {
            loading && doc == null -> CenterLoading()
            error != null && doc == null -> CenterError(error!!) { refresh(force = true) }
            doc != null -> DocBody(content = doc!!.content)
            else -> CenterError("No content.") { refresh(force = true) }
        }
    }
}

@Composable
private fun DocBody(content: String) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        // compose-markdown renders headings, lists, tables, code, links.
        // Colors inherit from MaterialTheme — set content color via Surface wrap.
        Surface(color = SlateBg, contentColor = Color(0xFFE2E8F0)) {
            Markdown(content = content)
        }
        Spacer(Modifier.height(32.dp))
    }
}

// ── Pieces ───────────────────────────────────────────────────────────────────

@Composable
private fun TopBar(
    title: String,
    onBack: () -> Unit,
    trailing: @Composable () -> Unit = {},
) {
    Surface(color = SlateBg) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
            }
            Text(
                title,
                color = Color.White,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f),
            )
            trailing()
        }
    }
}

@Composable
private fun SectionHeader(label: String) {
    Text(
        label,
        color = SlateMuted,
        fontSize = 11.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.padding(start = 4.dp, top = 12.dp, bottom = 2.dp),
    )
}

@Composable
private fun DocRow(doc: DocsApi.DocSummary, onClick: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = SlateCard,
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(doc.title, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Text(
                    "${(doc.bytes / 1024).coerceAtLeast(1)} KB",
                    color = SlateMuted,
                    fontSize = 11.sp,
                )
            }
            Icon(Icons.Filled.ChevronRight, contentDescription = null, tint = SlateMuted)
        }
    }
}

@Composable
private fun LlmTiersCard(modelTiers: List<ModelTier>) {
    Surface(shape = RoundedCornerShape(12.dp), color = SlateCard) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text("LLM Tiers (live)", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            if (modelTiers.isEmpty()) {
                Text(
                    "Loading current model configuration…",
                    color = SlateMuted,
                    fontSize = 12.sp,
                )
            } else {
                Surface(shape = RoundedCornerShape(8.dp), color = SlateDark.copy(alpha = 0.4f)) {
                    Column {
                        modelTiers.forEachIndexed { i, tier ->
                            if (i > 0) HorizontalDivider(color = Color(0xFF1E293B).copy(alpha = 0.5f))
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(modifier = Modifier.weight(1.2f)) {
                                    Text(tier.tier, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                                    Text(tier.role, color = SlateMuted, fontSize = 10.sp)
                                }
                                Text(
                                    tier.model,
                                    color = Violet400,
                                    fontSize = 12.sp,
                                    fontFamily = FontFamily.Monospace,
                                    modifier = Modifier.weight(2f),
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun LoadingRow() {
    Row(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator(strokeWidth = 2.dp, color = Violet400)
        Spacer(Modifier.width(12.dp))
        Text("Loading docs…", color = SlateMuted, fontSize = 13.sp)
    }
}

@Composable
private fun ErrorRow(message: String, onRetry: () -> Unit) {
    Surface(shape = RoundedCornerShape(10.dp), color = SlateCard) {
        Column(modifier = Modifier.fillMaxWidth().padding(14.dp)) {
            Text("Couldn't load docs", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            Text(message, color = SlateMuted, fontSize = 12.sp)
            Spacer(Modifier.height(4.dp))
            TextButton(onClick = onRetry) { Text("Retry", color = Violet400) }
        }
    }
}

@Composable
private fun CenterLoading() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(color = Violet400)
    }
}

@Composable
private fun CenterError(message: String, onRetry: () -> Unit) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(message, color = Color.White, fontSize = 14.sp)
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = onRetry) { Text("Retry", color = Violet400) }
        }
    }
}

