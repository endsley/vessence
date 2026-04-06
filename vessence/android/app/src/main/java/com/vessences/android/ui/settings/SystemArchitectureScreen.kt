package com.vessences.android.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val SlateDark = Color(0xFF020617)
private val Violet500 = Color(0xFFA855F7)
private val Violet400 = Color(0xFFC084FC)
private val SlateMuted = Color(0xFF94A3B8)
private val Blue500 = Color(0xFF3B82F6)
private val Green500 = Color(0xFF22C55E)
private val Amber500 = Color(0xFFF59E0B)
private val Red500 = Color(0xFFEF4444)
private val Cyan500 = Color(0xFF06B6D4)

@Composable
fun SystemArchitectureScreen(
    viewModel: SettingsViewModel,
    onBack: () -> Unit
) {
    var currentPage by remember { mutableStateOf("hub") }

    when (currentPage) {
        "hub" -> ArchitectureHub(viewModel, onBack) { currentPage = it }
        "overview" -> DetailPage("How Vessence Works", onBack = { currentPage = "hub" }) { OverviewContent() }
        "jane" -> DetailPage("Jane — Your AI Partner", onBack = { currentPage = "hub" }) { JaneContent() }
        "llm_tiers" -> DetailPage("LLM Tiers", onBack = { currentPage = "hub" }) { LlmTiersContent(viewModel) }
        "memory" -> DetailPage("Memory System", onBack = { currentPage = "hub" }) { MemoryContent() }
        "essences" -> DetailPage("Essences", onBack = { currentPage = "hub" }) { EssencesContent() }
        "vault" -> DetailPage("The Vault", onBack = { currentPage = "hub" }) { VaultContent() }
        "standing_brain" -> DetailPage("Standing Brain", onBack = { currentPage = "hub" }) { StandingBrainContent() }
        "provider_switch" -> DetailPage("Provider Switching", onBack = { currentPage = "hub" }) { ProviderSwitchContent() }
        "docker" -> DetailPage("Docker Deployment", onBack = { currentPage = "hub" }) { DockerContent() }
        "cron" -> DetailPage("Nightly Jobs", onBack = { currentPage = "hub" }) { CronContent() }
        "security" -> DetailPage("Security & Auth", onBack = { currentPage = "hub" }) { SecurityContent() }
    }
}

// ── Hub Page ─────────────────────────────────────────────────────────────────

