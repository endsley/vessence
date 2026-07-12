package com.vessences.android.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vessences.android.data.model.ShareLink
import com.vessences.android.data.model.TrustedDevice
import com.vessences.android.data.repository.SettingsRepository
import com.vessences.android.data.repository.VoiceSettingsRepository
import com.vessences.android.voice.AlwaysListeningService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

import com.vessences.android.util.ChatPreferences

data class SettingsUiState(
    val devices: List<TrustedDevice> = emptyList(),
    val shares: List<ShareLink> = emptyList(),
    val modelTiers: List<com.vessences.android.data.model.ModelTier> = emptyList(),
    val alwaysListeningEnabled: Boolean = false,
    val autoListenAfterTts: Boolean = true,
    val interruptibleVoiceMode: Boolean = false,
    val triggerPhrase: String = "hey jane",
    val triggerTrained: Boolean = false,
    val wakeWordThreshold: Float = com.vessences.android.util.Constants.DEFAULT_WAKE_WORD_THRESHOLD,
    val dndEnabled: Boolean = false,
    val dndStartHour: Int = com.vessences.android.util.Constants.DEFAULT_DND_START_HOUR,
    val dndStartMinute: Int = com.vessences.android.util.Constants.DEFAULT_DND_START_MINUTE,
    val dndEndHour: Int = com.vessences.android.util.Constants.DEFAULT_DND_END_HOUR,
    val dndEndMinute: Int = com.vessences.android.util.Constants.DEFAULT_DND_END_MINUTE,
    val dndPolicyAccessGranted: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,
)

class SettingsViewModel(private val context: Context) : ViewModel() {
    private val repo = SettingsRepository()
    private val voiceSettings = VoiceSettingsRepository(context.applicationContext)
    private val chatPrefs = ChatPreferences(context.applicationContext)
    private val _state = MutableStateFlow(
        SettingsUiState(
            alwaysListeningEnabled = voiceSettings.isAlwaysListeningEnabled(),
            autoListenAfterTts = chatPrefs.isAutoListenEnabled(),
            interruptibleVoiceMode = chatPrefs.isInterruptibleVoiceEnabled(),
            triggerPhrase = voiceSettings.getTriggerPhrase(),
            triggerTrained = voiceSettings.isTriggerTrained(),
            wakeWordThreshold = voiceSettings.getWakeWordThreshold(),
            dndEnabled = com.vessences.android.tools.DndScheduler.isEnabled(context.applicationContext),
            dndStartHour = com.vessences.android.tools.DndScheduler.getStart(context.applicationContext).first,
            dndStartMinute = com.vessences.android.tools.DndScheduler.getStart(context.applicationContext).second,
            dndEndHour = com.vessences.android.tools.DndScheduler.getEnd(context.applicationContext).first,
            dndEndMinute = com.vessences.android.tools.DndScheduler.getEnd(context.applicationContext).second,
            dndPolicyAccessGranted = com.vessences.android.tools.DndScheduler.hasPolicyAccess(context.applicationContext),
        )
    )
    val state: StateFlow<SettingsUiState> = _state

    init {
        loadAll()
    }

    fun loadAll() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true)
            val devices = repo.getDevices().getOrDefault(emptyList())
            val shares = repo.getShares().getOrDefault(emptyList())
            val modelTiers = repo.getModelSettings().map { it.tiers }.getOrDefault(emptyList())
            _state.value = _state.value.copy(
                devices = devices,
                shares = shares,
                modelTiers = modelTiers,
                alwaysListeningEnabled = voiceSettings.isAlwaysListeningEnabled(),
                autoListenAfterTts = chatPrefs.isAutoListenEnabled(),
                interruptibleVoiceMode = chatPrefs.isInterruptibleVoiceEnabled(),
                triggerPhrase = voiceSettings.getTriggerPhrase(),
                triggerTrained = voiceSettings.isTriggerTrained(),
                wakeWordThreshold = voiceSettings.getWakeWordThreshold(),
                isLoading = false,
            )
        }
    }

    fun revokeDevice(id: String) {
        viewModelScope.launch {
            repo.revokeDevice(id).onSuccess { loadAll() }
        }
    }

    fun revokeShare(id: String) {
        viewModelScope.launch {
            repo.revokeShare(id).onSuccess { loadAll() }
        }
    }

    fun setAlwaysListeningEnabled(enabled: Boolean) {
        voiceSettings.setAlwaysListeningEnabled(enabled)
        _state.value = _state.value.copy(alwaysListeningEnabled = enabled)
        if (enabled) {
            // Request battery optimization exemption for reliable screen-off operation
            requestBatteryOptimizationExemption()
            AlwaysListeningService.start(context.applicationContext)
        } else {
            AlwaysListeningService.stop(context.applicationContext)
        }
    }

    private fun requestBatteryOptimizationExemption() {
        val pm = context.getSystemService(android.content.Context.POWER_SERVICE) as android.os.PowerManager
        if (!pm.isIgnoringBatteryOptimizations(context.packageName)) {
            val intent = android.content.Intent(
                android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                android.net.Uri.parse("package:${context.packageName}")
            )
            intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
            try {
                context.startActivity(intent)
            } catch (_: Exception) {}
        }
    }

    fun setAutoListenAfterTts(enabled: Boolean) {
        chatPrefs.setAutoListenEnabled(enabled)
        _state.value = _state.value.copy(autoListenAfterTts = enabled)
    }

    fun setInterruptibleVoiceMode(enabled: Boolean) {
        chatPrefs.setInterruptibleVoiceEnabled(enabled)
        _state.value = _state.value.copy(interruptibleVoiceMode = enabled)
    }

    fun sendDiagnosticPing() {
        com.vessences.android.DiagnosticReporter.init(context)
        com.vessences.android.DiagnosticReporter.report("service", "manual_ping", mapOf(
            "always_listening" to _state.value.alwaysListeningEnabled,
            "threshold" to _state.value.wakeWordThreshold,
            "trigger_phrase" to _state.value.triggerPhrase,
            "source" to "settings_button",
        ))
    }

    fun setWakeWordThreshold(threshold: Float) {
        voiceSettings.setWakeWordThreshold(threshold)
        _state.value = _state.value.copy(wakeWordThreshold = threshold)
        // Don't restart service on every slider move — threshold picks up on next service start.
        // User can leave Settings to trigger onResume → service restart.
    }

    fun setDndEnabled(enabled: Boolean) {
        val app = context.applicationContext
        com.vessences.android.tools.DndScheduler.setEnabled(app, enabled)
        _state.value = _state.value.copy(
            dndEnabled = enabled,
            dndPolicyAccessGranted = com.vessences.android.tools.DndScheduler.hasPolicyAccess(app),
        )
    }

    fun setDndStart(hour: Int, minute: Int) {
        com.vessences.android.tools.DndScheduler.setStart(context.applicationContext, hour, minute)
        _state.value = _state.value.copy(dndStartHour = hour, dndStartMinute = minute)
    }

    fun setDndEnd(hour: Int, minute: Int) {
        com.vessences.android.tools.DndScheduler.setEnd(context.applicationContext, hour, minute)
        _state.value = _state.value.copy(dndEndHour = hour, dndEndMinute = minute)
    }

    fun refreshDndPolicyAccess() {
        val granted = com.vessences.android.tools.DndScheduler.hasPolicyAccess(context.applicationContext)
        _state.value = _state.value.copy(dndPolicyAccessGranted = granted)
        if (granted && _state.value.dndEnabled) {
            com.vessences.android.tools.DndScheduler.applyAndSchedule(context.applicationContext)
        }
    }
}
