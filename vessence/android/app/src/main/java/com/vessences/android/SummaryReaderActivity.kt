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
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.text.BreakIterator
import java.util.Locale

/**
 * Reader screen for shared-article summaries.
 *
 * The summary is split into sentences and played one-at-a-time so the user can:
 *   - toggle Play / Pause mid-summary,
 *   - drag the progress slider to jump to an earlier or later point.
 *
 * Android's TextToSpeech has no native pause or seek, so we implement both
 * at the sentence level: pause = stop + remember index, seek = stop + move
 * index + relaunch loop. A Mutex serializes play/pause/seek so they can't
 * race each other or leave stacked playback coroutines running.
 */
class SummaryReaderActivity : ComponentActivity() {

    companion object {
        const val EXTRA_TITLE = "summary_title"
        const val EXTRA_SUMMARY = "summary_text"
        const val EXTRA_URL = "summary_url"
        private const val TAG = "SummaryReader"
    }

    // Main.immediate so state mutations (Compose snapshot state) and the
    // playback loop all run on a single thread — no cross-thread snapshot races.
    private val scope = CoroutineScope(Dispatchers.Main.immediate + SupervisorJob())
    private val controllerMutex = Mutex()
    private var tts: AndroidTtsManager? = null
    private var playbackJob: Job? = null
    private var focusRequest: AudioFocusRequest? = null
    private lateinit var state: ReaderState

    private val focusListener = AudioManager.OnAudioFocusChangeListener { change ->
        when (change) {
            AudioManager.AUDIOFOCUS_LOSS,
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT,
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK -> pause()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val title = intent?.getStringExtra(EXTRA_TITLE).orEmpty()
        val summary = intent?.getStringExtra(EXTRA_SUMMARY).orEmpty()
        state = ReaderState(buildSentences(title, summary))

        setContent {
            VessenceTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFF0F172A),
                ) {
                    ReaderScreen(
                        title = title,
                        summary = summary,
                        state = state,
                        onPlay = { play() },
                        onPause = { pause() },
                        onSeek = { index -> seek(index) },
                        onClose = { finish() },
                    )
                }
            }
        }

        play()
    }

    override fun onDestroy() {
        super.onDestroy()
        state.isPlaying = false
        try { tts?.stop() } catch (_: Exception) {}
        scope.cancel()
        try { tts?.shutdown() } catch (_: Exception) {}
        tts = null
    }

    private fun play() {
        scope.launch {
            controllerMutex.withLock {
                if (state.sentences.isEmpty()) return@withLock
                playbackJob?.cancelAndJoin()
                if (state.currentIndex >= state.sentences.size) state.currentIndex = 0
                state.isPlaying = true
                playbackJob = launchPlayback()
            }
        }
    }

    private fun pause() {
        scope.launch {
            controllerMutex.withLock {
                state.isPlaying = false
                try { tts?.stop() } catch (_: Exception) {}
                playbackJob?.cancelAndJoin()
            }
        }
    }

    private fun seek(newIndex: Int) {
        scope.launch {
            controllerMutex.withLock {
                if (state.sentences.isEmpty()) return@withLock
                val clamped = newIndex.coerceIn(0, state.sentences.size - 1)
                val wasPlaying = state.isPlaying
                try { tts?.stop() } catch (_: Exception) {}
                playbackJob?.cancelAndJoin()
                state.currentIndex = clamped
                if (wasPlaying) {
                    state.isPlaying = true
                    playbackJob = launchPlayback()
                }
            }
        }
    }

    private fun launchPlayback(): Job = scope.launch {
        val audioMan = getSystemService(AUDIO_SERVICE) as? AudioManager
        val gotFocus = audioMan?.let { requestFocus(it) } ?: false
        if (!gotFocus) {
            // Speaking while another app owns focus is a bad citizen move;
            // flip back to paused so the UI reflects reality.
            state.isPlaying = false
            return@launch
        }
        try {
            val engine = tts ?: AndroidTtsManager(applicationContext).also { tts = it }
            while (isActive && state.isPlaying && state.currentIndex < state.sentences.size) {
                val idx = state.currentIndex
                engine.speak(state.sentences[idx])
                // seek() cancels this job before touching currentIndex, so if
                // we got here the utterance completed normally and we advance.
                if (isActive && state.isPlaying && state.currentIndex == idx) {
                    state.currentIndex = idx + 1
                }
            }
            if (state.currentIndex >= state.sentences.size) {
                state.isPlaying = false
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "playback failed: ${e.message}")
            state.isPlaying = false
        } finally {
            audioMan?.let { releaseFocus(it) }
        }
    }

    private fun buildFocusRequest(): AudioFocusRequest? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return null
        focusRequest?.let { return it }
        val built = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            .setOnAudioFocusChangeListener(focusListener)
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

    private fun requestFocus(audioMan: AudioManager): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val req = buildFocusRequest() ?: return false
            audioMan.requestAudioFocus(req) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        } else {
            @Suppress("DEPRECATION")
            audioMan.requestAudioFocus(
                focusListener,
                AudioManager.STREAM_MUSIC,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT,
            ) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        }
    }

    private fun releaseFocus(audioMan: AudioManager) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            buildFocusRequest()?.let { audioMan.abandonAudioFocusRequest(it) }
        } else {
            @Suppress("DEPRECATION")
            audioMan.abandonAudioFocus(focusListener)
        }
    }
}