@Composable
private fun ArchitectureHub(
    viewModel: SettingsViewModel,
    onBack: () -> Unit,
    onNavigate: (String) -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize().background(SlateBg)
    ) {
        // Top Bar
        Surface(color = SlateBg) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = Color.White)
                }
                Text("System Architecture", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            }
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            item {
                Text(
                    "Vessence is a personal AI system with two agents, a shared memory, and modular skills called Essences. Tap any section to learn more.",
                    color = SlateMuted, fontSize = 13.sp, lineHeight = 19.sp,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
            }

            // Getting Started
            item { SectionHeader("GETTING STARTED") }
            item {
                NavCard(
                    title = "How Vessence Works",
                    subtitle = "The big picture — what Vessence is and how all the pieces fit together",
                    color = Violet500,
                    onClick = { onNavigate("overview") }
                )
            }

            // Core Agents
            item { SectionHeader("CORE AGENTS") }
            item {
                NavCard(
                    title = "Jane — Your AI Partner",
                    subtitle = "Reasoning, code, research, architecture. The brain you're talking to right now.",
                    color = Violet500,
                    onClick = { onNavigate("jane") }
                )
            }
            item {
                NavCard(
                    title = "Essences",
                    subtitle = "Modular AI personas — Daily Briefing, Life Librarian, Tax Accountant, and more",
                    color = Blue500,
                    onClick = { onNavigate("essences") }
                )
            }

            // Intelligence
            item { SectionHeader("INTELLIGENCE") }
            item {
                NavCard(
                    title = "LLM Tiers",
                    subtitle = "Four tiers of AI models — from the powerful Orchestrator to fast local models",
                    color = Amber500,
                    onClick = { onNavigate("llm_tiers") }
                )
            }
            item {
                NavCard(
                    title = "Memory System",
                    subtitle = "How Jane remembers everything — permanent, long-term, short-term, and file memories",
                    color = Green500,
                    onClick = { onNavigate("memory") }
                )
            }
            item {
                NavCard(
                    title = "Jane's Mind (Standing Brain)",
                    subtitle = "The deep reasoning half of Jane — a long-lived CLI process kept warm so there's no cold start between messages",
                    color = Cyan500,
                    onClick = { onNavigate("standing_brain") }
                )
            }

            // Infrastructure
            item { SectionHeader("INFRASTRUCTURE") }
            item {
                NavCard(
                    title = "The Vault",
                    subtitle = "Your personal file storage — documents, photos, music, all searchable by AI",
                    color = Blue500,
                    onClick = { onNavigate("vault") }
                )
            }
            item {
                NavCard(
                    title = "Provider Switching",
                    subtitle = "Seamlessly switch between Claude, Gemini, and OpenAI — even mid-conversation",
                    color = Amber500,
                    onClick = { onNavigate("provider_switch") }
                )
            }
            item {
                NavCard(
                    title = "Docker Deployment",
                    subtitle = "How Vessence runs in containers — 3 services, 210 MB download, one-click install",
                    color = Cyan500,
                    onClick = { onNavigate("docker") }
                )
            }
            item {
                NavCard(
                    title = "Nightly Jobs",
                    subtitle = "What happens while you sleep — news briefing, memory cleanup, backups, and more",
                    color = Green500,
                    onClick = { onNavigate("cron") }
                )
            }
            item {
                NavCard(
                    title = "Security & Auth",
                    subtitle = "Google OAuth, trusted devices, per-user data isolation, and tool approval gates",
                    color = Red500,
                    onClick = { onNavigate("security") }
                )
            }

            item { Spacer(modifier = Modifier.height(24.dp)) }
        }
    }
}

// ── Reusable Components ──────────────────────────────────────────────────────

@Composable
private fun SectionHeader(text: String) {
    Text(
        text = text,
        color = SlateMuted,
        fontSize = 11.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = 1.sp,
        modifier = Modifier.padding(top = 8.dp)
    )
}

@Composable
private fun NavCard(title: String, subtitle: String, color: Color, onClick: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = SlateCard,
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier.size(8.dp).background(color, CircleShape)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(title, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(2.dp))
                Text(subtitle, color = SlateMuted, fontSize = 12.sp, lineHeight = 17.sp)
            }
            Icon(Icons.Default.ChevronRight, "Open", tint = SlateMuted, modifier = Modifier.size(20.dp))
        }
    }
}

@Composable
private fun DetailPage(title: String, onBack: () -> Unit, content: @Composable () -> Unit) {
    Column(modifier = Modifier.fillMaxSize().background(SlateBg)) {
        Surface(color = SlateBg) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = Color.White)
                }
                Text(title, color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }
        }
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item { content() }
        }
    }
}

@Composable
private fun InfoCard(title: String? = null, content: String, accentColor: Color = Violet400) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = SlateCard
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            if (title != null) {
                Text(title, color = accentColor, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(6.dp))
            }
            Text(content, color = Color(0xFFCBD5E1), fontSize = 13.sp, lineHeight = 20.sp)
        }
    }
}

@Composable
private fun BulletList(items: List<Pair<String, String>>, accentColor: Color = Violet500) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items.forEach { (title, desc) ->
            Row(verticalAlignment = Alignment.Top) {
                Box(modifier = Modifier.padding(top = 6.dp).size(6.dp).background(accentColor, CircleShape))
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(title, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                    Text(desc, color = SlateMuted, fontSize = 13.sp, lineHeight = 18.sp)
                }
            }
        }
    }
}

// ── Detail Page Content ──────────────────────────────────────────────────────

