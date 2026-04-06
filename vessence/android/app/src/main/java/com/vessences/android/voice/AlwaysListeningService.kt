package com.vessences.android.voice

import com.vessences.android.DiagnosticReporter
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
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
import android.util.Log
import androidx.core.app.NotificationCompat
import com.vessences.android.MainActivity
import com.vessences.android.R
import com.vessences.android.data.repository.VoiceSettingsRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

private const val TAG = "AlwaysListening"

class AlwaysListeningService : Service() {

    companion object {
        private const val CHANNEL_ID = "always_listening"
        private const val NOTIFICATION_ID = 9001
        const val ACTION_STOP = "com.vessences.android.STOP_LISTENING"
        private const val TRIGGER_COOLDOWN_MS = 5_000L

        /** Prevents rapid re-triggering from background sound loops */
        @Volatile
        private var lastTriggerTimestamp: Long = 0L

        private val _running = kotlinx.coroutines.flow.MutableStateFlow(false)
        val running: kotlinx.coroutines.flow.StateFlow<Boolean> = _running

        /**
         * Atomic guard that coordinates all calls to [startForegroundService]
         * across every caller site. Set to true the instant [start] is called,
         * cleared when either:
         *  - onStartCommand runs (meaning the service is alive and promoted), OR
         *  - onDestroy runs (meaning the service tore down), OR
         *  - start() itself throws (so a broken attempt does not permanently
         *    deadlock future starts).
         *
         * This is the CORRECT way to make start() idempotent. The previous
         * `_running.value` check was racy because `_running` only flips inside
         * startListeningLoop() which runs after foreground promotion — two
         * rapid callers could both see `_running=false` and both enqueue a
         * redundant startForegroundService(), eventually tripping Android 13's
         * 5-second foreground-service deadline enforcement.
         */
        private val startInFlight = java.util.concurrent.atomic.AtomicBoolean(false)

        fun start(context: Context) {
            // compareAndSet is the atomic primitive that makes this safe across
            // any number of concurrent callers: only ONE call wins the race and
            // proceeds to startForegroundService.
            if (!startInFlight.compareAndSet(false, true)) {
                android.util.Log.d(TAG, "start() called but another start is in flight — skipping")
                return
            }
            try {
                val intent = Intent(context, AlwaysListeningService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (t: Throwable) {
                // Reset the flag so a legitimate retry can proceed.
                startInFlight.set(false)
                throw t
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, AlwaysListeningService::class.java))
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private lateinit var voiceSettings: VoiceSettingsRepository
    private var detector: OpenWakeWordDetector? = null

    @Volatile
    private var isListening = false

    @Volatile
    private var listeningThread: Thread? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var audioRecord: AudioRecord? = null

    /** Tracks whether listening was paused due to screen off */
    @Volatile
    private var pausedForScreenOff = false

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                Intent.ACTION_SCREEN_OFF -> {
                    Log.i(TAG, "Screen OFF — pausing listening")
                    DiagnosticReporter.serviceEvent("AlwaysListening", "screen_off_pause")
                    pausedForScreenOff = true
                    pauseListening()
                }
                Intent.ACTION_SCREEN_ON -> {
                    if (pausedForScreenOff) {
                        Log.i(TAG, "Screen ON — resuming listening")
                        DiagnosticReporter.serviceEvent("AlwaysListening", "screen_on_resume")
                        pausedForScreenOff = false
                        resumeListening()
                    }
                }
            }
        }
    }
    private var screenReceiverRegistered = false

