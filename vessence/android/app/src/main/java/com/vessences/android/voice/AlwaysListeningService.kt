package com.vessences.android.voice

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.telephony.TelephonyManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.vessences.android.MainActivity
import com.vessences.android.R
import com.vessences.android.data.repository.ChatBackend
import com.vessences.android.data.repository.ChatRepository
import com.vessences.android.data.repository.VoiceSettingsRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import java.util.Locale
import java.util.UUID
import kotlin.math.abs

class AlwaysListeningService : Service() {

    companion object {
        private const val CHANNEL_ID = "always_listening"
        private const val NOTIFICATION_ID = 9001
        private const val RESPONSE_NOTIFICATION_ID = 9002
        private const val RESPONSE_CHANNEL_ID = "jane_responses"
        private const val COMMAND_TIMEOUT_MS = 5_000L
        private const val COMMAND_SILENCE_MS = 1_300L
        private const val SPEECH_RMS_THRESHOLD = 900

        fun start(context: Context) {
            val intent = Intent(context, AlwaysListeningService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, AlwaysListeningService::class.java))
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val chatRepository = ChatRepository()
    private lateinit var voiceSettings: VoiceSettingsRepository
    private lateinit var modelManager: VoskModelManager

    @Volatile
    private var isListening = false

    @Volatile
    private var listeningThread: Thread? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var audioRecord: AudioRecord? = null

    override fun onCreate() {
        super.onCreate()
        voiceSettings = VoiceSettingsRepository(applicationContext)
        modelManager = VoskModelManager(applicationContext)
        createNotificationChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val triggerPhrase = voiceSettings.getTriggerPhrase()
        startForeground(NOTIFICATION_ID, buildListeningNotification(triggerPhrase))
        acquireWakeLock()
        startListeningLoop()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        isListening = false
        audioRecord?.let { record ->
            runCatching {
                if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    record.stop()
                }
                record.release()
            }
        }
        audioRecord = null
        listeningThread?.interrupt()
        listeningThread = null
        releaseWakeLock()
        scope.cancel()
        super.onDestroy()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)

            val listeningChannel = NotificationChannel(
                CHANNEL_ID,
                "Always Listening",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "Shows when Vessence is listening for your wake word"
                setShowBadge(false)
            }
            manager.createNotificationChannel(listeningChannel)