@Composable
private fun OverviewContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "What is Vessence?",
            content = "Vessence is your personal AI system that runs on your own computer. It has two AI agents — Jane and Amber — that share a memory and work together to help you with everything from coding and research to daily news and file management."
        )
        InfoCard(
            title = "The Two Agents",
            content = "Jane handles technical work: reasoning, code, architecture, and research. She uses powerful cloud AI models (Claude, Gemini, or OpenAI) and can switch between them.\n\nAmber handles everyday companionship: casual chat, reminders, and personal tasks. She runs on Google's Gemini."
        )
        InfoCard(
            title = "How a Message Flows",
            content = "1. You send a message from the app or web\n2. A tiny local AI (Gemma 4B) classifies it as easy, medium, or hard\n3. Jane picks the right AI model for the job\n4. Your memory and context are loaded from ChromaDB\n5. The AI generates a response, streaming it to you in real-time\n6. The conversation is saved to memory for next time"
        )
        InfoCard(
            title = "Essences — Modular Skills",
            content = "Essences are like apps within Vessence. Each one is a specialized AI persona with its own memory, tools, and knowledge. Examples: Daily Briefing reads the news, Life Librarian manages your files, Tax Accountant helps with taxes. You can build custom essences or download them from the marketplace."
        )
        InfoCard(
            title = "Everything Stays Yours",
            content = "All your data lives on your machine — files in the Vault, memories in ChromaDB, configs in .env files. Nothing is sent to Vessence servers. The only external calls are to the AI providers (Claude/Gemini/OpenAI) for generating responses."
        )
    }
}

@Composable
private fun JaneContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "Who is Jane?",
            content = "Jane is your personal AI partner — not a subordinate, but an equal collaborator. She handles reasoning, coding, systems architecture, research, and anything that requires deep thinking. She remembers your preferences, your projects, and your history across every conversation."
        )
        InfoCard(
            title = "How Jane Thinks",
            content = "Jane has two halves that work together as one agent:\n\n• Jane's initial ack — the fast front half. Speaks first within a second or two, handles simple things like greetings, trivia, and unit conversions on her own, and for bigger questions says something like \"give me a minute on this\" before handing off.\n\n• Jane's mind — the deep-reasoning half. A long-lived CLI process (the 'Standing Brain') kept warm between messages so there's no cold-start delay. This is where code, research, and real problem-solving happen.\n\nFor complex questions, Jane shows you her thinking process: what files she's reading, what tools she's using, and what she's reasoning about. These appear as collapsible steps in the chat."
        )
        InfoCard(
            title = "Jane's Tools",
            content = "Jane can read and write files, search the web, run shell commands, search your codebase, manage your Vault, and build new Essences. On the web interface, dangerous operations (like deleting files) require your explicit approval."
        )
        InfoCard(
            title = "Voice Mode",
            content = "When TTS is enabled, Jane switches to a conversational style — short 2-5 sentence answers spoken aloud. She knows to keep it brief for listening and detailed for reading. You can toggle this per-conversation on both Android and web."
        )
        InfoCard(
            title = "Context Builder",
            content = "Before each response, Jane assembles a context package: your user profile, relevant memories from ChromaDB, recent conversation history, active task state, and any file context you've attached. This is injected as the system prompt on the first message; subsequent messages reuse the existing session."
        )
    }
}