/** Observable state shared between the playback coroutine and the Compose UI. */
class ReaderState(val sentences: List<String>) {
    var currentIndex by mutableStateOf(0)
    var isPlaying by mutableStateOf(false)
}

/**
 * Split title + summary into sentence-sized chunks using BreakIterator, which
 * understands common abbreviations (Mr., U.S., etc.) better than a plain regex.
 */
private fun buildSentences(title: String, summary: String): List<String> {
    val titlePart = title.trim().takeIf { it.isNotEmpty() }?.let {
        if (it.last() in ".!?") it else "$it."
    }
    val bodyPart = summary.trim().takeIf { it.isNotEmpty() }
    val combined = listOfNotNull(titlePart, bodyPart).joinToString(" ")
    if (combined.isBlank()) return emptyList()

    val iter = BreakIterator.getSentenceInstance(Locale.US)
    iter.setText(combined)
    val out = mutableListOf<String>()
    var start = iter.first()
    var end = iter.next()
    while (end != BreakIterator.DONE) {
        val chunk = combined.substring(start, end).trim()
        if (chunk.isNotEmpty()) out += chunk
        start = end
        end = iter.next()
    }
    return out
}

@Composable
private fun ReaderScreen(
    title: String,
    summary: String,
    state: ReaderState,
    onPlay: () -> Unit,
    onPause: () -> Unit,
    onSeek: (Int) -> Unit,
    onClose: () -> Unit,
) {
    val total = state.sentences.size
    val index = state.currentIndex
    val playing = state.isPlaying

    // While the user is dragging, decouple the thumb from `index` so it
    // doesn't jump if TTS happens to advance mid-drag.
    var dragValue by remember { mutableStateOf<Float?>(null) }

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
            Spacer(Modifier.height(12.dp))
            if (total > 1) {
                val maxVal = (total - 1).toFloat()
                val shown = (dragValue ?: index.toFloat()).coerceIn(0f, maxVal)
                Slider(
                    value = shown,
                    onValueChange = { v -> dragValue = v },
                    onValueChangeFinished = {
                        val v = dragValue
                        dragValue = null
                        if (v != null) onSeek(v.toInt().coerceIn(0, total - 1))
                    },
                    valueRange = 0f..maxVal,
                    steps = (total - 2).coerceAtLeast(0),
                )
                Text(
                    text = "${(shown.toInt() + 1).coerceAtMost(total)} / $total",
                    fontSize = 12.sp,
                    color = Color(0xFF94A3B8),
                )
                Spacer(Modifier.height(8.dp))
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = { if (playing) onPause() else onPlay() },
                    modifier = Modifier.weight(1f),
                ) { Text(if (playing) "Pause" else "Play") }
                OutlinedButton(
                    onClick = {
                        onPause()
                        onClose()
                    },
                    modifier = Modifier.weight(1f),
                ) { Text("Close") }
            }
        }
    }
}