            val responseChannel = NotificationChannel(
                RESPONSE_CHANNEL_ID,
                "Jane Responses",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "Shows responses from Jane"
            }
            manager.createNotificationChannel(responseChannel)
        }
    }

    private fun buildListeningNotification(triggerPhrase: String): Notification {
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Vessence is listening")
            .setContentText("Listening for '$triggerPhrase'")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }

    private fun acquireWakeLock() {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "vessence:always_listening",
        ).apply {
            acquire()
        }
    }

    private fun releaseWakeLock() {
        wakeLock?.let {
            if (it.isHeld) it.release()
        }
        wakeLock = null
    }

    private fun isInCall(): Boolean {
        val telephony = getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
        return telephony?.callState != TelephonyManager.CALL_STATE_IDLE
    }

    private fun startListeningLoop() {
        isListening = true
        listeningThread = Thread({
            while (isListening) {
                if (isInCall()) {
                    Thread.sleep(2000)
                    continue
                }
                try {
                    runWakeWordDetection()
                } catch (e: InterruptedException) {
                    break
                } catch (e: Exception) {
                    // Brief pause before retry on error
                    if (isListening) Thread.sleep(1000)
                }
            }
        }, "always-listening-loop").apply {
            isDaemon = true
            start()
        }
    }

    private fun runWakeWordDetection() {
        val model = modelManager.getModelSync() ?: return
        val triggerPhrase = voiceSettings.getTriggerPhrase().lowercase(Locale.US)
        val grammarPhrases = buildList {
            add(triggerPhrase)
            if (triggerPhrase != "hey jane") add("hey jane")
            add("[unk]")
        }
        val grammar = JSONObject().put("phrases", grammarPhrases).getJSONArray("phrases").toString()

        val bufferSize = AudioRecord.getMinBufferSize(
            ListeningSession.SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        ).coerceAtLeast(ListeningSession.SAMPLE_RATE)

        val record = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            ListeningSession.SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize,
        )

        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            Thread.sleep(2000)
            return
        }

        audioRecord = record
        val recognizer = Recognizer(model, ListeningSession.SAMPLE_RATE.toFloat(), grammar)

        try {
            record.startRecording()
            val buffer = ByteArray(bufferSize)

            while (isListening && !isInCall()) {
                val read = record.read(buffer, 0, buffer.size)
                if (read <= 0) continue

                val partialText = extractText(recognizer.partialResult, "partial")
                if (partialText.isNotBlank() && matchesTrigger(partialText, triggerPhrase)) {
                    onWakeWordDetected(model)
                    return
                }

                if (recognizer.acceptWaveForm(buffer, read)) {
                    val resultText = extractText(recognizer.result, "text")
                    if (resultText.isNotBlank() && matchesTrigger(resultText, triggerPhrase)) {
                        onWakeWordDetected(model)
                        return
                    }
                }
            }
        } finally {
            recognizer.close()
            runCatching {
                if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    record.stop()
                }
                record.release()
            }
            audioRecord = null
        }
    }

    private fun matchesTrigger(text: String, triggerPhrase: String): Boolean {
        val normalized = text.lowercase(Locale.US)
        if (normalized.contains(triggerPhrase)) return true

        // Sliding window fuzzy match
        val triggerWords = triggerPhrase.split(" ")
        val textWords = normalized.split(" ")
        if (textWords.size >= triggerWords.size) {
            for (i in 0..textWords.size - triggerWords.size) {
                val window = textWords.subList(i, i + triggerWords.size).joinToString(" ")
                if (ListeningSession.normalizedSimilarity(window, triggerPhrase) >= 0.7) {
                    return true
                }
            }
        }

        return ListeningSession.normalizedSimilarity(normalized, triggerPhrase) >= 0.7
    }

    private fun onWakeWordDetected(model: Model) {
        vibrateShort()
        val command = captureCommand(model)
        if (command.isNotBlank()) {
            sendToJane(command)
        }
    }

    private fun vibrateShort() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val manager = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
                manager.defaultVibrator.vibrate(
                    VibrationEffect.createOneShot(100, VibrationEffect.DEFAULT_AMPLITUDE)
                )
            } else {
                @Suppress("DEPRECATION")
                val vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator.vibrate(
                        VibrationEffect.createOneShot(100, VibrationEffect.DEFAULT_AMPLITUDE)
                    )
                } else {
                    @Suppress("DEPRECATION")
                    vibrator.vibrate(100)
                }
            }
        } catch (_: Exception) {
            // Vibration not critical
        }
    }

    private fun captureCommand(model: Model): String {
        val bufferSize = AudioRecord.getMinBufferSize(
            ListeningSession.SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        ).coerceAtLeast(ListeningSession.SAMPLE_RATE)

        val record = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            ListeningSession.SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize,
        )

        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            return ""
        }

        audioRecord = record
        val recognizer = Recognizer(model, ListeningSession.SAMPLE_RATE.toFloat())

        try {
            record.startRecording()
            val buffer = ByteArray(bufferSize)
            var transcript = ""
            var sawSpeech = false
            val startAt = System.currentTimeMillis()
            var lastSpeechAt = startAt

            while (isListening) {
                val read = record.read(buffer, 0, buffer.size)
                if (read <= 0) continue

                val energy = rmsLevel(buffer, read)
                val partialText = extractText(recognizer.partialResult, "partial")

                if (partialText.isNotBlank()) {
                    transcript = partialText
                    lastSpeechAt = System.currentTimeMillis()
                    sawSpeech = true
                } else if (energy >= SPEECH_RMS_THRESHOLD) {
                    lastSpeechAt = System.currentTimeMillis()
                    sawSpeech = true
                }

                if (recognizer.acceptWaveForm(buffer, read)) {
                    val resultText = extractText(recognizer.result, "text")
                    if (resultText.isNotBlank()) {
                        transcript = resultText
                        lastSpeechAt = System.currentTimeMillis()
                        sawSpeech = true
                    }
                }

                val now = System.currentTimeMillis()
                if (sawSpeech && now - lastSpeechAt >= COMMAND_SILENCE_MS) break
                if (!sawSpeech && now - startAt >= COMMAND_TIMEOUT_MS) break
                if (now - startAt >= COMMAND_TIMEOUT_MS + 3000) break // absolute max
            }

            val finalText = extractText(recognizer.finalResult, "text").ifBlank { transcript }
            return finalText.trim()
        } finally {
            recognizer.close()
            runCatching {
                if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    record.stop()
                }
                record.release()
            }
            audioRecord = null
        }
    }

    private fun sendToJane(command: String) {
        val sessionId = UUID.randomUUID().toString()
        scope.launch(Dispatchers.IO) {
            try {
                val response = StringBuilder()
                chatRepository.streamChat(
                    backend = ChatBackend.JANE,
                    message = command,
                    sessionId = sessionId,
                ).onEach { event ->
                    if (event.data.isNotBlank()) response.append(event.data)
                }.catch { e ->
                    showResponseNotification("Error: ${e.message ?: "Failed to get response"}")
                }.collect()

                val fullResponse = response.toString().trim()
                if (fullResponse.isNotBlank()) {
                    showResponseNotification(fullResponse)
                }
            } catch (e: Exception) {
                showResponseNotification("Error: ${e.message ?: "Failed to send command"}")
            }
        }
    }

    private fun showResponseNotification(text: String) {
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 1, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(this, RESPONSE_CHANNEL_ID)
            .setContentTitle("Jane")
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        try {
            NotificationManagerCompat.from(this).notify(RESPONSE_NOTIFICATION_ID, notification)
        } catch (_: SecurityException) {
            // Missing POST_NOTIFICATIONS permission
        }
    }

    private fun extractText(json: String, key: String): String =
        runCatching { JSONObject(json).optString(key).trim() }.getOrDefault("")

    private fun rmsLevel(buffer: ByteArray, length: Int): Int {
        if (length < 2) return 0
        var total = 0L
        var samples = 0
        var index = 0
        while (index + 1 < length) {
            val sample = ((buffer[index + 1].toInt() shl 8) or (buffer[index].toInt() and 0xff)).toShort()
            total += abs(sample.toInt())
            samples++
            index += 2
        }
        return if (samples == 0) 0 else (total / samples).toInt()
    }
}
