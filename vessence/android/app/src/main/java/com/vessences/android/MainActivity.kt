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
import com.vessences.android.data.api.ApiClient
import com.vessences.android.notifications.ChatNotificationManager
import com.vessences.android.ui.theme.ThemePreferences
import com.vessences.android.ui.theme.VessenceTheme

class MainActivity : ComponentActivity() {
    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    /** Global STT launcher — callable from anywhere via MainActivity.instance.launchStt() */
    val sttLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        SttResultBus.postResult(result.resultCode, result.data)
    }

    fun launchStt() {
        val hasMicPerm = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        if (!hasMicPerm) return

        com.vessences.android.voice.WakeWordBridge.sttActive = true
        com.vessences.android.voice.AlwaysListeningService.stop(this)

        val intent = Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL, android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE, java.util.Locale.getDefault())
            putExtra(android.speech.RecognizerIntent.EXTRA_PROMPT, "Speak your message...")
            putExtra(android.speech.RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000L)
            putExtra(android.speech.RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 6000L)
        }
        sttLauncher.launch(intent)
    }

    companion object {
        @Volatile var instance: MainActivity? = null
    }

    override fun onResume() {
        super.onResume()
        ChatNotificationManager.isAppInForeground = true
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
        requestNotificationPermissionIfNeeded()
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
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleWakeWordIntent(intent)
        handleIncomingShareIntent(intent)
        handleNotificationIntent(intent)
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
}
