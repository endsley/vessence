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

data class SettingsUiState(
    val devices: List<TrustedDevice> = emptyList(),
    val shares: List<ShareLink> = emptyList(),
    val alwaysListeningEnabled: Boolean = false,
    val triggerPhrase: String = "hey jane",
    val triggerTrained: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,
)

class SettingsViewModel(private val context: Context) : ViewModel() {
    private val repo = SettingsRepository()
    private val voiceSettings = VoiceSettingsRepository(context.applicationContext)
    private val _state = MutableStateFlow(
        SettingsUiState(
            alwaysListeningEnabled = voiceSettings.isAlwaysListeningEnabled(),
            triggerPhrase = voiceSettings.getTriggerPhrase(),
            triggerTrained = voiceSettings.isTriggerTrained(),
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
            _state.value = _state.value.copy(
                devices = devices,
                shares = shares,
                alwaysListeningEnabled = voiceSettings.isAlwaysListeningEnabled(),
                triggerPhrase = voiceSettings.getTriggerPhrase(),
                triggerTrained = voiceSettings.isTriggerTrained(),
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
            AlwaysListeningService.start(context.applicationContext)
        } else {
            AlwaysListeningService.stop(context.applicationContext)
        }
    }
}
