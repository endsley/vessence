package com.vessences.android

import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.vessences.android.ui.theme.VessenceTheme
import com.vessences.android.voice.AndroidTtsManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Reader screen for shared-article summaries.
 *
 * Launched from the "Summary ready" notification after the server returns
 * the qwen-generated summary. Auto-starts TTS on open; provides Stop and
 * Close controls. Lifecycle-scoped TTS — when the activity is destroyed,
 * speech stops and resources are released.
 */
class SummaryReaderActivity : ComponentActivity() {

    companion object {
        const val EXTRA_TITLE = "summary_title"
        const val EXTRA_SUMMARY = "summary_text"
        const val EXTRA_URL = "summary_url"
        private const val TAG = "SummaryReader"
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var tts: AndroidTtsManager? = null
    private var speakJob: Job? = null
    private var focusRequest: AudioFocusRequest? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val title = intent?.getStringExtra(EXTRA_TITLE).orEmpty()
        val summary = intent?.getStringExtra(EXTRA_SUMMARY).orEmpty()

        setContent {
            VessenceTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFF0F172A),
                ) {
                    ReaderScreen(
                        title = title,
                        summary = summary,
                        onStart = { startSpeaking(title, summary) },
                        onStop = { stopSpeaking() },
                        onClose = { finish() },
                    )
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        stopSpeaking()
        try { tts?.shutdown() } catch (_: Exception) {}
        tts = null
    }

    private fun startSpeaking(title: String, summary: String) {
        val spoken = if (title.isNotBlank()) "$title. $summary" else summary
        if (spoken.isBlank()) return
        stopSpeaking()
        speakJob = scope.launch {
            val audioMan = getSystemService(AUDIO_SERVICE) as? AudioManager
            val gotFocus = audioMan?.let { requestFocus(it) } ?: false
            try {
                val engine = tts ?: AndroidTtsManager(applicationContext).also { tts = it }
                engine.speak(spoken)
            } catch (e: Exception) {
                Log.w(TAG, "TTS speak failed: ${e.message}")
            } finally {
                if (gotFocus) audioMan?.let { releaseFocus(it) }
            }
        }
    }

    private fun stopSpeaking() {
        speakJob?.cancel()
        speakJob = null
        try { tts?.stop() } catch (_: Exception) {}
    }

    private fun buildFocusRequest(): AudioFocusRequest? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return null
        focusRequest?.let { return it }
        val built = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .build()
        focusRequest = built
        return built
    }

    private suspend fun requestFocus(audioMan: AudioManager): Boolean {
        return withContext(Dispatchers.Main.immediate) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val req = buildFocusRequest() ?: return@withContext false
                audioMan.requestAudioFocus(req) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            } else {
                @Suppress("DEPRECATION")
                audioMan.requestAudioFocus(
                    null,
                    AudioManager.STREAM_MUSIC,
                    AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK,
                ) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            }
        }
    }

    private suspend fun releaseFocus(audioMan: AudioManager) {
        withContext(Dispatchers.Main.immediate) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                buildFocusRequest()?.let { audioMan.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                audioMan.abandonAudioFocus(null)
            }
        }
    }
}

@Composable
private fun ReaderScreen(
    title: String,
    summary: String,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onClose: () -> Unit,
) {
    var isSpeaking by remember { mutableStateOf(true) }

    // Auto-start TTS once on first composition.
    LaunchedEffect(Unit) {
        onStart()
    }

    Scaffold { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 20.dp, vertical = 16.dp),
        ) {
            if (title.isNotBlank()) {
                Text(
                    text = title,
                    fontSize = 22.sp,
                    color = Color.White,
                    style = MaterialTheme.typography.titleLarge,
                )
                Spacer(Modifier.height(12.dp))
            }
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
            ) {
                Text(
                    text = summary,
                    fontSize = 17.sp,
                    color = Color(0xFFE2E8F0),
                    lineHeight = 26.sp,
                )
            }
            Spacer(Modifier.height(16.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (isSpeaking) {
                    Button(
                        onClick = {
                            onStop()
                            isSpeaking = false
                        },
                        modifier = Modifier.weight(1f),
                    ) { Text("Stop") }
                } else {
                    Button(
                        onClick = {
                            onStart()
                            isSpeaking = true
                        },
                        modifier = Modifier.weight(1f),
                    ) { Text("Replay") }
                }
                OutlinedButton(
                    onClick = {
                        onStop()
                        onClose()
                    },
                    modifier = Modifier.weight(1f),
                ) { Text("Close") }
            }
        }
    }
}