@Composable
private fun LlmTiersContent(viewModel: SettingsViewModel) {
    val state by viewModel.state.collectAsState()
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            content = "Vessence uses four tiers of AI models. Each tier is optimized for different tasks — powerful models for hard problems, fast models for quick tasks, and local models for privacy-sensitive work."
        )
        // Live tier table
        if (state.modelTiers.isNotEmpty()) {
            Surface(shape = RoundedCornerShape(12.dp), color = SlateDark.copy(alpha = 0.4f)) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth().background(SlateCard.copy(alpha = 0.5f)).padding(horizontal = 12.dp, vertical = 8.dp)
                    ) {
                        Text("Tier", color = SlateMuted, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1.2f))
                        Text("Current Model", color = SlateMuted, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(2f))
                    }
                    state.modelTiers.forEach { tier ->
                        HorizontalDivider(color = Color(0xFF1E293B).copy(alpha = 0.5f))
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1.2f)) {
                                Text(tier.tier, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                                Text(tier.role, color = SlateMuted, fontSize = 10.sp)
                            }
                            Text(tier.model, color = Violet400, fontSize = 12.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.weight(2f))
                        }
                    }
                }
            }
        }
        BulletList(listOf(
            "Orchestrator" to "The main brain you talk to. Handles complex reasoning, coding, and architecture decisions. Uses the most capable model available.",
            "Agent" to "Specialist workers for research, memory retrieval, and multi-step tasks. Runs in the background when Jane needs help.",
            "Utility" to "Fast, cheap models for high-volume tasks: memory archival, message classification, formatting. Runs hundreds of times per day.",
            "Local" to "Runs on your machine via Ollama. Used for privacy-sensitive classification, memory librarian synthesis, and fast intent detection. No data leaves your computer."
        ))
    }
}

@Composable
private fun MemoryContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "How Jane Remembers",
            content = "Jane's memory lives in ChromaDB — a vector database that stores facts as searchable embeddings. When you send a message, Jane searches for relevant memories and weaves them into her response. This is how she remembers your name, your projects, and things you told her weeks ago."
        )
        InfoCard(title = "Memory Tiers", content = "Memories are organized into four tiers, each serving a different purpose:")
        BulletList(listOf(
            "Permanent" to "Core identity — your name, family, preferences, and explicit instructions. Never expires. Shared between Jane and Amber.",
            "Long-Term" to "Significant decisions and architectural changes. Written by the Thematic Archivist after each session. Persists indefinitely.",
            "Short-Term" to "Recent conversation context and work-in-progress notes. Auto-expires after 14 days to prevent memory bloat.",
            "File Index" to "Descriptions of every file in your Vault, generated from content analysis. Only queried when you ask about files."
        ), accentColor = Green500)
        InfoCard(
            title = "The Thematic Archivist",
            content = "After each session, the Archivist reads the full transcript to identify 'Arcs of Lasting Value'. Before saving, it performs a 'Look-Before-Leap' check: comparing new arcs against existing memories to decide whether to MERGE them into a master record or add them as a NEW entry. This ensures LTM evolves into comprehensive knowledge rather than fragmented snippets."
        )
        InfoCard(
            title = "Speed Optimizations",
            content = "Simple greetings skip memory search entirely (<2ms). Near-perfect memory matches (distance < 0.35) are returned directly without LLM synthesis. File memories are only searched when the question is about files. These shortcuts keep most responses fast."
        )
    }
}

@Composable
private fun EssencesContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "What are Essences?",
            content = "Essences are modular AI personas — like apps for your AI system. Each essence has its own personality, knowledge, tools, and isolated memory. They run through Jane's brain but act as independent specialists."
        )
        InfoCard(
            title = "Built-in Essences",
            content = "Vessence ships with several essences:\n\n• Daily Briefing — Fetches and summarizes news overnight, with audio playback\n• Life Librarian — Manages your Vault files with search, sharing, and playlists\n• Work Log — Tracks Jane's daily activities and completed tasks"
        )
        InfoCard(
            title = "Building Custom Essences",
            content = "Tell Jane to 'build an essence' and she'll walk you through a 12-section interview: name, personality, tools, knowledge, memory setup, and more. Once you approve the spec, she generates the entire essence folder automatically."
        )
        InfoCard(
            title = "Essence Isolation",
            content = "Each essence gets its own ChromaDB collection, working files directory, and callable functions. Essences can't accidentally access each other's data. But they can collaborate through the platform's coordination layer — for example, Music Playlist can browse files from Life Librarian."
        )
        InfoCard(
            title = "Marketplace (Coming Soon)",
            content = "Essences are designed as immutable products — like buying an edition of a textbook. No updates, no migration complexity. If needs change, you get a new essence. The marketplace at vessences.com will let users publish, share, and download essences."
        )
    }
}

