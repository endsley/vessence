package com.vessences.android.ui.voice

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.vessences.android.data.repository.VoiceSettingsRepository
import com.vessences.android.util.Constants
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val Violet500 = Color(0xFFA855F7)
private val Violet700 = Color(0xFF7C3AED)
private val SlateText = Color(0xFF94A3B8)
private val GreenCheck = Color(0xFF22C55E)

private const val SAMPLE_RATE = 16_000
private const val RECORD_DURATION_MS = 3_000L
private const val TOTAL_SAMPLES = 3

private enum class TrainingPhase {
    SETUP,
    RECORDING,
    REVIEW,
    COMPLETE,
}

@Composable
fun TriggerWordTrainingScreen(
    onComplete: () -> Unit,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val voiceSettings = remember { VoiceSettingsRepository(context.applicationContext) }

    var phase by remember { mutableStateOf(TrainingPhase.SETUP) }
    var triggerPhrase by remember { mutableStateOf(voiceSettings.getTriggerPhrase()) }
    var currentSample by remember { mutableIntStateOf(0) }
    var isRecording by remember { mutableStateOf(false) }
    var isPlaying by remember { mutableStateOf(false) }
    var recordedSamples by remember { mutableStateOf(List(TOTAL_SAMPLES) { false }) }
    var recordJob by remember { mutableStateOf<Job?>(null) }
    var playJob by remember { mutableStateOf<Job?>(null) }

    var hasMicPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        hasMicPermission = granted
    }

    DisposableEffect(Unit) {
        onDispose {
            recordJob?.cancel()
            playJob?.cancel()
        }
    }

    fun sampleFile(index: Int): File {
        val dir = File(context.filesDir, "trigger_samples")
        dir.mkdirs()
        return File(dir, "sample_$index.wav")
    }

    fun startRecording() {
        if (!hasMicPermission) {
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            return
        }
        isRecording = true
        recordJob = scope.launch {
            withContext(Dispatchers.IO) {
                recordSample(sampleFile(currentSample))
            }
            isRecording = false
            val updated = recordedSamples.toMutableList()
            updated[currentSample] = true
            recordedSamples = updated
            phase = TrainingPhase.REVIEW
        }
    }

    fun playSample() {
        isPlaying = true
        playJob = scope.launch {
            withContext(Dispatchers.IO) {
                playWavFile(sampleFile(currentSample))
            }
            isPlaying = false
        }
    }

    fun nextSample() {
        if (currentSample + 1 < TOTAL_SAMPLES) {
            currentSample++
            phase = TrainingPhase.RECORDING
        } else {
            // All samples recorded — save settings
            voiceSettings.setTriggerPhrase(triggerPhrase.lowercase().trim())
            voiceSettings.setTriggerTrained(true)
            voiceSettings.setTriggerSamplesCount(TOTAL_SAMPLES)
            phase = TrainingPhase.COMPLETE
        }
    }

    fun retryCurrentSample() {
        val updated = recordedSamples.toMutableList()
        updated[currentSample] = false
        recordedSamples = updated
        phase = TrainingPhase.RECORDING
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg),
    ) {
        // Top bar
        Surface(color = SlateBg) {
            Row(
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = {
                    recordJob?.cancel()
                    playJob?.cancel()
                    onBack()
                }) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "Back",
                        tint = Color.White,
                    )
                }
                Text(
                    text = "Trigger Word Training",
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            when (phase) {
                TrainingPhase.SETUP -> SetupPhase(
                    triggerPhrase = triggerPhrase,
                    onPhraseChanged = { triggerPhrase = it },
                    onStart = {
                        if (!hasMicPermission) {
                            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        } else {
                            phase = TrainingPhase.RECORDING
                        }
                    },
                )

                TrainingPhase.RECORDING -> RecordingPhase(
                    currentSample = currentSample,
                    triggerPhrase = triggerPhrase,
                    isRecording = isRecording,
                    onRecord = { startRecording() },
                )

                TrainingPhase.REVIEW -> ReviewPhase(
                    currentSample = currentSample,
                    isPlaying = isPlaying,
                    onPlay = { playSample() },
                    onRetry = { retryCurrentSample() },
                    onAccept = { nextSample() },
                )

                TrainingPhase.COMPLETE -> CompletePhase(
                    triggerPhrase = triggerPhrase,
                    onDone = onComplete,
                )
            }

            // Sample progress indicators
            if (phase != TrainingPhase.SETUP && phase != TrainingPhase.COMPLETE) {
                Spacer(modifier = Modifier.height(32.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    for (i in 0 until TOTAL_SAMPLES) {
                        SampleIndicator(
                            index = i,
                            isCurrent = i == currentSample,
                            isRecorded = recordedSamples[i],
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SetupPhase(
    triggerPhrase: String,
    onPhraseChanged: (String) -> Unit,
    onStart: () -> Unit,
) {
    Spacer(modifier = Modifier.height(48.dp))

    Icon(
        Icons.Default.Mic,
        contentDescription = null,
        tint = Violet500,
        modifier = Modifier.size(64.dp),
    )

    Spacer(modifier = Modifier.height(24.dp))

    Text(
        "Train Your Trigger Word",
        color = Color.White,
        fontSize = 24.sp,
        fontWeight = FontWeight.Bold,
        textAlign = TextAlign.Center,
    )

    Spacer(modifier = Modifier.height(12.dp))

    Text(
        "Say your chosen wake phrase 3 times so the app learns to recognize your voice.",
        color = SlateText,
        fontSize = 14.sp,
        textAlign = TextAlign.Center,
        modifier = Modifier.padding(horizontal = 16.dp),
    )

    Spacer(modifier = Modifier.height(32.dp))

    OutlinedTextField(
        value = triggerPhrase,
        onValueChange = onPhraseChanged,
        label = { Text("Trigger phrase") },
        singleLine = true,
        colors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = Color.White,
            unfocusedTextColor = Color.White,
            focusedBorderColor = Violet500,
            unfocusedBorderColor = SlateText,
            focusedLabelColor = Violet500,
            unfocusedLabelColor = SlateText,
            cursorColor = Violet500,
        ),
        modifier = Modifier.fillMaxWidth(),
    )

    Spacer(modifier = Modifier.height(32.dp))

    Button(
        onClick = onStart,
        colors = ButtonDefaults.buttonColors(
            containerColor = Violet500,
            contentColor = Color.White,
        ),
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier
            .fillMaxWidth()
            .height(48.dp),
    ) {
        Text("Start Training", fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun RecordingPhase(
    currentSample: Int,
    triggerPhrase: String,
    isRecording: Boolean,
    onRecord: () -> Unit,
) {
    Spacer(modifier = Modifier.height(48.dp))

    Text(
        "Sample ${currentSample + 1} of $TOTAL_SAMPLES",
        color = Violet500,
        fontSize = 16.sp,
        fontWeight = FontWeight.SemiBold,
    )

    Spacer(modifier = Modifier.height(12.dp))

    Text(
        "Say: \"$triggerPhrase\"",
        color = Color.White,
        fontSize = 22.sp,
        fontWeight = FontWeight.Bold,
        textAlign = TextAlign.Center,
    )

    Spacer(modifier = Modifier.height(48.dp))

    // Pulsing mic button
    Box(contentAlignment = Alignment.Center) {
        if (isRecording) {
            val infiniteTransition = rememberInfiniteTransition(label = "pulse")
            val scale by infiniteTransition.animateFloat(
                initialValue = 1f,
                targetValue = 1.3f,
                animationSpec = infiniteRepeatable(
                    animation = tween(600, easing = LinearEasing),
                    repeatMode = RepeatMode.Reverse,
                ),
                label = "pulseScale",
            )
            Box(
                modifier = Modifier
                    .size(120.dp)
                    .scale(scale)
                    .background(Violet500.copy(alpha = 0.2f), CircleShape),
            )
        }

        IconButton(
            onClick = { if (!isRecording) onRecord() },
            modifier = Modifier
                .size(96.dp)
                .background(
                    if (isRecording) Color(0xFFEF4444) else Violet500,
                    CircleShape,
                ),
        ) {
            Icon(
                Icons.Default.Mic,
                contentDescription = if (isRecording) "Recording" else "Tap to record",
                tint = Color.White,
                modifier = Modifier.size(48.dp),
            )
        }
    }

    Spacer(modifier = Modifier.height(16.dp))

    Text(
        if (isRecording) "Recording..." else "Tap the microphone to record",
        color = SlateText,
        fontSize = 14.sp,
    )
}

@Composable
private fun ReviewPhase(
    currentSample: Int,
    isPlaying: Boolean,
    onPlay: () -> Unit,
    onRetry: () -> Unit,
    onAccept: () -> Unit,
) {
    Spacer(modifier = Modifier.height(48.dp))

    Icon(
        Icons.Default.CheckCircle,
        contentDescription = null,
        tint = GreenCheck,
        modifier = Modifier.size(64.dp),
    )

    Spacer(modifier = Modifier.height(16.dp))

    Text(
        "Sample ${currentSample + 1} recorded!",
        color = Color.White,
        fontSize = 20.sp,
        fontWeight = FontWeight.Bold,
    )

    Spacer(modifier = Modifier.height(8.dp))

    Text(
        "Play it back to check, or accept and continue.",
        color = SlateText,
        fontSize = 14.sp,
        textAlign = TextAlign.Center,
    )

    Spacer(modifier = Modifier.height(32.dp))

    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        OutlinedButton(
            onClick = onPlay,
            enabled = !isPlaying,
            colors = ButtonDefaults.outlinedButtonColors(contentColor = Violet500),
            shape = RoundedCornerShape(12.dp),
        ) {
            Icon(Icons.Default.PlayArrow, contentDescription = null)
            Spacer(modifier = Modifier.width(4.dp))
            Text(if (isPlaying) "Playing..." else "Play")
        }

        OutlinedButton(
            onClick = onRetry,
            colors = ButtonDefaults.outlinedButtonColors(contentColor = SlateText),
            shape = RoundedCornerShape(12.dp),
        ) {
            Icon(Icons.Default.Refresh, contentDescription = null)
            Spacer(modifier = Modifier.width(4.dp))
            Text("Try Again")
        }
    }

    Spacer(modifier = Modifier.height(24.dp))

    Button(
        onClick = onAccept,
        colors = ButtonDefaults.buttonColors(
            containerColor = Violet500,
            contentColor = Color.White,
        ),
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier
            .fillMaxWidth()
            .height(48.dp),
    ) {
        Text(
            if (currentSample + 1 < TOTAL_SAMPLES) "Accept & Next" else "Accept & Finish",
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun CompletePhase(
    triggerPhrase: String,
    onDone: () -> Unit,
) {
    Spacer(modifier = Modifier.height(64.dp))

    Icon(
        Icons.Default.CheckCircle,
        contentDescription = null,
        tint = GreenCheck,
        modifier = Modifier.size(80.dp),
    )

    Spacer(modifier = Modifier.height(24.dp))

    Text(
        "Training Complete!",
        color = Color.White,
        fontSize = 24.sp,
        fontWeight = FontWeight.Bold,
    )

    Spacer(modifier = Modifier.height(12.dp))

    Text(
        "Always-listening is now active. Say \"$triggerPhrase\" to wake up Jane.",
        color = SlateText,
        fontSize = 14.sp,
        textAlign = TextAlign.Center,
        modifier = Modifier.padding(horizontal = 16.dp),
    )

    Spacer(modifier = Modifier.height(48.dp))

    Button(
        onClick = onDone,
        colors = ButtonDefaults.buttonColors(
            containerColor = Violet500,
            contentColor = Color.White,
        ),
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier
            .fillMaxWidth()
            .height(48.dp),
    ) {
        Text("Done", fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun SampleIndicator(
    index: Int,
    isCurrent: Boolean,
    isRecorded: Boolean,
) {
    Box(
        modifier = Modifier
            .size(40.dp)
            .background(
                when {
                    isRecorded -> GreenCheck.copy(alpha = 0.2f)
                    isCurrent -> Violet500.copy(alpha = 0.2f)
                    else -> SlateCard
                },
                CircleShape,
            )
            .then(
                if (isCurrent) Modifier.border(2.dp, Violet500, CircleShape) else Modifier
            ),
        contentAlignment = Alignment.Center,
    ) {
        if (isRecorded) {
            Icon(
                Icons.Default.CheckCircle,
                contentDescription = "Recorded",
                tint = GreenCheck,
                modifier = Modifier.size(20.dp),
            )
        } else {
            Text(
                "${index + 1}",
                color = if (isCurrent) Violet500 else SlateText,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

/**
 * Records [RECORD_DURATION_MS] of audio and saves as a WAV file.
 */
private fun recordSample(file: File) {
    val bufferSize = AudioRecord.getMinBufferSize(
        SAMPLE_RATE,
        AudioFormat.CHANNEL_IN_MONO,
        AudioFormat.ENCODING_PCM_16BIT,
    ).coerceAtLeast(SAMPLE_RATE)

    val record = AudioRecord(
        MediaRecorder.AudioSource.VOICE_RECOGNITION,
        SAMPLE_RATE,
        AudioFormat.CHANNEL_IN_MONO,
        AudioFormat.ENCODING_PCM_16BIT,
        bufferSize,
    )

    if (record.state != AudioRecord.STATE_INITIALIZED) {
        record.release()
        return
    }

    val totalBytes = (SAMPLE_RATE * 2 * RECORD_DURATION_MS / 1000).toInt()
    val audioData = ByteArray(totalBytes)
    var offset = 0

    try {
        record.startRecording()
        val buffer = ByteArray(bufferSize)
        val startTime = System.currentTimeMillis()

        while (offset < totalBytes && System.currentTimeMillis() - startTime < RECORD_DURATION_MS + 500) {
            val toRead = minOf(buffer.size, totalBytes - offset)
            val read = record.read(buffer, 0, toRead)
            if (read > 0) {
                System.arraycopy(buffer, 0, audioData, offset, read)
                offset += read
            }
        }
    } finally {
        runCatching {
            if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                record.stop()
            }
            record.release()
        }
    }

    // Write WAV file
    writeWavFile(file, audioData, offset)
}

private fun writeWavFile(file: File, audioData: ByteArray, dataLength: Int) {
    file.parentFile?.mkdirs()
    FileOutputStream(file).use { fos ->
        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        // RIFF header
        header.put("RIFF".toByteArray())
        header.putInt(36 + dataLength)
        header.put("WAVE".toByteArray())
        // fmt chunk
        header.put("fmt ".toByteArray())
        header.putInt(16) // chunk size
        header.putShort(1) // PCM
        header.putShort(1) // mono
        header.putInt(SAMPLE_RATE)
        header.putInt(SAMPLE_RATE * 2) // byte rate
        header.putShort(2) // block align
        header.putShort(16) // bits per sample
        // data chunk
        header.put("data".toByteArray())
        header.putInt(dataLength)

        fos.write(header.array())
        fos.write(audioData, 0, dataLength)
    }
}

private fun playWavFile(file: File) {
    if (!file.exists()) return

    val raf = RandomAccessFile(file, "r")
    try {
        // Skip WAV header
        raf.seek(44)
        val dataLength = (file.length() - 44).toInt()
        if (dataLength <= 0) return

        val audioData = ByteArray(dataLength)
        raf.readFully(audioData)

        val bufferSize = AudioTrack.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )

        @Suppress("DEPRECATION")
        val track = AudioTrack(
            android.media.AudioManager.STREAM_MUSIC,
            SAMPLE_RATE,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize,
            AudioTrack.MODE_STREAM,
        )

        try {
            track.play()
            track.write(audioData, 0, audioData.size)
            // Wait for playback to finish
            Thread.sleep((dataLength.toLong() * 1000) / (SAMPLE_RATE * 2) + 200)
        } finally {
            runCatching {
                track.stop()
                track.release()
            }
        }
    } finally {
        raf.close()
    }
}
