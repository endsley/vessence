package com.vessences.android

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import com.vessences.android.contacts.ContactsSyncManager
import com.vessences.android.contacts.SmsSyncManager
import com.vessences.android.data.api.ApiClient
import com.vessences.android.notifications.ChatNotificationManager
import com.vessences.android.ui.theme.ThemePreferences
import com.vessences.android.ui.theme.VessenceTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    /**
     * Jane Phone Tools: multi-permission launcher for READ_CONTACTS, CALL_PHONE,
     * SEND_SMS. Requested together on first launch so the handlers don't hit
     * "permission denied" on the first tool invocation.
     */
    private val phoneToolsPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        // Log-only — handlers re-check permission at invocation time and
        // surface a NeedsUser status if anything is still missing.
        val denied = grants.filterValues { !it }.keys
        if (denied.isNotEmpty()) {
            android.util.Log.i("MainActivity", "phone tools permissions denied: $denied")
        }
    }

    /** Active headless STT recognizer (main-thread only). Replaced on each call. */
    private var activeRecognizer: android.speech.SpeechRecognizer? = null

    /**
     * Launch headless STT (no system dialog). Uses Android SpeechRecognizer directly
     * so errors auto-dismiss without requiring a manual tap. On no-speech / error,
     * AlwaysListening is silently restored. On success, result flows to SttResultBus.
     */
    fun launchStt() {
        val hasMicPerm = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        if (!hasMicPerm) {
            com.vessences.android.voice.WakeWordBridge.sttActive = false
            return
        }

        com.vessences.android.voice.WakeWordBridge.sttActive = true
        com.vessences.android.voice.AlwaysListeningService.stop(this)

        // SpeechRecognizer must be created on the main thread
        runOnUiThread {
            activeRecognizer?.destroy()
            activeRecognizer = null

            if (!android.speech.SpeechRecognizer.isRecognitionAvailable(this)) {
                restoreAlwaysListening()
                return@runOnUiThread
            }

            val recognizer = android.speech.SpeechRecognizer.createSpeechRecognizer(this)
            activeRecognizer = recognizer

            val intent = Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE, java.util.Locale.getDefault())
                // Wait at least 2s for speech to start before timing out
                putExtra(android.speech.RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 2000L)
                putExtra(android.speech.RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
                putExtra(android.speech.RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 6000L)
                putExtra(android.speech.RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            }

            var done = false
            recognizer.setRecognitionListener(object : android.speech.RecognitionListener {
                override fun onResults(results: android.os.Bundle?) {
                    if (done) return; done = true
                    activeRecognizer = null
                    recognizer.destroy()
                    SttResultBus.onListening?.invoke(false)
                    val matches = results?.getStringArrayList(
                        android.speech.SpeechRecognizer.RESULTS_RECOGNITION)
                    val spoken = matches?.firstOrNull()?.trim()
                    if (!spoken.isNullOrBlank()) {
                        SttResultBus.onResult?.invoke(spoken)
                    } else {
                        restoreAlwaysListening()
                    }
                }

                override fun onError(error: Int) {
                    if (done) return; done = true
                    activeRecognizer = null
                    recognizer.destroy()
                    SttResultBus.onListening?.invoke(false)
                    // No speech or recognizer error — silently restore always-listen
                    restoreAlwaysListening()
                }

                override fun onReadyForSpeech(params: android.os.Bundle?) {
                    // Notify UI that we're actively listening
                    SttResultBus.onListening?.invoke(true)
                    // Play a short beep so the user knows it's their turn to speak
                    try {
                        val tg = android.media.ToneGenerator(
                            android.media.AudioManager.STREAM_MUSIC, 60)
                        tg.startTone(android.media.ToneGenerator.TONE_PROP_BEEP, 120)
                        android.os.Handler(android.os.Looper.getMainLooper())
                            .postDelayed({ tg.release() }, 300)
                    } catch (_: Exception) {}
                }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onPartialResults(partial: android.os.Bundle?) {
                    val preview = partial?.getStringArrayList(
                        android.speech.SpeechRecognizer.RESULTS_RECOGNITION
                    )?.firstOrNull()?.trim()
                    if (!preview.isNullOrBlank()) {
                        SttResultBus.onPartialResult?.invoke(preview)
                    }
                }
                override fun onEvent(eventType: Int, params: android.os.Bundle?) {}
            })

            recognizer.startListening(intent)
        }
    }

    private fun restoreAlwaysListening() {
        com.vessences.android.voice.WakeWordBridge.sttActive = false
        val voiceSettings = com.vessences.android.data.repository.VoiceSettingsRepository(applicationContext)
        if (voiceSettings.isAlwaysListeningEnabled()) {
            com.vessences.android.voice.AlwaysListeningService.start(applicationContext)
        }
    }

    private var permissionsRequested = false

    override fun onResume() {
        super.onResume()
        ChatNotificationManager.isAppInForeground = true
        // Request permissions after the activity is fully visible so the
        // dialog reliably appears on first launch (not swallowed by the
        // installer activity still being in the foreground).
        if (!permissionsRequested) {
            permissionsRequested = true
            window.decorView.post {
                requestNotificationPermissionIfNeeded()
                requestPhoneToolsPermissionsIfNeeded()
                promptNotificationListenerIfNeeded()
            }
        }
        // Start wake word listening only if not in an active voice conversation
        // (STT popup returning triggers onResume — don't restart listening mid-conversation)
        val voiceSettings = com.vessences.android.data.repository.VoiceSettingsRepository(this)
        if (voiceSettings.isAlwaysListeningEnabled() && !com.vessences.android.voice.WakeWordBridge.sttActive) {
            com.vessences.android.voice.AlwaysListeningService.start(this)
        }
    }

    override fun onPause() {
        super.onPause()
        ChatNotificationManager.isAppInForeground = false
        // Stop wake word listening when app goes to background
        com.vessences.android.voice.AlwaysListeningService.stop(this)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        instance = this
        // Draw behind system bars (status bar + navigation bar) — removes white bar
        androidx.core.view.WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        handleWakeWordIntent(intent)
        CrashReporter.install(applicationContext)
        DiagnosticReporter.init(applicationContext)
        ApiClient.init(applicationContext)
        // Sync contacts and SMS messages to server on startup
        CoroutineScope(Dispatchers.IO).launch {
            try { ContactsSyncManager.syncIfNeeded(applicationContext) } catch (_: Exception) {}
            try { SmsSyncManager.backfillIfNeeded(applicationContext) } catch (_: Exception) {}
        }
        // Periodic SMS sync every 5 minutes — catches sent messages and
        // fills gaps if notification listener was killed by the system
        SmsSyncManager.startPeriodicSync(applicationContext)
        try { ChatNotificationManager(applicationContext).ensureChannels() } catch (_: Exception) {}
        // Auto-start wake word service if always-listen was enabled
        // BUT skip if this is a wake word intent — service just stopped itself on purpose
        val isWakeWordLaunch = intent?.getBooleanExtra("wake_word", false) == true
        if (!isWakeWordLaunch) {
            try {
                val voicePrefs = com.vessences.android.data.repository.VoiceSettingsRepository(applicationContext)
                if (voicePrefs.isAlwaysListeningEnabled()) {
                    com.vessences.android.voice.AlwaysListeningService.start(applicationContext)
                }
            } catch (_: Exception) {}
        }
        try { ThemePreferences.init(applicationContext) } catch (_: Exception) {}
        // Apply "keep screen on" if enabled
        try {
            val prefs = getSharedPreferences(com.vessences.android.util.Constants.PREFS_NAME, MODE_PRIVATE)
            if (prefs.getBoolean(com.vessences.android.util.Constants.PREF_KEEP_SCREEN_ON, true)) {
                window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }
        } catch (_: Exception) {}
        handleIncomingShareIntent(intent)
        handleNotificationIntent(intent)

        setContent {
            VessenceTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFF0F172A),
                ) {
                    VessencesApp()
                }
            }
        }
        // If launched directly from ShareReceiverActivity with a summary,
        // dispatch it after the UI mounts (slight delay so chat is ready).
        if (intent?.hasExtra("shared_summary_text") == true) {
            window.decorView.post { handleSharedSummaryIntent(intent) }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleWakeWordIntent(intent)
        handleIncomingShareIntent(intent)
        handleNotificationIntent(intent)
        handleSharedSummaryIntent(intent)
    }

    /**
     * When ShareReceiverActivity finishes summarizing a shared URL, it
     * launches MainActivity with the summary text as an extra. Post the
     * summary into the chat as an assistant message and trigger TTS via
     * the main app's TTS path so the user can stop, replay, etc.
     */
    private fun handleSharedSummaryIntent(intent: Intent?) {
        val text = intent?.getStringExtra("shared_summary_text") ?: return
        if (text.isBlank()) return
        // Clear so a configuration change doesn't replay it
        intent.removeExtra("shared_summary_text")
        val shouldSpeak = intent.getBooleanExtra("shared_summary_speak", true)
        intent.removeExtra("shared_summary_speak")
        try {
            // Push to ChatViewModel via a shared channel — exposed through
            // a broadcast so the active Compose chat picks it up.
            val broadcastIntent = Intent("com.vessences.android.SHARED_SUMMARY_READY").apply {
                putExtra("text", text)
                putExtra("speak", shouldSpeak)
                setPackage(packageName)
            }
            sendBroadcast(broadcastIntent)
        } catch (e: Exception) {
            android.util.Log.w("MainActivity", "Failed to dispatch shared summary: ${e.message}")
        }
    }

    private fun handleWakeWordIntent(intent: Intent?) {
        if (intent?.getBooleanExtra("wake_word", false) == true) {
            // Screen-off wake word disabled for now (v0.1.36+).
            // Lock screen bypass code removed to avoid Android security warnings.
            // When re-enabling screen-off wake word, add back setShowWhenLocked/setTurnScreenOn
            // and USE_FULL_SCREEN_INTENT permission.
            /*
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                setShowWhenLocked(true)
                setTurnScreenOn(true)
            } else {
                @Suppress("DEPRECATION")
                window.addFlags(
                    android.view.WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                        or android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                )
            }
            // Dismiss keyguard so STT can run
            val keyguardManager = getSystemService(android.app.KeyguardManager::class.java)
            keyguardManager?.requestDismissKeyguard(this, null)
            */
        }
    }

    private fun handleNotificationIntent(intent: Intent?) {
        val openChat = intent?.getStringExtra("open_chat")
        if (openChat != null) {
            // Signal the app to navigate to the chat screen
            NotificationNavigationState.pendingChatTarget = openChat
        }
    }

    private fun handleIncomingShareIntent(intent: Intent?) {
        if (intent == null) return
        when (intent.action) {
            Intent.ACTION_SEND -> {
                // Shared text (e.g. URL or plain text)
                intent.getStringExtra(Intent.EXTRA_TEXT)?.let { text ->
                    SharedIntentState.setSharedText(text)
                }
                // Shared file attachment
                @Suppress("DEPRECATION")
                val uri: Uri? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                } else {
                    intent.getParcelableExtra(Intent.EXTRA_STREAM)
                }
                if (uri != null) {
                    SharedIntentState.setSharedUris(listOf(uri))
                }
            }
            Intent.ACTION_SEND_MULTIPLE -> {
                @Suppress("DEPRECATION")
                val uris: List<Uri>? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
                } else {
                    intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM)
                }
                if (!uris.isNullOrEmpty()) {
                    SharedIntentState.setSharedUris(uris)
                }
            }
        }
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    /**
     * Jane Phone Tools: on first launch, proactively request the three runtime
     * permissions the phone-tools handlers need. If any are already granted,
     * Android no-ops silently. If all three are granted, this call is a no-op
     * so subsequent launches don't show prompts.
     */
    private fun requestPhoneToolsPermissionsIfNeeded() {
        val needed = listOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.READ_CONTACTS,
            Manifest.permission.CALL_PHONE,
            Manifest.permission.SEND_SMS,
            Manifest.permission.READ_SMS,
        ).filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (needed.isEmpty()) return
        phoneToolsPermissionLauncher.launch(needed.toTypedArray())
    }

    /**
     * Check if the NotificationListener service is enabled. If not, show a
     * dialog explaining why it's needed and deep-link to the system settings.
     * Only prompts once — tracks via SharedPreferences so we don't nag.
     */
    private fun promptNotificationListenerIfNeeded() {
        // Check if already enabled
        if (com.vessences.android.notifications.NotificationSafety.isListenerEnabled(this)) return

        // Check if we already prompted (don't nag on every launch)
        val prefs = getSharedPreferences(com.vessences.android.util.Constants.PREFS_NAME, MODE_PRIVATE)
        val prompted = prefs.getBoolean(PREF_NOTIFICATION_LISTENER_PROMPTED, false)
        if (prompted) return

        // Mark as prompted
        prefs.edit().putBoolean(PREF_NOTIFICATION_LISTENER_PROMPTED, true).apply()

        // Show explanation dialog with deep-link to settings
        android.app.AlertDialog.Builder(this)
            .setTitle("Enable Message Reading")
            .setMessage(
                "Jane needs Notification Access to read your text messages and help you triage them.\n\n" +
                "Tap \"Open Settings\" below, then find and enable Jane in the list."
            )
            .setPositiveButton("Open Settings") { _, _ ->
                try {
                    val intent = android.content.Intent(
                        android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS
                    )
                    startActivity(intent)
                } catch (e: Exception) {
                    android.util.Log.w("MainActivity", "Could not open notification listener settings", e)
                }
            }
            .setNegativeButton("Later", null)
            .show()
    }

    override fun onDestroy() {
        super.onDestroy()
        // Clean up active recognizer to release mic on activity teardown
        runOnUiThread {
            activeRecognizer?.destroy()
            activeRecognizer = null
        }
        if (instance === this) instance = null
    }

    companion object {
        @Volatile var instance: MainActivity? = null
        private const val PREF_NOTIFICATION_LISTENER_PROMPTED = "notification_listener_prompted"
    }
}