@Composable
private fun VaultContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "Your Personal Cloud",
            content = "The Vault is your private file storage — documents, photos, music, and more. It lives on your machine and is accessible from the web interface, Android app, and through Jane/Amber in chat."
        )
        InfoCard(
            title = "AI-Powered Search",
            content = "Every file in the Vault gets indexed into ChromaDB with a content-derived description. You can ask Jane 'find my tax documents' or 'show me photos from last month' and she'll search semantically, not just by filename."
        )
        InfoCard(
            title = "Features",
            content = "• File browser with grid and list views\n• PDF viewer with fullscreen mode\n• Image thumbnails and previews\n• Music playback with playlists\n• File sharing via unique links\n• Upload from Android (share-to-app)\n• Folder navigation and descriptions"
        )
    }
}

@Composable
private fun StandingBrainContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "Jane's Two Halves",
            content = "Jane is one agent, but her execution is split across two pluggable slots:\n\n• Jane's initial ack — the fast front half. Runs a small model (Haiku 4.5, Gemini Flash, GPT-5-nano, or local Gemma4) to speak first within ~1–2s, handle trivia itself, and otherwise emit a quick \"give me a minute\" style ack with an ETA hint before handing off.\n\n• Jane's mind (the 'Standing Brain') — the deep-reasoning half. Runs a frontier model (Claude Opus, Gemini Pro, or GPT-5) as a long-lived CLI process kept warm between messages. This is where the real thinking happens.\n\nFrom your side there's just Jane. The two halves only exist so the first response feels instant while the hard work still gets a frontier model behind it."
        )
        InfoCard(
            title = "What is the Standing Brain?",
            content = "Instead of starting a new AI process for every message (which takes 5-30 seconds), Vessence keeps a long-lived CLI process running at all times. This 'Standing Brain' hosts Jane's mind — it accepts messages via stdin and streams responses back, making conversations feel instant."
        )
        InfoCard(
            title = "How It Works",
            content = "1. At startup, jane-web spawns the CLI process (claude, gemini, or codex)\n2. The system prompt is injected on the first message only\n3. Subsequent messages are sent raw — the CLI remembers the context\n4. After 20 turns, the brain restarts to prevent context staleness\n5. A background reaper monitors health every 60 seconds"
        )
        InfoCard(
            title = "Real-Time Streaming",
            content = "Jane streams her work to you as it happens. On Claude, you see thinking blocks, tool calls, and partial text as they're generated. On Gemini and OpenAI, you see plain text streaming line-by-line. All of this shows up as collapsible steps in the chat."
        )
        InfoCard(
            title = "Self-Healing",
            content = "If the brain process dies, it auto-restarts within 60 seconds. If it's been idle for 5+ minutes with high CPU, the reaper kills it to save resources. If it hits 3 consecutive failures, it restarts fresh. This keeps Jane available without manual intervention."
        )
    }
}

@Composable
private fun ProviderSwitchContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "Three Providers, One Interface",
            content = "Vessence supports Claude (Anthropic), Gemini (Google), and OpenAI as interchangeable AI providers. You choose one during setup, but you can switch at any time — even mid-conversation."
        )
        InfoCard(
            title = "Automatic Error Detection",
            content = "Jane monitors the AI provider's error output in the background. If she detects a rate limit, billing issue, or quota exhaustion, she immediately shows you what happened and offers one-click buttons to switch to another provider."
        )
        InfoCard(
            title = "How Switching Works",
            content = "1. You tap 'Switch to Gemini' (or another provider)\n2. Jane kills the current CLI process\n3. If the new CLI isn't installed yet, it's installed on-demand\n4. The new CLI process starts up\n5. Your .env file is updated so the switch persists across restarts\n6. If the new provider needs login, you get an OAuth link"
        )
    }
}