    override fun onCreate() {
        super.onCreate()
        // PROMOTE TO FOREGROUND IMMEDIATELY. On Android 13+ there is a hard
        // 5-second budget from Context.startForegroundService() to the first
        // Service.startForeground() call. onCreate runs on the main thread,
        // and if the main thread is busy when onStartCommand is eventually
        // scheduled, the budget may have elapsed. Calling startForeground
        // here guarantees we promote in time regardless of main-thread load.
        //
        // We use a minimal placeholder notification that does NOT require
        // reading VoiceSettingsRepository (which hits SharedPreferences disk
        // I/O and can block on cold start). onStartCommand will replace it
        // with the final notification that has the user's trigger phrase.
        createNotificationChannel()
        startForegroundWithPlaceholder()
        voiceSettings = VoiceSettingsRepository(applicationContext)
        DiagnosticReporter.init(applicationContext)
        Log.i(TAG, "Service created and promoted to foreground")
    }

    /** Minimal notification used during startup to satisfy the 5-second
     *  startForeground() deadline before we've had a chance to read user
     *  preferences. onStartCommand will replace this with the real one.
     *
     *  If this throws, we deliberately LET IT propagate instead of catching.
     *  A swallowed exception here creates a zombie state: the service exists,
     *  the process is alive, but foreground promotion never happened — so
     *  Android will kill the app a few seconds later with a less obvious
     *  trace. Better to crash fast and loud at the actual point of failure.
     */
    private fun startForegroundWithPlaceholder() {
        val placeholder = androidx.core.app.NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Jane")
            .setContentText("Listening…")
            .setOngoing(true)
            .setPriority(androidx.core.app.NotificationCompat.PRIORITY_LOW)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                NOTIFICATION_ID, placeholder,
                android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                    or android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK,
            )
        } else {
            startForeground(NOTIFICATION_ID, placeholder)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // We're past the 5-second foreground-promotion deadline at this point
        // (onCreate already called startForeground with the placeholder), so
        // clear the in-flight guard so future legitimate starts (after a stop)
        // aren't blocked.
        startInFlight.set(false)
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        // Foreground promotion already happened in onCreate — here we just
        // UPDATE the notification with the user's real trigger phrase.
        try {
            val triggerPhrase = voiceSettings.getTriggerPhrase()
            val notification = buildListeningNotification(triggerPhrase)
            val nm = getSystemService(NOTIFICATION_SERVICE) as? android.app.NotificationManager
            nm?.notify(NOTIFICATION_ID, notification)
        } catch (e: Throwable) {
            Log.w(TAG, "failed to update notification with trigger phrase", e)
        }
        if (listeningThread?.isAlive != true) {
            DiagnosticReporter.serviceEvent("AlwaysListening", "started")
            acquireWakeLock()
            startListeningLoop()
        }
        if (!screenReceiverRegistered) {
            val filter = IntentFilter().apply {
                addAction(Intent.ACTION_SCREEN_OFF)
                addAction(Intent.ACTION_SCREEN_ON)
            }
            registerReceiver(screenReceiver, filter)
            screenReceiverRegistered = true
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        DiagnosticReporter.serviceEvent("AlwaysListening", "stopped")
        // Clear the start-in-flight guard immediately so a subsequent start()
        // from another caller can proceed without waiting for the rest of
        // onDestroy to finish (we're about to tear down the listener thread
        // which can take up to 3 seconds on the join below).
        startInFlight.set(false)
        if (screenReceiverRegistered) {
            unregisterReceiver(screenReceiver)
            screenReceiverRegistered = false
        }
        isListening = false
        _running.value = false
        // Stop the listener thread and WAIT for it to exit before closing resources
        listeningThread?.let { thread ->
            thread.interrupt()
            try { thread.join(3000) } catch (_: InterruptedException) {}
        }
        listeningThread = null
        // Now safe to close resources — thread is no longer using them
        audioRecord?.let { record ->
            runCatching {
                if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    record.stop()
                }
                record.release()
            }
        }
        audioRecord = null
        detector?.close()
        detector = null
        releaseWakeLock()
        scope.cancel()
        super.onDestroy()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Always Listening", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Shows when Vessence is listening for your wake word"
                    setShowBadge(false)
                }
            )
            // High-priority channel for wake word detection — needed for full-screen intent
            manager.createNotificationChannel(
                NotificationChannel("wake_word_alert", "Wake Word Alert", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Alerts when wake word is detected"
                    setShowBadge(false)
                }
            )
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
        val stopIntent = Intent(this, AlwaysListeningService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this, 1, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Vessence is listening")
            .setContentText("Say '$triggerPhrase' to talk to Jane")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .addAction(0, "Stop", stopPendingIntent)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }

    private fun acquireWakeLock() {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "vessence:always_listening",
        ).apply {
            acquire(4 * 60 * 60 * 1000L)  // 4 hour timeout — prevents leak if service dies without onDestroy
        }
    }

    private fun releaseWakeLock() {
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
    }

    /** Pause listening (screen off): stop thread, release mic and wake lock, but keep service alive */
    private fun pauseListening() {
        isListening = false
        _running.value = false
        listeningThread?.let { thread ->
            thread.interrupt()
            try { thread.join(3000) } catch (_: InterruptedException) {}
        }
        listeningThread = null
        audioRecord?.let { record ->
            runCatching {
                if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    record.stop()
                }
                record.release()
            }
        }
        audioRecord = null
        releaseWakeLock()
    }

    /** Resume listening (screen on): re-acquire wake lock and restart the listening loop */
    private fun resumeListening() {
        if (listeningThread?.isAlive == true) return  // already running
        acquireWakeLock()
        startListeningLoop()
    }

    @Suppress("DEPRECATION")
    private fun isInCall(): Boolean {
        return try {
            val tm = getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
            tm?.callState != TelephonyManager.CALL_STATE_IDLE
        } catch (_: SecurityException) {
            false  // Can't check — assume not in call
        }
    }

    private fun isMediaPlaying(): Boolean {
        return try {
            val am = getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
            am?.isMusicActive == true
        } catch (_: Exception) {
            false
        }
    }

    private fun startListeningLoop() {
        isListening = true
        _running.value = true
        // Periodic heartbeat so we can confirm the service is actually running
        scope.launch {
            var beatCount = 0
            while (isListening) {
                beatCount++
                val threshold = voiceSettings.getWakeWordThreshold()
                val detectorAlive = detector != null
                Log.i(TAG, "♥ heartbeat #$beatCount — detector=$detectorAlive threshold=$threshold listening=$isListening thread=${listeningThread?.isAlive}")
                DiagnosticReporter.report("service", "heartbeat", mapOf(
                    "beat" to beatCount,
                    "detector_alive" to detectorAlive,
                    "threshold" to threshold,
                    "thread_alive" to (listeningThread?.isAlive == true),
                ))
                kotlinx.coroutines.delay(30_000)  // every 30s
            }
        }
        listeningThread = Thread({
            Log.i(TAG, "Listening thread started")
            DiagnosticReporter.serviceEvent("AlwaysListening", "thread_started")
            try {
                while (isListening) {
                    if (isInCall() || isMediaPlaying()) {
                        try {
                            Thread.sleep(2000)
                        } catch (_: InterruptedException) {
                            Log.i(TAG, "Listening thread interrupted during pause-sleep — exiting cleanly")
                            return@Thread
                        }
                        continue
                    }
                    try {
                        runWakeWordDetection()
                    } catch (ie: InterruptedException) {
                        Log.i(TAG, "Listening thread interrupted during detection — exiting cleanly")
                        return@Thread
                    } catch (e: Exception) {
                        Log.e(TAG, "Wake word detection error", e)
                        DiagnosticReporter.nonFatalError("AlwaysListening", "detection_loop_error", e)
                        if (isListening) {
                            try {
                                Thread.sleep(3000)
                            } catch (_: InterruptedException) {
                                Log.i(TAG, "Listening thread interrupted during error-backoff — exiting cleanly")
                                return@Thread
                            }
                        }
                    }
                }
            } catch (ie: InterruptedException) {
                Log.i(TAG, "Listening thread interrupted — exiting cleanly")
            }
            Log.i(TAG, "Listening thread exiting")
        }, "oww-listener").apply { start() }
    }

    // ── Wake Word Detection (OpenWakeWord) ──────────────────────────────────

    private fun runWakeWordDetection() {
        if (detector == null) {
            val threshold = voiceSettings.getWakeWordThreshold()  // user-adjustable via Settings
            Log.i(TAG, "Initializing OpenWakeWord detector (threshold=$threshold)...")
            DiagnosticReporter.serviceEvent("AlwaysListening", "init_start", "threshold=$threshold")
            val t0 = System.currentTimeMillis()
            try {
                detector = OpenWakeWordDetector(applicationContext, threshold = threshold)
                val elapsed = System.currentTimeMillis() - t0
                Log.i(TAG, "OpenWakeWord detector ready (${elapsed}ms, threshold=$threshold)")
                DiagnosticReporter.wakeWordModelLoaded("hey_jane.onnx", elapsed)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to initialize OpenWakeWord detector", e)
                DiagnosticReporter.wakeWordModelFailed("hey_jane.onnx", e.toString())
                return
            }
        }
        val det = detector ?: return

        val minBufSize = AudioRecord.getMinBufferSize(
            OpenWakeWordDetector.SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        val bufferSize = minBufSize.coerceAtLeast(OpenWakeWordDetector.CHUNK_SIZE * 2)
        Log.i(TAG, "AudioRecord minBufSize=$minBufSize, using bufferSize=$bufferSize")

        val record = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                OpenWakeWordDetector.SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize,
            )
        } catch (e: SecurityException) {
            Log.e(TAG, "Microphone permission denied", e)
            DiagnosticReporter.micPermissionState(false)
            return
        }

        if (record.state != AudioRecord.STATE_INITIALIZED) {
            Log.e(TAG, "AudioRecord not initialized! state=${record.state}")
            record.release()
            DiagnosticReporter.micInitFailed("AudioRecord state=${record.state}")
            return
        }

        audioRecord = record
        val buffer = ShortArray(OpenWakeWordDetector.CHUNK_SIZE)
        record.startRecording()
        Log.i(TAG, "Listening for wake word... (recordingState=${record.recordingState})")
        DiagnosticReporter.serviceEvent("AlwaysListening", "mic_started", "bufSize=$bufferSize recState=${record.recordingState}")

        var chunkCount = 0
        var maxScore = 0f
        // Two-stage verification: require CONFIRMATION_FRAMES consecutive detections
        // before triggering. This eliminates single-frame spikes from background speech.
        // At 80ms per chunk, 5 frames = 400ms of sustained detection.
        val CONFIRMATION_FRAMES = 5
        var consecutiveDetections = 0

        try {
            while (isListening) {
                val read = record.read(buffer, 0, buffer.size)
                if (read <= 0) {
                    Log.w(TAG, "AudioRecord.read returned $read")
                    continue
                }
                chunkCount++

                if (det.feedShorts(buffer, read)) {
                    consecutiveDetections++
                    if (consecutiveDetections < CONFIRMATION_FRAMES) {
                        // Still accumulating confirmation — keep listening
                        if (consecutiveDetections == 1) {
                            Log.d(TAG, "🔍 Stage 1 candidate (score=${det.lastScore}), confirming...")
                        }
                        continue
                    }
                    // Stage 2: confirmed — N consecutive frames above threshold
                    val now = System.currentTimeMillis()
                    val elapsed = now - lastTriggerTimestamp
                    if (elapsed < TRIGGER_COOLDOWN_MS) {
                        Log.i(TAG, "🎯 Confirmed detection but COOLDOWN active (${elapsed}ms) — ignoring")
                        consecutiveDetections = 0
                        det.reset()
                        continue
                    }
                    lastTriggerTimestamp = now
                    Log.i(TAG, "🎯 Wake word CONFIRMED! score=${det.lastScore} after $consecutiveDetections consecutive frames")
                    DiagnosticReporter.wakeWordDetected(det.lastScore)
                    onWakeWordDetected()
                    det.reset()
                    return
                } else {
                    // Score dropped below threshold — reset confirmation counter
                    if (consecutiveDetections > 0) {
                        Log.d(TAG, "🔍 Candidate rejected after $consecutiveDetections frames (score dropped to ${det.lastScore})")
                    }
                    consecutiveDetections = 0
                }

                // Track max score and send periodic updates
                if (det.lastScore > maxScore) maxScore = det.lastScore
                if (chunkCount % 625 == 0) {  // ~every 50s (625 * 80ms)
                    Log.i(TAG, "📊 status: chunks=$chunkCount maxScore=%.4f lastScore=%.4f".format(maxScore, det.lastScore))
                    DiagnosticReporter.report("wakeword", "periodic_status", mapOf(
                        "chunks_processed" to chunkCount,
                        "max_score" to maxScore,
                        "last_score" to det.lastScore,
                    ))
                    maxScore = 0f  // reset per reporting period
                }
            }
        } finally {
            runCatching {
                if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    record.stop()
                }
                record.release()
            }
            audioRecord = null
        }
    }

    // ── Wake Word Detected → Stop service, open chat, let ChatViewModel restart us ──

    private fun onWakeWordDetected() {
        Log.i(TAG, "Wake word detected — stopping service, handing off to chat")
        DiagnosticReporter.wakeWordDetected(detector?.lastScore ?: 0f)

        // Log device info for debugging background launch issues
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val isScreenOn = pm.isInteractive
        val sdkVersion = Build.VERSION.SDK_INT
        val manufacturer = Build.MANUFACTURER
        val model = Build.MODEL
        val product = Build.PRODUCT
        Log.i(TAG, "📱 Device: $manufacturer $model (SDK $sdkVersion, product=$product)")
        Log.i(TAG, "📱 Screen interactive: $isScreenOn")
        DiagnosticReporter.report("wakeword", "device_info", mapOf(
            "sdk_version" to sdkVersion,
            "manufacturer" to manufacturer,
            "model" to model,
            "screen_interactive" to isScreenOn,
            "product" to product,
        ))

        // Check if app can launch from background (Android 10+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as android.app.ActivityManager
            val appTasks = am.appTasks
            val isInForeground = appTasks.any { task ->
                task.taskInfo?.isRunning == true
            }
            Log.i(TAG, "📱 App tasks: ${appTasks.size}, isInForeground=$isInForeground")
            DiagnosticReporter.report("wakeword", "app_state", mapOf(
                "app_tasks" to appTasks.size,
                "is_in_foreground" to isInForeground,
            ))
        }

        // Vibrate to acknowledge wake word
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vm.defaultVibrator.vibrate(VibrationEffect.createOneShot(150, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                val vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
                vibrator.vibrate(VibrationEffect.createOneShot(150, VibrationEffect.DEFAULT_AMPLITUDE))
            }
            Log.i(TAG, "📱 Vibration triggered")
        } catch (e: Exception) {
            Log.w(TAG, "📱 Vibration failed: ${e.message}")
        }

        // Wake the screen if it's off
        if (!isScreenOn) {
            Log.i(TAG, "📱 Screen is off — acquiring wake lock to turn it on")
            @Suppress("DEPRECATION")
            val screenWake = pm.newWakeLock(
                PowerManager.FULL_WAKE_LOCK
                    or PowerManager.ACQUIRE_CAUSES_WAKEUP
                    or PowerManager.ON_AFTER_RELEASE,
                "vessence:wake_word_screen",
            )
            screenWake.acquire(10_000L)
            Log.i(TAG, "📱 Screen wake lock acquired")
        }

        // Mark STT active BEFORE stopping — prevents onResume from restarting always-listen
        WakeWordBridge.sttActive = true

        // Launch STT directly — works from any screen
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            com.vessences.android.MainActivity.instance?.launchStt()
            Log.i(TAG, "📱 STT launched")
        }

        // STOP the service completely.
        isListening = false
        _running.value = false
        stopSelf()
    }
}
