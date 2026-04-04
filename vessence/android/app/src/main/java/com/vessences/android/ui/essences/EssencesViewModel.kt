package com.vessences.android.ui.essences

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vessences.android.data.model.Essence
import com.vessences.android.data.repository.EssenceRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class EssencesUiState(
    val essences: List<Essence> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val selectedEssence: Essence? = null,
    val actionInProgress: String? = null,
)

class EssencesViewModel : ViewModel() {
    private val repo = EssenceRepository()
    private val _state = MutableStateFlow(EssencesUiState())
    val state: StateFlow<EssencesUiState> = _state

    init {
        try {
            loadEssences()
        } catch (e: Exception) {
            _state.value = _state.value.copy(
                isLoading = false,
                error = "Failed to initialize: ${e.message}"
            )
        }
    }

    fun loadEssences() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            try {
                repo.listEssences().onSuccess { essences ->
                    // Order: Work Log always last, rest alphabetical
                    val sorted = essences.sortedWith(
                        compareBy<Essence> { if (it.name == "Work Log") 1 else 0 }
                            .thenBy { it.name }
                    )
                    _state.value = _state.value.copy(
                        essences = sorted,
                        isLoading = false,
                    )
                }.onFailure { e ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = e.message ?: "Failed to load essences"
                    )
                }
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = "Network error: ${e.message}"
                )
            }
        }
    }

    fun selectEssence(essence: Essence?) {
        _state.value = _state.value.copy(selectedEssence = essence)
    }

    fun loadEssence(name: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(actionInProgress = name)
            repo.loadEssence(name).onSuccess {
                loadEssences()
            }.onFailure { e ->
                _state.value = _state.value.copy(error = e.message, actionInProgress = null)
            }
        }
    }

    fun unloadEssence(name: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(actionInProgress = name)
            repo.unloadEssence(name).onSuccess {
                loadEssences()
            }.onFailure { e ->
                _state.value = _state.value.copy(error = e.message, actionInProgress = null)
            }
        }
    }

    fun activateEssence(name: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(actionInProgress = name)
            repo.activateEssence(name).onSuccess {
                loadEssences()
            }.onFailure { e ->
                _state.value = _state.value.copy(error = e.message, actionInProgress = null)
            }
        }
    }

    fun deleteEssence(name: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(actionInProgress = name)
            repo.deleteEssence(name).onSuccess {
                _state.value = _state.value.copy(selectedEssence = null)
                loadEssences()
            }.onFailure { e ->
                _state.value = _state.value.copy(error = e.message, actionInProgress = null)
            }
        }
    }
}
