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
        // Sync contacts to server on startup (respects 6-hour interval)
        CoroutineScope(Dispatchers.IO).launch {
            try { ContactsSyncManager.syncIfNeeded(applicationContext) } catch (_: Exception) {}
        }
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

    companion object {
        @Volatile var instance: MainActivity? = null
        private const val PREF_NOTIFICATION_LISTENER_PROMPTED = "notification_listener_prompted"
    }
}
