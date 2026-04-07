package com.vessences.android.ui.settings

import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.vessences.android.util.ChatPreferences
import java.util.Locale

private val BgColor = Color(0xFF0F172A)
private val CardColor = Color(0xFF1E293B)
private val Violet = Color(0xFF7C3AED)
private val SlateMuted = Color(0xFF94A3B8)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TtsVoicePickerSheet(
    visible: Boolean,
    onDismiss: () -> Unit,
) {
    if (!visible) return

    val context = LocalContext.current
    val prefs = remember { ChatPreferences(context) }
    var voices by remember { mutableStateOf<List<Voice>>(emptyList()) }
    var selectedVoiceName by remember { mutableStateOf(prefs.getTtsVoice()) }
    var tts by remember { mutableStateOf<TextToSpeech?>(null) }
    var ttsReady by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        val engine = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                ttsReady = true
            }
        }
        tts = engine
        onDispose {
            engine.stop()
            engine.shutdown()
        }
    }

    LaunchedEffect(ttsReady) {
        if (ttsReady && tts != null) {
            val available = tts!!.voices?.toList() ?: emptyList()
            // Include ALL English voices (including network/high-quality ones)
            voices = available
                .filter { it.locale.language == Locale.ENGLISH.language }
                .sortedWith(compareByDescending<Voice> { it.quality }.thenBy { it.name })

            // Apply saved voice
            if (selectedVoiceName.isNotEmpty()) {
                val saved = voices.find { it.name == selectedVoiceName }
                if (saved != null) tts!!.voice = saved
            }
        }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = BgColor,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp),
        ) {
            Text("TTS Voice", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(4.dp))
            Text("Tap a voice to preview, select to use", color = SlateMuted, fontSize = 12.sp)
            Spacer(modifier = Modifier.height(12.dp))

            if (voices.isEmpty()) {
                Text("Loading voices...", color = SlateMuted, fontSize = 13.sp, modifier = Modifier.padding(16.dp))
            } else {
                LazyColumn(
                    modifier = Modifier.heightIn(max = 400.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    items(voices) { voice ->
                        val isSelected = voice.name == selectedVoiceName
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(
                                    if (isSelected) Violet.copy(alpha = 0.15f) else CardColor,
                                    RoundedCornerShape(8.dp)
                                )
                                .clickable {
                                    selectedVoiceName = voice.name
                                    prefs.setTtsVoice(voice.name)
                                    tts?.voice = voice
                                }
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            if (isSelected) {
                                Icon(Icons.Default.Check, "Selected", tint = Violet, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                            }
                            Column(modifier = Modifier.weight(1f)) {
                                // Show full voice name for differentiation
                                val displayName = voice.name
                                    .replace("en-us-x-", "")
                                    .replace("en-gb-x-", "UK ")
                                    .replace("en-au-x-", "AU ")
                                    .replace("#", " #")
                                    .replaceFirstChar { it.uppercase() }
                                val qualityLabel = when (voice.quality) {
                                    in 400..500 -> "Very High"
                                    in 300..399 -> "High"
                                    in 200..299 -> "Normal"
                                    else -> "Basic"
                                }
                                val networkLabel = if (voice.isNetworkConnectionRequired) " (cloud)" else " (local)"
                                Text(
                                    text = displayName,
                                    color = if (isSelected) Color.White else Color(0xFFCBD5E1),
                                    fontSize = 13.sp,
                                    fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                                )
                                Text(
                                    text = "${voice.locale.displayName} · $qualityLabel$networkLabel",
                                    color = SlateMuted,
                                    fontSize = 11.sp,
                                )
                            }
                            IconButton(
                                onClick = {
                                    tts?.voice = voice
                                    tts?.speak("Hi, this is how I sound.", TextToSpeech.QUEUE_FLUSH, null, "preview")
                                },
                                modifier = Modifier.size(32.dp),
                            ) {
                                Icon(Icons.Default.PlayArrow, "Preview", tint = Violet, modifier = Modifier.size(18.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}