@Composable
private fun DockerContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "Container Architecture",
            content = "Vessence runs as 3 Docker containers:\n\n• Jane (port 8090) — The main web server, AI brain, and API\n• Onboarding (port 3000) — First-run setup wizard\n• ChromaDB — Vector database for memory storage"
        )
        InfoCard(
            title = "Lightweight Install",
            content = "The entire download is ~210 MB. The Jane image is 770 MB uncompressed, Onboarding is 139 MB (Alpine-based). The AI CLI (Claude/Gemini/OpenAI) is installed on first boot based on which provider you chose."
        )
        InfoCard(
            title = "Onboarding Flow",
            content = "When you first run Vessence:\n1. Open localhost:3000\n2. Welcome screen introduces Jane, Essences, and Tools\n3. If the installer already chose a provider, you go straight to login\n4. OAuth login authenticates your AI provider\n5. You're redirected to Jane's chat — ready to go"
        )
        InfoCard(
            title = "Remote Access",
            content = "Cloudflare Tunnel integration lets you access Vessence from anywhere — your phone, another computer, or while traveling. Set up a tunnel token in Settings and your instance becomes reachable at your custom domain."
        )
    }
}

@Composable
private fun CronContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "What Happens Overnight",
            content = "Every night between 2:00 and 6:00 AM, a pipeline of maintenance jobs runs automatically. These keep your system healthy, your news fresh, and your memories organized."
        )
        BulletList(listOf(
            "2:00 AM — USB Backup" to "Incremental sync of your Vault to USB drive. Only changed files are copied. Weekly snapshots preserve history.",
            "2:10 AM — Daily Briefing" to "Fetches news from Google News RSS, scrapes articles, generates AI summaries (brief + full), and produces audio files.",
            "2:15 AM — Memory Janitor" to "Cleans up ChromaDB: consolidates duplicate facts, deletes operational noise, and enforces the 14-day TTL on short-term memories.",
            "3:00 AM — System Janitor" to "General system maintenance — log rotation, temp file cleanup, and health checks.",
            "3:15 AM — Context Refresh" to "Regenerates Jane's startup context so the next conversation starts with fresh system knowledge.",
            "4:00 AM — Identity Essay" to "Generates a narrative essay about you from your profile and memories — helps Jane understand you holistically.",
            "4:15 AM — Code Map" to "Auto-generates an index of the codebase with function names, line numbers, and file descriptions.",
            "5:00 AM — Heartbeat" to "System health check and activity summary."
        ), accentColor = Green500)
    }
}

@Composable
private fun SecurityContent() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoCard(
            title = "Authentication",
            content = "Vessence uses Google OAuth for login — both on the web interface and the Android app. Your Google account is the single key to your system. Multiple emails can be allowed (e.g., you and a family member) via the ALLOWED_GOOGLE_EMAILS setting."
        )
        InfoCard(
            title = "Trusted Devices",
            content = "Each device that logs in is registered as a 'trusted device' with a unique fingerprint. You can see all trusted devices in Settings and revoke access to any device at any time."
        )
        InfoCard(
            title = "Tool Approval Gate",
            content = "When enabled, Jane asks for your permission before running potentially dangerous commands — file writes, shell commands, and code edits. You see exactly what she wants to do and can approve or deny each action. Dangerous patterns (rm -rf, DROP TABLE) are always flagged."
        )
        InfoCard(
            title = "Data Privacy",
            content = "All your data stays on your machine. Files are in the Vault, memories are in ChromaDB, configs are in .env files. The only external calls are to AI providers (Claude/Gemini/OpenAI) for generating responses. Vessence has no telemetry, no analytics, and no cloud sync."
        )
        InfoCard(
            title = "Per-User Isolation",
            content = "Each authorized user gets their own data directory, memory namespace, and personality settings. Users can't see each other's memories or private files."
        )
    }
}
